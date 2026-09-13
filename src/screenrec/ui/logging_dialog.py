from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QCheckBox,QLineEdit,QPushButton,
    QLabel,QDialogButtonBox,QFileDialog,QMessageBox)
from screenrec.logger.logger import LEVELS,get_default_log_path

class LoggingDialog(QDialog):
    def __init__(self,settings,parent=None):
        super().__init__(parent)
        self.settings=settings
        self.setWindowTitle("Логирование")
        self.setMinimumWidth(680)
        layout=QVBoxLayout(self)
        self.enabled=QCheckBox("Включить логирование")
        self.enabled.setChecked(settings.logging_enabled)
        layout.addWidget(self.enabled)
        layout.addWidget(QLabel("Файл лога (по умолчанию рядом с EXE):"))
        row=QHBoxLayout()
        self.path=QLineEdit(settings.log_path or str(get_default_log_path()))
        browse=QPushButton("Выбрать файл…")
        row.addWidget(self.path,1)
        row.addWidget(browse)
        layout.addLayout(row)
        row=QHBoxLayout()
        default=QPushButton("Путь по умолчанию")
        open_file=QPushButton("Открыть лог")
        open_dir=QPushButton("Открыть папку")
        row.addWidget(default)
        row.addWidget(open_file)
        row.addWidget(open_dir)
        layout.addLayout(row)
        layout.addWidget(QLabel("Уровни включаются независимо (не минимальный порог):"))
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
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        browse.clicked.connect(self.browse)
        default.clicked.connect(lambda:self.path.setText(str(get_default_log_path())))
        open_file.clicked.connect(lambda:self.open(False))
        open_dir.clicked.connect(lambda:self.open(True))
    def browse(self):
        path,_=QFileDialog.getSaveFileName(self,"Файл лога",self.path.text(),"Логи (*.log);;Все файлы (*)")
        if path:
            self.path.setText(path)
    def open(self,directory):
        path=Path(self.path.text().strip() or get_default_log_path())
        if directory:
            path=path.parent
        if not path.exists():
            QMessageBox.information(self,"Логирование","Файл или папка ещё не существует.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
            QMessageBox.warning(self,"Логирование","Не удалось открыть выбранный путь.")
    def result_settings(self):
        path=self.path.text().strip()
        return replace(self.settings,logging_enabled=self.enabled.isChecked(),
                       log_path="" if not path or path==str(get_default_log_path()) else path,
                       log_levels=[key for key,box in self.levels.items() if box.isChecked()])
