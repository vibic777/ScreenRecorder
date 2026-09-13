from dataclasses import replace
from PySide6.QtWidgets import (QDialog, QFormLayout, QComboBox, QDialogButtonBox,
                              QLabel, QPushButton)
from screenrec.config.recording import FORMATS, QUALITIES, AUDIO_MODES
from screenrec.recorder.audio import devices


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Конфигуратор записи")
        self.setMinimumWidth(510)
        form = QFormLayout(self)
        self.file_format = self.combo(FORMATS, settings.file_format)
        self.quality = self.combo(QUALITIES, settings.quality)
        self.fps = self.combo({i: str(i) for i in (15, 24, 30, 60)}, settings.fps)
        self.audio_mode = self.combo(AUDIO_MODES, settings.audio_mode)
        self.microphone = QComboBox()
        self.system_device = QComboBox()
        self.bitrate = self.combo({i: f"{i} кбит/с" for i in (96, 128, 192, 256, 320)}, settings.audio_bitrate)
        form.addRow("Формат файла", self.file_format)
        form.addRow("Качество видео", self.quality)
        form.addRow("Кадров в секунду", self.fps)
        form.addRow("Запись звука", self.audio_mode)
        form.addRow("Микрофон", self.microphone)
        form.addRow("Источник системного звука", self.system_device)
        form.addRow("Качество звука", self.bitrate)
        self.refresh = QPushButton("Обновить аудиоустройства")
        form.addRow(self.refresh)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form.addRow(self.message)
        note = QLabel("Высокое качество увеличивает размер файла. WebM может сильнее нагружать процессор.\n"
                      "Настройки применяются к следующей записи. Без звука — аудиоустройства не используются.")
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.refresh.clicked.connect(self.refresh_devices)
        self.audio_mode.currentIndexChanged.connect(self.update_audio)
        self.fill_devices([], settings.microphone_id, settings.system_device_id)
        self.update_audio()

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
            box.addItem("Устройство по умолчанию", "")
            for device_id, name, is_loopback in items:
                if is_loopback == loopback:
                    box.addItem(name, device_id)
            if selected and box.findData(selected) < 0:
                box.addItem(f"Сохранённое устройство (обновите список): {selected}", selected)
            box.setCurrentIndex(max(0, box.findData(selected)))

    def refresh_devices(self):
        try:
            items = devices()
            self.fill_devices(items, self.microphone.currentData(), self.system_device.currentData())
            self.message.setText("Список устройств обновлён." if items else "Аудиоустройства не найдены.")
        except Exception as exc:
            self.message.setText(f"Не удалось получить аудиоустройства: {exc}")

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
                       audio_bitrate=self.bitrate.currentData())
