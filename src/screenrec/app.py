import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QActionGroup, QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QFileDialog, QMessageBox, QSystemTrayIcon

from .config.settings import Settings
from .recorder.screen import monitors
from .recorder.worker import RecordingWorker
from .ui.main_window import MainWindow
from .ui.tray_menu import create_tray
from .ui.settings_dialog import SettingsDialog
from .config.recording import FORMATS, QUALITIES, AUDIO_MODES
from .ui.sources import SourceController
from .ui.themes.theme_manager import THEMES, apply_theme


class ScreenRecApp(SourceController, QObject):
    def __init__(self, application):
        super().__init__(application)
        self.application = application
        self.settings = Settings.load()
        self.worker = None
        self.exiting = False
        self.started_at = None
        self.stop_deadline = None
        self.icon = QIcon(str(Path(__file__).parent / "assets/icons/icon_blue.svg"))
        application.setWindowIcon(self.icon)
        application.setQuitOnLastWindowClosed(False)
        self.window = MainWindow(self.settings, self.icon)
        self.start_action = QAction("Начать запись", self)
        self.stop_action = QAction("Остановить запись", self)
        self.stop_action.setEnabled(False)
        self.show_action = QAction("Открыть главное окно", self)
        self.exit_action = QAction("Выход", self)
        self.start_action.triggered.connect(self.start_recording)
        self.stop_action.triggered.connect(self.stop_recording)
        self.show_action.triggered.connect(self.show_window)
        self.exit_action.triggered.connect(self.request_exit)
        menu = self.window.menuBar().addMenu("Файл")
        menu.addAction(self.start_action)
        menu.addAction(self.stop_action)
        menu.addSeparator()
        menu.addAction(self.exit_action)
        settings_menu = self.window.menuBar().addMenu("Настройки")
        self.configure_action = settings_menu.addAction("Конфигуратор записи…")
        self.configure_action.triggered.connect(self.configure_recording)
        self.window.configure.clicked.connect(self.configure_recording)
        self.filename_action = settings_menu.addAction("Имя файла…")
        self.filename_action.triggered.connect(self.configure_filename)
        self.window.filename_button.clicked.connect(self.configure_filename)
        self.overlay_action = settings_menu.addAction("Картинка и текст…")
        self.overlay_action.triggered.connect(self.configure_overlay)
        self.window.overlay_button.clicked.connect(self.configure_overlay)
        self.window.overlay_enabled.toggled.connect(self.set_overlay_enabled)
        notifications = settings_menu.addAction("Уведомления")
        notifications.setCheckable(True)
        notifications.setChecked(self.settings.notifications)
        notifications.toggled.connect(self.set_notifications)
        self.tray, self.tray_menu = create_tray(self.window, self.icon, self.start_action,
                                               self.stop_action, self.show_action, self.exit_action)
        self.theme_menu = settings_menu.addMenu("Тема")
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_actions = {}
        for key, theme in THEMES.items():
            action = self.theme_menu.addAction(QIcon(str(theme["window_icon_path"])), theme["label"])
            action.setCheckable(True)
            action.setData(key)
            self.theme_group.addAction(action)
            self.theme_actions[key] = action
        self.theme_group.triggered.connect(lambda action: self.set_theme(action.data()))
        self.set_theme(self.settings.theme, save=False)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.window.start.clicked.connect(self.start_recording)
        self.window.stop.clicked.connect(self.stop_recording)
        self.window.browse.clicked.connect(self.choose_folder)
        self.window.open_folder.clicked.connect(self.open_folder)
        self.window.refresh.clicked.connect(self.refresh_sources)
        self.window.close_requested.connect(self.close_window)
        self.window.close_to_tray.toggled.connect(self.set_close_to_tray)
        self.window.fps.currentTextChanged.connect(self.set_fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(200)
        application.aboutToQuit.connect(self.cleanup)
        self.refresh_monitors()
        self.update_summary()
        self.initialize_sources()

    def configure_filename(self):
        if self.worker:
            return
        from .ui.filename_dialog import FilenameDialog
        dialog = FilenameDialog(self.settings, self.window)
        if dialog.exec():
            self.settings = dialog.result_settings()
            self.save_settings()

    def set_overlay_enabled(self, enabled):
        self.settings.overlay_enabled = enabled
        self.save_settings()

    def configure_overlay(self):
        if self.worker:
            return
        from .ui.overlay_editor import OverlayEditor
        from .recorder.overlay import enabled
        source = self.current_source() or {}
        aspect = source.get("width", 16) / max(1, source.get("height", 9))
        dialog = OverlayEditor(self.settings, self.window, aspect)
        if dialog.exec():
            self.settings.overlay = dialog.template
            self.settings.overlay_name = dialog.names.currentText().strip()
            self.settings.overlay_enabled = enabled(dialog.template)
            self.window.overlay_enabled.blockSignals(True)
            self.window.overlay_enabled.setChecked(self.settings.overlay_enabled)
            self.window.overlay_enabled.blockSignals(False)
            self.save_settings()

    def set_theme(self, name, *, save=True):
        name = name if name in THEMES else "blue"
        self.icon = apply_theme(self.application, self.window, self.tray, name)
        self.settings.theme = name
        self.theme_actions[name].setChecked(True)
        if save:
            self.save_settings()

    def update_summary(self):
        self.window.recording_summary.setText(f"{FORMATS[self.settings.file_format]} • "
            f"{QUALITIES[self.settings.quality]} • {AUDIO_MODES[self.settings.audio_mode]}")

    def configure_recording(self):
        if self.worker:
            return
        dialog = SettingsDialog(self.settings, self.window)
        if dialog.exec():
            self.settings = dialog.result_settings()
            self.window.fps.blockSignals(True)
            self.window.fps.setCurrentText(str(self.settings.fps))
            self.window.fps.blockSignals(False)
            self.update_summary()
            self.save_settings()

    def save_settings(self):
        try:
            self.settings.save()
        except OSError as exc:
            self.error(f"Не удалось сохранить настройки: {exc}")

    def set_notifications(self, value):
        self.settings.notifications = value
        self.save_settings()

    def set_close_to_tray(self, value):
        self.settings.close_to_tray = value
        self.save_settings()

    def set_fps(self, value):
        self.settings.fps = int(value)
        self.save_settings()

    def refresh_monitors(self):
        self.window.monitors.clear()
        try:
            for index, monitor in enumerate(monitors(), 1):
                self.window.monitors.addItem(
                    f"Монитор {index}: {monitor['width']} × {monitor['height']} "
                    f"({monitor['left']}, {monitor['top']})", monitor)
            if not self.window.monitors.count():
                raise RuntimeError("Мониторы не найдены.")
            self.window.status.setText("Готов к записи")
        except Exception as exc:
            self.window.status.setText(str(exc))
        self.set_busy(False)

    def set_busy(self, busy):
        can_start = not busy and bool(self.current_source())
        self.window.start.setEnabled(can_start)
        self.start_action.setEnabled(can_start)
        self.window.stop.setEnabled(busy)
        self.stop_action.setEnabled(busy)
        self.configure_action.setEnabled(not busy)
        self.filename_action.setEnabled(not busy)
        self.window.filename_button.setEnabled(not busy)
        self.overlay_action.setEnabled(not busy)
        self.window.overlay_button.setEnabled(not busy)
        self.window.overlay_enabled.setEnabled(not busy)
        for widget in (self.window.monitors, self.window.refresh, self.window.fps, self.window.browse, self.window.configure, self.window.source_mode, self.window.window_list, self.window.select_region, self.window.export_extension):
            widget.setEnabled(not busy)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self.window, "Папка записей", self.settings.output_dir)
        if folder:
            self.settings.output_dir = folder
            self.window.folder.setText(folder)
            self.save_settings()

    def open_folder(self):
        try:
            directory = Path(self.settings.output_dir)
            directory.mkdir(parents=True, exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve()))):
                raise OSError("Не удалось открыть файловый менеджер.")
        except OSError as exc:
            self.error(str(exc))

    def start_recording(self):
        if self.worker or self.exiting:
            return
        monitor = self.current_source()
        if not monitor:
            return
        if monitor.get("kind") == "tab":
            from .recorder.browser_tab import BrowserWorker
            self.window.pairing.clear()
            self.worker = BrowserWorker(replace(self.settings), self)
            self.worker.pairing_ready.connect(self.show_pairing)
            self.worker.tab_selected.connect(lambda title: self.window.pairing.setToolTip("Записывается: " + title))
        else:
            self.worker = RecordingWorker(monitor, self.settings.output_dir, self.settings.fps, self,
                                          settings=replace(self.settings))
        self.worker.recording_started.connect(self.recording_started)
        self.worker.recording_saved.connect(self.recording_saved)
        self.worker.failed.connect(self.error)
        self.worker.finalizing.connect(self.finalizing)
        self.worker.finished.connect(self.worker_finished)
        self.set_busy(True)
        self.window.status.setText("Подготовка записи…")
        self.worker.start()

    def finalizing(self):
        self.window.status.setText("Сохранение записи и обработка звука…")
        self.window.stop.setEnabled(False)
        self.stop_action.setEnabled(False)

    def recording_started(self, path):
        self.started_at = time.monotonic()
        self.tray.setToolTip("ScreenRec — идёт запись")
        self.notify("Запись начата", path)

    def tick(self):
        if self.stop_deadline and time.monotonic() > self.stop_deadline:
            encoder = self.worker.encoder if self.worker else None
            if encoder:
                encoder.abort()
            self.stop_deadline = None
        if self.started_at is not None and self.worker and not self.worker.stop_event.is_set():
            elapsed = int(time.monotonic() - self.started_at)
            self.window.status.setText(f"● Запись  {elapsed // 3600:02}:{elapsed // 60 % 60:02}:{elapsed % 60:02}")

    def stop_recording(self):
        if self.worker:
            self.worker.stop()
            if self.stop_deadline is None:
                self.stop_deadline = time.monotonic() + 15
            self.window.stop.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.window.status.setText("Завершение записи…")

    def recording_saved(self, path):
        self.window.status.setText(f"Сохранено: {path}")
        self.notify("Запись сохранена", path)

    def worker_finished(self):
        self.worker.wait()
        self.worker.deleteLater()
        self.worker = None
        self.window.pairing.clear()
        self.started_at = None
        self.stop_deadline = None
        self.tray.setToolTip("ScreenRec — готов к записи")
        self.set_busy(False)
        if self.exiting:
            self.application.quit()

    def notify(self, title, text):
        if self.settings.notifications and self.tray.isVisible():
            self.tray.showMessage(title, text)

    def error(self, message):
        self.window.status.setText(f"Ошибка: {message}")
        self.notify("Ошибка ScreenRec", message)
        if not self.exiting:
            self.show_window()
            QMessageBox.warning(self.window, "Ошибка ScreenRec", message)

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def close_window(self):
        if self.settings.close_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
            self.window.hide()
            self.notify("ScreenRec работает в трее", "Для полного закрытия выберите «Выход».")
        else:
            self.request_exit()

    def request_exit(self, checked=False, *, confirm=True):
        if self.exiting:
            return
        if self.worker and confirm:
            answer = QMessageBox.question(self.window, "Завершение работы",
                "Остановить запись, сохранить файл и выйти?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.exiting = True
        self.start_action.setEnabled(False)
        if self.worker:
            self.stop_recording()
        else:
            self.application.quit()

    def cleanup(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(15000):
                encoder = self.worker.encoder
                if encoder:
                    encoder.abort()
                self.worker.wait()
        self.tray.hide()
