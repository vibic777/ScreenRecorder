from dataclasses import replace
from screenrec.qt.QtWidgets import (QDialog, QFormLayout, QComboBox, QDialogButtonBox,
                              QLabel, QPushButton, QCheckBox)
from screenrec.config.recording import FORMATS, QUALITIES, AUDIO_MODES
from screenrec.recorder.audio import devices
from screenrec.localization import Translator


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.translator = Translator(settings.language)
        self.setWindowTitle(self.t("settings.dialog.title"))
        self.setMinimumWidth(510)
        form = QFormLayout(self)
        self.file_format = self.combo(FORMATS, settings.file_format)
        self.quality = self.combo({key: self.t(f"settings.quality.{key}") for key in QUALITIES}, settings.quality)
        self.fps = self.combo({i: str(i) for i in (15, 24, 30, 60)}, settings.fps)
        self.audio_mode = self.combo({key: self.t(f"settings.audio_mode.{key}") for key in AUDIO_MODES}, settings.audio_mode)
        self.microphone = QComboBox()
        self.system_device = QComboBox()
        self.bitrate = self.combo({i: self.t("settings.bitrate").format(value=i) for i in (96, 128, 192, 256, 320)}, settings.audio_bitrate)
        self.allow_multiple_instances = QCheckBox(self.t("app.allow_multiple"))
        self.allow_multiple_instances.setChecked(settings.allow_multiple_instances)
        self.allow_multiple_instances.setToolTip(self.t("tip.allow_multiple"))
        form.addRow(self.t("settings.format"), self.file_format)
        form.addRow(self.t("settings.video_quality"), self.quality)
        form.addRow(self.t("settings.fps"), self.fps)
        form.addRow(self.t("settings.audio"), self.audio_mode)
        form.addRow(self.t("settings.microphone"), self.microphone)
        form.addRow(self.t("settings.system_audio"), self.system_device)
        form.addRow(self.t("settings.audio_quality"), self.bitrate)
        form.addRow(self.t("settings.single_instance"), self.allow_multiple_instances)
        filename_button = QPushButton(self.t("settings.filename"))
        filename_button.clicked.connect(self.configure_filename)
        form.addRow(filename_button)
        self.refresh = QPushButton(self.t("settings.refresh_audio"))
        form.addRow(self.refresh)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form.addRow(self.message)
        note = QLabel(self.t("settings.note_quality") + "\n" + self.t("settings.note_audio"))
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.t("common.save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.t("common.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.refresh.clicked.connect(self.refresh_devices)
        self.audio_mode.currentIndexChanged.connect(self.update_audio)
        self.fill_devices([], settings.microphone_id, settings.system_device_id)
        self.file_format.setToolTip(self.t("tip.format"))
        self.quality.setToolTip(self.t("tip.video_quality"))
        self.fps.setToolTip(self.t("tip.fps"))
        self.audio_mode.setToolTip(self.t("tip.audio_mode"))
        self.microphone.setToolTip(self.t("tip.microphone"))
        self.system_device.setToolTip(self.t("tip.system_audio"))
        self.bitrate.setToolTip(self.t("tip.audio_bitrate"))
        self.update_audio()

    def t(self,key):
        return self.translator.tr(key)

    def configure_filename(self):
        from .filename_dialog import FilenameDialog
        dialog = FilenameDialog(replace(self.settings, file_format=self.file_format.currentData()), self)
        if dialog.exec():
            self.settings = dialog.result_settings()

    @staticmethod
    def combo(options, value):
        box = QComboBox()
        for key, label in options.items():
            box.addItem(label, key)
        box.setCurrentIndex(max(0, box.findData(value)))
        return box

    def fill_devices(self, items, mic_id, system_id):
        for box, selected, loopback in ((self.microphone, mic_id, False), (self.system_device, system_id, True)):
            box.clear()
            box.addItem(self.t("settings.default_device"), "")
            for device_id, name, is_loopback in items:
                if is_loopback == loopback:
                    box.addItem(name, device_id)
            if selected and box.findData(selected) < 0:
                box.addItem(self.t("settings.saved_device").format(id=selected), selected)
            box.setCurrentIndex(max(0, box.findData(selected)))

    def refresh_devices(self):
        try:
            items = devices()
            self.fill_devices(items, self.microphone.currentData(), self.system_device.currentData())
            self.message.setText(self.t("settings.devices_updated") if items else self.t("settings.devices_none"))
        except Exception as exc:
            self.message.setText(self.t("settings.devices_error").format(error=exc))

    def update_audio(self):
        mode = self.audio_mode.currentData()
        self.microphone.setEnabled(mode in ("microphone", "both"))
        self.system_device.setEnabled(mode in ("system", "both"))
        self.bitrate.setEnabled(mode != "none")
        self.refresh.setEnabled(mode != "none")

    def result_settings(self):
        return replace(self.settings, file_format=self.file_format.currentData(), quality=self.quality.currentData(),
                       fps=self.fps.currentData(), audio_mode=self.audio_mode.currentData(),
                       microphone_id=self.microphone.currentData(), system_device_id=self.system_device.currentData(),
                       audio_bitrate=self.bitrate.currentData(), allow_multiple_instances=self.allow_multiple_instances.isChecked())

