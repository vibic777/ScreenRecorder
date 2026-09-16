import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QActionGroup, QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QFileDialog, QMessageBox, QSystemTrayIcon

from .config.settings import Settings
from .config.profiles import save_profile, load_profile, load_default_profile
from .localization import Translator, SUPPORTED_LANGUAGES
from .recorder.screen import monitors
from .recorder.worker import RecordingWorker
from .ui.main_window import MainWindow
from .ui.tray_menu import create_tray
from .ui.settings_dialog import SettingsDialog
from .config.recording import FORMATS, QUALITIES, AUDIO_MODES
from .config.commands import COMMANDS, commands_for
from .ui.sources import SourceController
from .ui.themes.theme_manager import THEMES, apply_theme
from .logger.logger import get_logger, configure as configure_log, hub, shutdown as close_log
log = get_logger(__name__)


class ScreenRecApp(SourceController, QObject):
    def __init__(self, application, profile_path=None):
        super().__init__(application)
        self.application = application
        self.settings = load_profile(profile_path) if profile_path else (load_default_profile() or Settings.load())
        self.translator = Translator(self.settings.language)
        log_warning = self.apply_logging()
        log.info("Application started")
        self.worker = None
        self.exiting = False
        self.started_at = None
        self.stop_deadline = None
        self.icon = QIcon(str(Path(__file__).parent / "assets/icons/icon_gray.svg"))
        application.setWindowIcon(self.icon)
        application.setQuitOnLastWindowClosed(False)
        self.window = MainWindow(self.settings, self.icon)
        self.start_action = QAction(self.translator.tr("action.start"), self)
        self.stop_action = QAction(self.translator.tr("action.stop.full"), self)
        self.stop_action.setEnabled(False)
        self.show_action = QAction(self.translator.tr("window.show"), self)
        self.exit_action = QAction(self.translator.tr("action.exit"), self)
        self.start_action.setShortcut(COMMANDS["start_recording"].shortcut)
        self.stop_action.setShortcut(COMMANDS["stop_recording"].shortcut)
        self.show_action.setShortcut(COMMANDS["show_window"].shortcut)
        self.exit_action.setShortcut(COMMANDS["exit"].shortcut)
        self.start_action.triggered.connect(self.start_recording)
        self.stop_action.triggered.connect(self.stop_recording)
        self.show_action.triggered.connect(self.show_window)
        self.exit_action.triggered.connect(self.request_exit)
        menu = self.window.menuBar().addMenu(self.translator.tr("menu.file", fallback="File"))
        menu.addAction(self.start_action)
        menu.addAction(self.stop_action)
        menu.addSeparator()
        menu.addAction(self.exit_action)
        settings_menu = self.window.menuBar().addMenu(self.translator.tr("menu.settings", fallback="Settings"))
        help_menu = self.window.menuBar().addMenu(self.translator.tr("menu.help", fallback="Help"))
        help_action = help_menu.addAction(self.translator.tr("help.about"))
        help_action.triggered.connect(self.show_help)

        profiles_menu = settings_menu.addMenu(self.translator.tr("profiles.menu"))
        export_profile_action = profiles_menu.addAction(self.translator.tr("profiles.export"))
        export_profile_action.triggered.connect(self.export_profile)
        import_profile_action = profiles_menu.addAction(self.translator.tr("profiles.import"))
        import_profile_action.triggered.connect(self.import_profile)

        self.logging_action = settings_menu.addAction(self.translator.tr("settings.logging"))
        self.logging_action.triggered.connect(self.configure_logging)
        self.configure_action = settings_menu.addAction(self.translator.tr("settings.recording"))
        self.configure_action.triggered.connect(self.configure_recording)
        self.window.configure.clicked.connect(self.configure_recording)
        self.filename_action = settings_menu.addAction(self.translator.tr("settings.filename"))
        self.filename_action.triggered.connect(self.configure_filename)
        self.window.filename_button.clicked.connect(self.configure_filename)
        self.overlay_action = settings_menu.addAction(self.translator.tr("settings.overlay"))
        self.overlay_action.triggered.connect(self.configure_overlay)
        self.window.overlay_button.clicked.connect(self.configure_overlay)
        self.window.overlay_enabled.toggled.connect(self.set_overlay_enabled)
        notifications = settings_menu.addAction(self.translator.tr("settings.notifications"))
        notifications.setCheckable(True)
        notifications.setChecked(self.settings.notifications)
        notifications.toggled.connect(self.set_notifications)
        self.tray, self.tray_menu = create_tray(self.window, self.icon, self.start_action,
                                               self.stop_action, self.show_action, self.exit_action)
        self.language_menu = settings_menu.addMenu(self.translator.tr("menu.language", fallback="Language"))
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.language_actions = {}
        for key, label in SUPPORTED_LANGUAGES.items():
            action = self.language_menu.addAction(label)
            action.setCheckable(True)
            action.setData(key)
            action.setChecked(key == self.settings.language)
            self.language_group.addAction(action)
            self.language_actions[key] = action
        self.language_group.triggered.connect(self.set_language)
        self.theme_menu = settings_menu.addMenu(self.translator.tr("settings.theme"))
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_actions = {}
        for key, theme in THEMES.items():
            action = self.theme_menu.addAction(QIcon(str(theme["window_icon_path"])), self.translator.tr(f"theme.{key}"))
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
        if log_warning:
            QTimer.singleShot(0, lambda: QMessageBox.warning(self.window,self.translator.tr("logging.title"),log_warning))

    def show_help(self):
        shortcuts = "\\n".join(f"{command.shortcut} — {self.translator.tr(command.label_key)}" for command in COMMANDS.values() if command.shortcut)
        text = self.translator.tr("help.description") + "\\n\\n" + self.translator.tr("help.shortcuts") + "\\n" + shortcuts
        QMessageBox.information(self.window, self.translator.tr("help.title"), text)

    def set_language(self, action):
        language = action.data()
        if language == self.settings.language:
            return
        self.settings.language = language
        self.settings.save()
        QMessageBox.information(
            self.window,
            self.translator.tr("language.changed_title"),
            self.translator.tr("language.restart_required"),
        )
    def apply_logging(self):
        path, warning = configure_log(self.settings.logging_enabled,self.settings.log_path,self.settings.log_levels)
        if self.settings.logging_enabled and path is None:
            self.settings.logging_enabled = False
        elif path is not None and warning:
            self.settings.log_path = str(path)
        return warning

    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(
            self.window, self.translator.tr("profiles.import_title"),
            "", self.translator.tr("profiles.file_filter"),
        )
        if not path:
            return
        previous_language = self.settings.language
        loaded = load_profile(Path(path))
        self.settings = loaded
        self.save_settings()
        self.set_theme(self.settings.theme, save=False)
        self.window.fps.blockSignals(True)
        self.window.fps.setCurrentText(str(self.settings.fps))
        self.window.fps.blockSignals(False)
        self.window.close_to_tray.setChecked(self.settings.close_to_tray)
        self.window.overlay_enabled.setChecked(self.settings.overlay_enabled)
        self.update_summary()
        self.apply_logging()
        if previous_language != self.settings.language:
            QMessageBox.information(self.window, self.translator.tr("profiles.import_title"),
                                    self.translator.tr("language.restart_required"))
        else:
            QMessageBox.information(self.window, self.translator.tr("profiles.import_title"),
                                    self.translator.tr("profiles.imported", path=path))

    def export_profile(self):
        path, _ = QFileDialog.getSaveFileName(
            self.window, self.translator.tr("profiles.export_title"),
            "ScreenRec-profile.json", self.translator.tr("profiles.file_filter"),
        )
        if not path:
            return
        try:
            save_profile(Path(path), self.settings)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self.window, self.translator.tr("profiles.error_title"),
                                self.translator.tr("profiles.export_error", error=exc))
            return
        QMessageBox.information(self.window, self.translator.tr("profiles.export_title"),
                                self.translator.tr("profiles.exported", path=path))

    def configure_logging(self):
        from .ui.logging_dialog import LoggingDialog
        dialog = LoggingDialog(self.settings,self.window)
        if dialog.exec():
            self.settings = dialog.result_settings()
            warning = self.apply_logging()
            self.save_settings()
            log.info("Logging configuration applied")
            if warning:
                QMessageBox.warning(self.window,self.translator.tr("logging.title"),warning)

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
        name = name if name in THEMES else "gray"
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
            log.debug("Settings saved")
        except OSError as exc:
            self.error(self.translator.tr("error.save_settings", error=exc))

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
                self.window.monitors.addItem(self.translator.tr("source.monitor_item", index=index, width=monitor["width"], height=monitor["height"], left=monitor["left"], top=monitor["top"]), monitor)
            if not self.window.monitors.count():
                raise RuntimeError(self.translator.tr("error.no_monitors"))
            self.window.status.setText(self.translator.tr("status.ready"))
        except Exception as exc:
            self.window.status.setText(str(exc))
        self.set_busy(False)

    def set_busy(self, busy):
        self.window.recordings.set_recording(busy)
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
        folder = QFileDialog.getExistingDirectory(self.window, self.translator.tr("folder.recordings"), self.settings.output_dir)
        if folder:
            self.settings.output_dir = folder
            self.window.folder.setText(folder)
            self.window.recordings.set_directory(folder)
            self.save_settings()

    def open_folder(self):
        try:
            directory = Path(self.settings.output_dir)
            directory.mkdir(parents=True, exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve()))):
                raise OSError(self.translator.tr("error.open_file_manager"))
        except OSError as exc:
            self.error(str(exc))

    def start_recording(self):
        log.debug("Start recording requested")
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
            self.worker.tab_selected.connect(lambda title: self.window.pairing.setToolTip(self.translator.tr("status.tab_recording") + " " + title))
        else:
            self.worker = RecordingWorker(monitor, self.settings.output_dir, self.settings.fps, self,
                                          settings=replace(self.settings))
        self.worker.recording_started.connect(self.recording_started)
        self.worker.recording_saved.connect(self.recording_saved)
        self.worker.failed.connect(self.error)
        self.worker.finalizing.connect(self.finalizing)
        self.worker.finished.connect(self.worker_finished)
        self.set_busy(True)
        self.window.status.setText(self.translator.tr("status.preparing"))
        self.worker.start()

    def finalizing(self):
        log.info("Finalizing recording")
        self.window.status.setText(self.translator.tr("status.processing"))
        self.window.stop.setEnabled(False)
        self.stop_action.setEnabled(False)

    def recording_started(self, path):
        log.info("Recording started: %s",path)
        self.started_at = time.monotonic()
        self.tray.setToolTip(self.translator.tr("tray.recording"))
        self.notify(self.translator.tr("notify.started"), path)

    def tick(self):
        problem = hub.take_problem()
        if problem:
            self.settings.logging_enabled = False
            self.save_settings()
            QMessageBox.warning(self.window,self.translator.tr("logging.title"),problem)
        if self.stop_deadline and time.monotonic() > self.stop_deadline:
            encoder = self.worker.encoder if self.worker else None
            if encoder:
                encoder.abort()
            self.stop_deadline = None
        if self.started_at is not None and self.worker and not self.worker.stop_event.is_set():
            elapsed = int(time.monotonic() - self.started_at)
            self.window.status.setText(self.translator.tr("status.recording_time", hours=elapsed // 3600, minutes=elapsed // 60 % 60, seconds=elapsed % 60))

    def stop_recording(self):
        log.info("Stop recording requested")
        if self.worker:
            self.worker.stop()
            if self.stop_deadline is None:
                self.stop_deadline = time.monotonic() + 15
            self.window.stop.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.window.status.setText(self.translator.tr("status.finishing"))

    def recording_saved(self, path):
        log.info("Recording saved: %s",path)
        self.window.status.setText(self.translator.tr("status.saved", path=path))
        self.notify(self.translator.tr("notify.saved"), path)
        self.window.recordings.refresh(select=path)

    def worker_finished(self):
        self.worker.wait()
        self.worker.deleteLater()
        self.worker = None
        self.window.pairing.clear()
        self.started_at = None
        self.stop_deadline = None
        self.tray.setToolTip(self.translator.tr("tray.ready"))
        self.set_busy(False)
        if self.exiting:
            self.application.quit()

    def notify(self, title, text):
        if self.settings.notifications and self.tray.isVisible():
            self.tray.showMessage(title, text)

    def error(self, message):
        log.error("Application error: %s",message)
        self.window.status.setText(self.translator.tr("status.error", error=message))
        self.notify(self.translator.tr("error.title"), message)
        if not self.exiting:
            self.show_window()
            QMessageBox.warning(self.window, self.translator.tr("error.title"), message)

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def close_window(self):
        self.window.recordings.leave_fullscreen()
        self.window.recordings.stop_playback()
        log.debug("Window close requested; close_to_tray=%s",self.settings.close_to_tray)
        if self.settings.close_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
            self.window.hide()
            self.notify(self.translator.tr("tray.running"), self.translator.tr("tray.exit_hint"))
        else:
            self.request_exit()

    def request_exit(self, checked=False, *, confirm=True):
        if self.exiting:
            return
        if self.worker and confirm:
            answer = QMessageBox.question(self.window, self.translator.tr("exit.title"),
                self.translator.tr("exit.confirm"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        log.info("Application exit requested")
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
        self.window.recordings.shutdown()
        self.tray.hide()
        log.info("Application cleanup complete")
        close_log()
