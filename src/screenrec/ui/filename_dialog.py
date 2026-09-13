from dataclasses import replace
from datetime import datetime
from PySide6.QtWidgets import (QDialog,QFormLayout,QLineEdit,QCheckBox,QComboBox,QLabel,
                              QDialogButtonBox,QPushButton)
from screenrec.config.filenames import DATE_FORMATS,TIME_FORMATS,filename,clean_prefix

class FilenameDialog(QDialog):
    def __init__(self,settings,parent=None):
        super().__init__(parent)
        self.settings=settings
        self.moment=datetime.now()
        self.setWindowTitle("Имя файла записи")
        self.setMinimumWidth(650)
        form=QFormLayout(self)
        self.prefix=QLineEdit(settings.filename_prefix)
        self.prefix.setMaxLength(80)
        self.date=QCheckBox("Добавлять дату")
        self.date.setChecked(settings.filename_date)
        self.time=QCheckBox("Добавлять время")
        self.time.setChecked(settings.filename_time)
        self.uuid=QCheckBox("Добавлять UUID")
        self.uuid.setChecked(settings.filename_uuid)
        self.date_format=QComboBox()
        for key,(label,_) in DATE_FORMATS.items():
            self.date_format.addItem(label,key)
        self.date_format.setCurrentIndex(max(0,self.date_format.findData(settings.filename_date_format)))
        self.time_format=QComboBox()
        for key,label in TIME_FORMATS.items():
            self.time_format.addItem(label,key)
        self.time_format.setCurrentIndex(max(0,self.time_format.findData(settings.filename_time_format)))
        form.addRow("Префикс",self.prefix)
        form.addRow(self.date)
        form.addRow("Формат даты",self.date_format)
        form.addRow(self.time)
        form.addRow("Формат времени",self.time_format)
        form.addRow(self.uuid)
        self.preview=QLineEdit()
        self.preview.setReadOnly(True)
        form.addRow("Пример имени",self.preview)
        self.note=QLabel()
        self.note.setWordWrap(True)
        form.addRow(self.note)
        hint=QLabel("Порядок: префикс → дата → время → UUID. Дата и время — местные, на момент начала подготовки записи.\n"
                    "При совпадении добавляется _2, _3… Старые файлы не перезаписываются.\n"
                    "Если префикс пуст и все галочки сняты, используется ScreenRec.")
        hint.setWordWrap(True)
        form.addRow(hint)
        reset=QPushButton("По умолчанию")
        form.addRow(reset)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        form.addRow(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        reset.clicked.connect(self.defaults)
        self.prefix.textChanged.connect(self.update_preview)
        for box in (self.date,self.time,self.uuid):
            box.toggled.connect(self.update_preview)
        self.date_format.currentIndexChanged.connect(self.update_preview)
        self.time_format.currentIndexChanged.connect(self.update_preview)
        self.update_preview()
    def result_settings(self):
        return replace(self.settings,filename_prefix=clean_prefix(self.prefix.text()),
                       filename_date=self.date.isChecked(),filename_time=self.time.isChecked(),
                       filename_uuid=self.uuid.isChecked(),filename_date_format=self.date_format.currentData(),
                       filename_time_format=self.time_format.currentData())
    def update_preview(self,*_):
        self.date_format.setEnabled(self.date.isChecked())
        self.time_format.setEnabled(self.time.isChecked())
        self.preview.setText(filename(self.result_settings(),self.moment,"12345678-1234-4123-8123-123456789abc"))
        safe=clean_prefix(self.prefix.text())
        self.note.setText("Недопустимые символы заменены; префикс: " + (safe or "(пусто)") if safe!=self.prefix.text() else
                         ("UUID в примере условный; при каждой записи создаётся новый." if self.uuid.isChecked() else "UUID отключён; совпадения имён разрешаются числовым суффиксом."))
    def defaults(self):
        self.prefix.setText("ScreenRec")
        for box in (self.date,self.time,self.uuid):
            box.setChecked(True)
        self.date_format.setCurrentIndex(self.date_format.findData("ymd"))
        self.time_format.setCurrentIndex(self.time_format.findData("24h"))
