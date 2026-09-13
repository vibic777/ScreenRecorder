"""Two draggable/resizable normalized rectangles on a frame mock-up."""
from copy import deepcopy
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QPushButton, QCheckBox, QLineEdit, QPlainTextEdit, QDoubleSpinBox, QFontComboBox,
    QColorDialog, QFileDialog, QDialogButtonBox, QLabel, QMessageBox)
from screenrec.config import templates
from screenrec.recorder.overlay import render, load_image

class Canvas(QWidget):
    changed = Signal()
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setMinimumSize(480,270)
        self.setMouseTracking(True)
        self.drag = None
    def frame(self):
        w = min(self.width(), self.height()*self.editor.aspect)
        h = w/self.editor.aspect
        return QRectF((self.width()-w)/2,(self.height()-h)/2,w,h)
    def box(self, kind):
        r = self.frame()
        d = self.editor.template[kind]
        return QRectF(r.x()+d["x"]*r.width(),r.y()+d["y"]*r.height(),d["w"]*r.width(),d["h"]*r.height())
    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor("#121820"))
        frame=self.frame()
        painter.fillRect(frame,QColor("#344454"))
        painter.setPen(QColor("#a7b5c5"))
        painter.drawText(frame,Qt.AlignmentFlag.AlignCenter,"Макет кадра")
        data=deepcopy(self.editor.template)
        if self.editor.picture is None:
            data["image"]["enabled"]=False
        overlay=render(data,max(1,round(frame.width())),max(1,round(frame.height())),self.editor.picture)
        painter.drawImage(frame,overlay)
        for kind in ("image","text"):
            if not self.editor.template[kind]["enabled"] and self.editor.kind.currentData()!=kind:
                continue
            rect=self.box(kind)
            painter.setPen(QPen(QColor("#5cc9ff" if self.editor.kind.currentData()==kind else "#aab7c4"),2))
            painter.drawRect(rect)
            painter.fillRect(QRectF(rect.right()-5,rect.bottom()-5,10,10),QColor("#5cc9ff"))
        painter.end()
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:
            return
        for kind in (self.editor.kind.currentData(), "text", "image"):
            rect=self.box(kind)
            if rect.adjusted(-7,-7,7,7).contains(event.position()):
                self.editor.kind.setCurrentIndex(self.editor.kind.findData(kind))
                self.anchor=event.position()
                self.original=deepcopy(self.editor.template[kind])
                self.drag="resize" if (event.position()-rect.bottomRight()).manhattanLength()<20 else "move"
                return
    def mouseMoveEvent(self,event):
        if not self.drag:
            return
        r=self.frame()
        dx=(event.position().x()-self.anchor.x())/r.width()
        dy=(event.position().y()-self.anchor.y())/r.height()
        d=self.editor.template[self.editor.kind.currentData()]
        old=self.original
        if self.drag=="move":
            d["x"]=max(0,min(1-d["w"],old["x"]+dx))
            d["y"]=max(0,min(1-d["h"],old["y"]+dy))
        else:
            d["w"]=max(.005,min(1-d["x"],old["w"]+dx))
            d["h"]=max(.005,min(1-d["y"],old["h"]+dy))
        self.editor.sync_geometry()
        self.update()
    def mouseReleaseEvent(self,event):
        self.drag=None

class OverlayEditor(QDialog):
    def __init__(self, settings, parent=None, aspect=16/9):
        super().__init__(parent)
        self.setWindowTitle("Наложения: картинка и текст")
        self.resize(1000,780)
        self.aspect=max(.2,min(5,aspect))
        self.template=templates.validate(settings.overlay)
        self.library=templates.load()
        self.picture=None
        self.loading=False
        root=QVBoxLayout(self)
        row=QHBoxLayout()
        self.names=QComboBox()
        self.names.setEditable(True)
        self.names.addItems(sorted(self.library))
        self.names.setCurrentText(settings.overlay_name or "Мой шаблон")
        row.addWidget(QLabel("Шаблон:"))
        row.addWidget(self.names,1)
        load=QPushButton("Загрузить")
        save=QPushButton("Сохранить шаблон")
        row.addWidget(load)
        row.addWidget(save)
        root.addLayout(row)
        root.addWidget(QLabel("Макет кадра: перемещайте прямоугольник мышью, меняйте размер за нижний правый угол."))
        self.canvas=Canvas(self)
        root.addWidget(self.canvas,1)
        row=QHBoxLayout()
        self.kind=QComboBox()
        self.kind.addItem("Картинка","image")
        self.kind.addItem("Текст","text")
        self.enabled=QCheckBox("Показывать этот элемент")
        row.addWidget(self.kind)
        row.addWidget(self.enabled)
        root.addLayout(row)
        row=QHBoxLayout()
        self.geometry={}
        for key,label in (("x","X, %"),("y","Y, %"),("w","Ширина, %"),("h","Высота, %"),("opacity","Непрозрачность, %")):
            row.addWidget(QLabel(label))
            box=QDoubleSpinBox()
            box.setRange(.5 if key in ("w","h") else 0,100)
            box.setDecimals(1)
            self.geometry[key]=box
            row.addWidget(box)
            box.valueChanged.connect(self.update_layer)
        root.addLayout(row)
        self.image_panel=QWidget()
        row=QHBoxLayout(self.image_panel)
        self.image_path=QLineEdit()
        self.image_path.setReadOnly(True)
        browse=QPushButton("Выбрать картинку…")
        row.addWidget(self.image_path,1)
        row.addWidget(browse)
        root.addWidget(self.image_panel)
        self.text_panel=QWidget()
        form=QFormLayout(self.text_panel)
        self.text=QPlainTextEdit()
        self.text.setMaximumHeight(70)
        self.font=QFontComboBox()
        self.size=QDoubleSpinBox()
        self.size.setRange(.5,100)
        self.size.setSuffix(" % высоты кадра")
        self.color=QPushButton("Цвет текста…")
        form.addRow("Текст:",self.text)
        row=QHBoxLayout()
        row.addWidget(self.font,1)
        row.addWidget(self.size)
        row.addWidget(self.color)
        form.addRow("Шрифт:",row)
        root.addWidget(self.text_panel)
        self.note=QLabel()
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Применить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        root.addWidget(buttons)
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        self.kind.currentIndexChanged.connect(self.populate)
        self.enabled.toggled.connect(self.update_layer)
        self.text.textChanged.connect(self.update_layer)
        self.font.currentFontChanged.connect(self.update_layer)
        self.size.valueChanged.connect(self.update_layer)
        browse.clicked.connect(self.browse)
        self.color.clicked.connect(self.choose_color)
        load.clicked.connect(self.load_template)
        save.clicked.connect(self.save_template)
        self.refresh_picture()
        self.populate()
    def refresh_picture(self):
        self.picture=None
        path=self.template["image"]["path"]
        if path:
            try:
                self.picture=load_image(path)
                self.note.setText("")
            except Exception as exc:
                self.note.setText(str(exc))
    def sync_geometry(self):
        self.loading=True
        for key,box in self.geometry.items():
            box.setValue(self.template[self.kind.currentData()][key]*100)
        self.loading=False
    def populate(self,*_):
        self.loading=True
        kind=self.kind.currentData()
        d=self.template[kind]
        self.enabled.setChecked(d["enabled"])
        self.image_panel.setVisible(kind=="image")
        self.text_panel.setVisible(kind=="text")
        self.image_path.setText(self.template["image"]["path"])
        text=self.template["text"]
        self.text.setPlainText(text["text"])
        from PySide6.QtGui import QFont
        self.font.setCurrentFont(QFont(text["font"]))
        self.size.setValue(text["size"]*100)
        self.loading=False
        self.sync_geometry()
        self.canvas.update()
    def update_layer(self,*_):
        if self.loading:
            return
        kind=self.kind.currentData()
        d=self.template[kind]
        d["enabled"]=self.enabled.isChecked()
        for key,box in self.geometry.items():
            d[key]=box.value()/100
        if kind=="text":
            d["text"]=self.text.toPlainText()[:4000]
            d["font"]=self.font.currentFont().family()
            d["size"]=self.size.value()/100
        self.template=templates.validate(self.template)
        self.sync_geometry()
        self.canvas.update()
    def browse(self):
        path,_=QFileDialog.getOpenFileName(self,"Картинка","","Изображения (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            try:
                image=load_image(path)
                self.picture=image
                self.template["image"]["path"]=path
                self.template["image"]["enabled"]=True
                self.note.setText("")
                self.populate()
            except Exception as exc:
                QMessageBox.warning(self,"Картинка",str(exc))
    def choose_color(self):
        color=QColorDialog.getColor(QColor(self.template["text"]["color"]),self,"Цвет текста")
        if color.isValid():
            self.template["text"]["color"]=color.name()
            self.canvas.update()
    def load_template(self):
        name=self.names.currentText().strip()
        if name in self.library:
            self.template=deepcopy(self.library[name])
            self.refresh_picture()
            self.populate()
        else:
            self.note.setText("Шаблон с таким именем не найден.")
    def save_template(self):
        name=self.names.currentText().strip()
        if not name:
            self.note.setText("Укажите имя шаблона.")
            return
        if not self.valid():
            return
        self.library[name]=deepcopy(self.template)
        try:
            templates.save(self.library)
            if self.names.findText(name)<0:
                self.names.addItem(name)
            self.note.setText("Шаблон сохранён. «Применить» выбирает его для записи.")
        except OSError as exc:
            QMessageBox.warning(self,"Шаблон",str(exc))
    def valid(self):
        if self.template["image"]["enabled"]:
            try:
                load_image(self.template["image"]["path"])
            except Exception as exc:
                QMessageBox.warning(self,"Картинка",str(exc))
                return False
        return True
    def apply(self):
        if self.valid():
            self.accept()
