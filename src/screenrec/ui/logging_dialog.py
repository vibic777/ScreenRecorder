from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QCheckBox,QLineEdit,QPushButton,
    QLabel,QDialogButtonBox,QFileDialog,QMessageBox)
from screenrec.logger.logger import LEVELS,get_default_log_path
from screenrec.localization import Translator

class LoggingDialog(QDialog):
    def __init__(self,settings,parent=None):
        super().__init__(parent)
        self.settings=settings
        self.translator=Translator(settings.language)
        self.setWindowTitle(self.t("logging.title"))
        self.setMinimumWidth(680)
        layout=QVBoxLayout(self)
        self.enabled=QCheckBox(self.t("logging.enable"))
        self.enabled.setChecked(settings.logging_enabled)
        layout.addWidget(self.enabled)
        layout.addWidget(QLabel(self.t("logging.file")))
        row=QHBoxLayout()
        self.path=QLineEdit(settings.log_path or str(get_default_log_path()))
        browse=QPushButton(self.t("logging.choose"))
        row.addWidget(self.path,1)
        row.addWidget(browse)
        layout.addLayout(row)
        row=QHBoxLayout()
        default=QPushButton(self.t("logging.default"))
        open_file=QPushButton(self.t("logging.open_file"))
        open_dir=QPushButton(self.t("logging.open_folder"))
        row.addWidget(default)
        row.addWidget(open_file)
        row.addWidget(open_dir)
        layout.addLayout(row)
        layout.addWidget(QLabel(self.t("logging.levels")))
        row=QHBoxLayout()
        self.levels={}
        for name in LEVELS:
            box=QCheckBox("FATAL ERROR" if name=="FATAL" else name)
            box.setChecked(name in settings.log_levels)
            row.addWidget(box)
            self.levels[name]=box
        layout.addLayout(row)
        note=QLabel("По умолчанию логгер выключен. Настройки применяются сразу после сохранения.\n"
                    "Ротация: 5 МБ на файл, три резервные копии (.1–.3).\n"
                    "Без выбранных уровней события не записываются. FATAL не обходит выключенные галочки.\n"
                    "Токены подключения, содержимое вкладок и текст наложений в лог не выводятся.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.t("common.save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.t("common.cancel"))
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        browse.clicked.connect(self.browse)
        default.clicked.connect(lambda:self.path.setText(str(get_default_log_path())))
        open_file.clicked.connect(lambda:self.open(False))
        open_dir.clicked.connect(lambda:self.open(True))
    def t(self,key):
        return self.translator.tr(key)

    def browse(self):
        path,_=QFileDialog.getSaveFileName(self,self.t("logging.file_title"),self.path.text(),"Логи (*.log);;Все файлы (*)")
        if path:
            self.path.setText(path)
    def open(self,directory):
        path=Path(self.path.text().strip() or get_default_log_path())
        if directory:
            path=path.parent
        if not path.exists():
            QMessageBox.information(self,self.t("logging.title"),self.t("logging.missing"))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
            QMessageBox.warning(self,self.t("logging.title"),self.t("logging.open_error"))
    def result_settings(self):
        path=self.path.text().strip()
        return replace(self.settings,logging_enabled=self.enabled.isChecked(),
                       log_path="" if not path or path==str(get_default_log_path()) else path,
                       log_levels=[key for key,box in self.levels.items() if box.isChecked()])
