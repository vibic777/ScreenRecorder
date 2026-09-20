"""Two draggable/resizable normalized rectangles on a frame mock-up."""
from copy import deepcopy
from screenrec.qt.QtCore import Qt, QRectF, QPointF, Signal
from screenrec.qt.QtGui import QPainter, QColor, QPen
from screenrec.qt.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QPushButton, QCheckBox, QLineEdit, QPlainTextEdit, QDoubleSpinBox, QFontComboBox,
    QColorDialog, QFileDialog, QDialogButtonBox, QLabel, QMessageBox)
from screenrec.config import templates
from screenrec.localization import Translator
from screenrec.recorder.overlay import render, load_image
from screenrec.logger.logger import get_logger

log = get_logger(__name__)

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
        # The selected text must remain visible while editing even if its
        # recording checkbox is off; the outline still indicates its bounds.
        data=deepcopy(self.editor.template)
        if self.editor.kind.currentData() == "text" and data["text"]["text"].strip():
            data["text"]["enabled"] = True
        if self.editor.picture is None:
            data["image"]["enabled"]=False
        try:
            overlay=render(data,max(1,round(frame.width())),max(1,round(frame.height())),self.editor.picture)
        except Exception:
            log.exception("Overlay preview rendering failed")
            painter.end()
            return
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
        point=event.position() if hasattr(event,"position") else QPointF(event.pos())
        for kind in (self.editor.kind.currentData(), "text", "image"):
            rect=self.box(kind)
            if rect.adjusted(-7,-7,7,7).contains(point):
                self.editor.kind.setCurrentIndex(self.editor.kind.findData(kind))
                self.anchor=point
                self.original=deepcopy(self.editor.template[kind])
                self.drag="resize" if (point-rect.bottomRight()).manhattanLength()<20 else "move"
                return
    def mouseMoveEvent(self,event):
        if not self.drag:
            return
        r=self.frame()
        point=event.position() if hasattr(event,"position") else QPointF(event.pos())
        dx=(point.x()-self.anchor.x())/r.width()
        dy=(point.y()-self.anchor.y())/r.height()
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
        self.translator = Translator(settings.language)
        self.setWindowTitle(self.t("overlay.title"))
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
        self.names.setCurrentText(settings.overlay_name or self.t("overlay.my_template"))
        row.addWidget(QLabel(self.t("overlay.template")))
        row.addWidget(self.names,1)
        load=QPushButton(self.t("overlay.load"))
        save=QPushButton(self.t("overlay.save_template"))
        row.addWidget(load)
        row.addWidget(save)
        root.addLayout(row)
        root.addWidget(QLabel(self.t("overlay.canvas_hint")))
        self.canvas=Canvas(self)
        root.addWidget(self.canvas,1)
        row=QHBoxLayout()
        self.kind=QComboBox()
        self.kind.addItem(self.t("overlay.image"),"image")
        self.kind.addItem(self.t("overlay.text"),"text")
        self.enabled=QCheckBox(self.t("overlay.show"))
        self.kind.setToolTip(self.t("tip.overlay_kind"))
        self.enabled.setToolTip(self.t("tip.overlay_element"))
        row.addWidget(self.kind)
        row.addWidget(self.enabled)
        root.addLayout(row)
        row=QHBoxLayout()
        self.geometry={}
        for key,label in (("x",self.t("overlay.x")),("y",self.t("overlay.y")),("w",self.t("overlay.width")),("h",self.t("overlay.height")),("opacity",self.t("overlay.opacity"))):
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
        browse=QPushButton(self.t("overlay.choose_image"))
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
        self.size.setSuffix(self.t("overlay.frame_height"))
        self.size.setToolTip(self.t("tip.overlay_size"))
        self.color=QPushButton(self.t("overlay.text_color"))
        form.addRow(self.t("overlay.text_label"),self.text)
        row=QHBoxLayout()
        row.addWidget(self.font,1)
        row.addWidget(self.size)
        row.addWidget(self.color)
        form.addRow(self.t("overlay.font"),row)
        root.addWidget(self.text_panel)
        self.note=QLabel()
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.t("common.apply"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.t("common.cancel"))
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
    def t(self, key):
        return self.translator.tr(key)

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
        from screenrec.qt.QtGui import QFont
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
        path,_=QFileDialog.getOpenFileName(self,self.t("overlay.choose_image_title"),"",self.t("overlay.image_filter"))
        if path:
            try:
                image=load_image(path)
                self.picture=image
                self.template["image"]["path"]=path
                self.template["image"]["enabled"]=True
                self.note.setText("")
                self.populate()
            except Exception as exc:
                QMessageBox.warning(self,self.t("overlay.image"),str(exc))
    def choose_color(self):
        color=QColorDialog.getColor(QColor(self.template["text"]["color"]),self,self.t("overlay.text_color_title"))
        if color.isValid():
            self.template["text"]["color"]=color.name()
            log.info("Overlay text color changed: %s", color.name())
            self.canvas.update()
    def load_template(self):
        name=self.names.currentText().strip()
        if name in self.library:
            self.template=deepcopy(self.library[name])
            self.refresh_picture()
            self.populate()
        else:
            self.note.setText(self.t("overlay.not_found"))
    def save_template(self):
        name=self.names.currentText().strip()
        if not name:
            self.note.setText(self.t("overlay.name_required"))
            return
        if not self.valid():
            return
        self.library[name]=deepcopy(self.template)
        try:
            templates.save(self.library)
            if self.names.findText(name)<0:
                self.names.addItem(name)
            self.note.setText(self.t("overlay.saved"))
        except OSError as exc:
            QMessageBox.warning(self,self.t("overlay.template"),str(exc))
    def valid(self):
        if self.template["image"]["enabled"]:
            try:
                load_image(self.template["image"]["path"])
            except Exception as exc:
                QMessageBox.warning(self,self.t("overlay.image"),str(exc))
                return False
        return True
    def apply(self):
        # Entering text is an explicit request to show the text layer. This
        # also prevents old templates with a stale disabled flag from silently
        # recording without the text the user just configured.
        if self.template["text"]["text"].strip():
            self.template["text"]["enabled"] = True
        if self.valid():
            log.info("Overlay editor applying: image=%s text=%s text_color=%s",
                     self.template["image"]["enabled"], self.template["text"]["enabled"],
                     self.template["text"]["color"])
            self.accept()
