from dataclasses import replace
from datetime import datetime
from PySide6.QtWidgets import (QDialog,QFormLayout,QLineEdit,QCheckBox,QComboBox,QLabel,
                              QDialogButtonBox,QPushButton)
from screenrec.config.filenames import DATE_FORMATS,TIME_FORMATS,filename,clean_prefix
from screenrec.localization import Translator

class FilenameDialog(QDialog):
    def __init__(self,settings,parent=None):
        super().__init__(parent)
        self.settings=settings
        self.translator=Translator(settings.language)
        self.moment=datetime.now()
        self.setWindowTitle(self.t("filename.title"))
        self.setMinimumWidth(650)
        form=QFormLayout(self)
        self.prefix=QLineEdit(settings.filename_prefix)
        self.prefix.setMaxLength(80)
        self.date=QCheckBox(self.t("filename.add_date"))
        self.date.setChecked(settings.filename_date)
        self.time=QCheckBox(self.t("filename.add_time"))
        self.time.setChecked(settings.filename_time)
        self.uuid=QCheckBox(self.t("filename.add_uuid"))
        self.uuid.setChecked(settings.filename_uuid)
        self.prefix.setToolTip(self.t("tip.filename_prefix"))
        self.date.setToolTip(self.t("tip.filename_date"))
        self.time.setToolTip(self.t("tip.filename_time"))
        self.uuid.setToolTip(self.t("tip.filename_uuid"))
        self.date_format=QComboBox()
        for key,(label,_) in DATE_FORMATS.items():
            self.date_format.addItem(label,key)
        self.date_format.setCurrentIndex(max(0,self.date_format.findData(settings.filename_date_format)))
        self.time_format=QComboBox()
        for key,label in TIME_FORMATS.items():
            self.time_format.addItem(label,key)
        self.time_format.setCurrentIndex(max(0,self.time_format.findData(settings.filename_time_format)))
        form.addRow(self.t("filename.prefix"),self.prefix)
        form.addRow(self.date)
        form.addRow(self.t("filename.date_format"),self.date_format)
        form.addRow(self.time)
        form.addRow(self.t("filename.time_format"),self.time_format)
        form.addRow(self.uuid)
        self.preview=QLineEdit()
        self.preview.setReadOnly(True)
        form.addRow(self.t("filename.preview"),self.preview)
        self.note=QLabel()
        self.note.setWordWrap(True)
        form.addRow(self.note)
        hint=QLabel(self.t("filename.note_order") + "\\n" + self.t("filename.note_collision") + "\\n" + self.t("filename.note_empty"))
        hint.setWordWrap(True)
        form.addRow(hint)
        reset=QPushButton(self.t("common.defaults"))
        form.addRow(reset)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.t("common.save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.t("common.cancel"))
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
    def t(self,key):
        return self.translator.tr(key)

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
        self.note.setText(self.t("filename.note_sanitized").format(prefix=safe or self.t("filename.empty")) if safe!=self.prefix.text() else
                         (self.t("filename.note_uuid_example") if self.uuid.isChecked() else self.t("filename.note_uuid_disabled")))
    def defaults(self):
        self.prefix.setText("ScreenRec")
        for box in (self.date,self.time,self.uuid):
            box.setChecked(True)
        self.date_format.setCurrentIndex(self.date_format.findData("ymd"))
        self.time_format.setCurrentIndex(self.time_format.findData("24h"))
