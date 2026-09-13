import json
import shutil
from pathlib import Path
from datetime import datetime
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog, QMessageBox
from .region_selector import RegionSelector


class SourceController:
    def initialize_sources(self):
        self.window.source_mode.currentIndexChanged.connect(self.source_changed)
        self.window.window_list.currentIndexChanged.connect(lambda _: self.set_busy(bool(self.worker)))
        self.window.select_region.clicked.connect(self.choose_region)
        self.window.copy_pairing.clicked.connect(lambda: self.application.clipboard().setText(self.window.pairing.text()))
        self.window.export_extension.clicked.connect(self.export_extension)
        self.source_changed(save=False)

    def current_source(self):
        mode = self.window.source_mode.currentData()
        if mode == "tab":
            return {"kind":"tab"}
        if mode == "window":
            return self.window.window_list.currentData()
        if mode == "region":
            region = self.settings.region
            if all(type(region.get(key)) is int for key in ("left","top","width","height")) and region["width"] >= 2 and region["height"] >= 2:
                return {**region, "kind":"region"}
            return None
        return self.window.monitors.currentData()

    def source_changed(self, *_, save=True):
        mode = self.window.source_mode.currentData()
        self.settings.source_mode = mode
        self.window.monitors.setVisible(mode in ("monitor","region"))
        self.window.window_list.setVisible(mode == "window")
        self.window.select_region.setVisible(mode == "region")
        self.window.region_info.setVisible(mode == "region")
        self.window.tab_panel.setVisible(mode == "tab")
        self.window.refresh.setVisible(mode != "tab")
        if mode == "window":
            self.refresh_windows()
        self.window.region_info.setText(self.region_description())
        self.set_busy(bool(self.worker))
        if save:
            self.save_settings()

    def region_description(self):
        region = self.settings.region
        if self.current_source() and self.settings.source_mode == "region":
            return f"Область: {region['width']} × {region['height']} — X={region['left']}, Y={region['top']}"
        return "Область ещё не выбрана."

    def refresh_sources(self):
        if self.window.source_mode.currentData() == "window":
            self.refresh_windows()
        else:
            self.refresh_monitors()

    def refresh_windows(self):
        from screenrec.recorder.window import windows
        self.window.window_list.clear()
        try:
            for item in windows():
                self.window.window_list.addItem(f"{item['title']}  (PID {item['pid']})", item)
            if not self.window.window_list.count():
                self.window.status.setText("Подходящие окна не найдены. Откройте нужную программу и обновите список.")
        except Exception as exc:
            self.window.status.setText(str(exc))
        self.set_busy(bool(self.worker))

    def choose_region(self):
        if self.worker:
            return
        monitor = self.window.monitors.currentData()
        if not monitor:
            return
        from .region_selector import screen_for_monitor
        try:
            screen = screen_for_monitor(monitor, self.window.monitors.currentIndex())
            dialog = RegionSelector(screen, monitor, self.settings.region)
            if dialog.exec():
                self.settings.region = dialog.selected_region()
                self.window.region_info.setText(self.region_description())
                self.save_settings()
                self.set_busy(False)
        except Exception as exc:
            self.error(str(exc))

    def show_pairing(self, code):
        self.window.pairing.setText(code)
        self.window.status.setText("Ожидание вкладки: скопируйте код и подключите нужную вкладку через расширение.")

    def export_extension(self):
        directory = QFileDialog.getExistingDirectory(self.window, "Куда сохранить локальное расширение")
        if not directory:
            return
        try:
            source = Path(__file__).resolve().parents[1] / "browser_extension"
            target = Path(directory) / "ScreenRec-extension-0.3.0"
            if target.exists():
                target = target.with_name(target.name + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            shutil.copytree(source, target)
            QMessageBox.information(self.window, "Расширение сохранено",
                f"Папка: {target}\n\nОткройте chrome://extensions или edge://extensions. "
                "Включите режим разработчика, нажмите «Загрузить распакованное» и выберите эту папку.\n"
                "Затем начните сеанс вкладки в ScreenRec, скопируйте код и нажмите значок расширения в нужной вкладке.")
        except OSError as exc:
            self.error(str(exc))
