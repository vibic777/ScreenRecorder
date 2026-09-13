import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from imageio_ffmpeg import read_frames
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from screenrec.config import templates
from screenrec.config.settings import Settings
from screenrec.recorder.encoder import Encoder
from screenrec.recorder.overlay import render
from screenrec.ui.overlay_editor import OverlayEditor

class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_encoded_image_position_opacity_and_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            image=QImage(40,30,QImage.Format.Format_ARGB32)
            image.fill(QColor("red"))
            path=root/"logo.png"
            self.assertTrue(image.save(str(path)))
            template=templates.default_template()
            template["image"].update(enabled=True,path=str(path),x=.25,y=.25,w=.5,h=.5,opacity=.5)
            template["text"].update(enabled=True,text="Hello",x=.65,y=0,w=.35,h=.2,size=.15)
            for format in ("mp4","mkv","webm"):
                file=root/f"out.{format}"
                encoder=Encoder(file,160,120,15,format,overlay=template)
                for _ in range(5):
                    encoder.write(bytes([0,0,0,255])*160*120)
                encoder.finish()
                reader=read_frames(str(file),pix_fmt="rgb24")
                try:
                    next(reader)
                    pixels=np.frombuffer(next(reader),np.uint8).reshape(120,160,3)
                    self.assertTrue(100<int(pixels[60,80,0])<155)
                    self.assertLess(int(pixels[10,10].max()),10)
                    self.assertTrue(np.any(np.all(pixels[:24,104:]>180,axis=2)))
                finally:
                    reader.close()
            template["image"]["enabled"]=False
            self.assertEqual(render(template,160,120).pixelColor(80,60).alpha(),0)

    def test_literal_text_and_template_roundtrip(self):
        template=templates.default_template()
        template["text"].update(enabled=True,text="Text : '%{x}' [0:v]; Привет",size=.15,x=0,y=0,w=1,h=1)
        picture=render(template,640,360)
        self.assertFalse(picture.isNull())
        self.assertTrue(any(picture.pixelColor(x,y).alpha() for y in range(100) for x in range(640)))
        with tempfile.TemporaryDirectory() as directory, patch.object(Settings,"path",return_value=Path(directory)/"settings.json"):
            templates.save({"Example":template})
            self.assertEqual(templates.load()["Example"],template)
            settings=Settings(overlay=template,overlay_enabled=True)
            settings.save()
            self.assertEqual(Settings.load(),settings)
        validated=templates.validate({"image":{"x":float("nan"),"w":-3,"opacity":8}})
        self.assertEqual(validated["image"]["x"],.72)
        self.assertEqual(validated["image"]["opacity"],1)

    def test_editor_drag_resize_and_cancel(self):
        original=Settings()
        editor=OverlayEditor(original)
        editor.show()
        self.app.processEvents()
        before=dict(editor.template["image"])
        rect=editor.canvas.box("image")
        start=rect.center().toPoint()
        QTest.mousePress(editor.canvas,Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(editor.canvas,start-QPoint(30,20))
        QTest.mouseRelease(editor.canvas,Qt.MouseButton.LeftButton,pos=start-QPoint(30,20))
        self.assertLess(editor.template["image"]["x"],before["x"])
        rect=editor.canvas.box("image")
        start=rect.bottomRight().toPoint()
        width=editor.template["image"]["w"]
        QTest.mousePress(editor.canvas,Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(editor.canvas,start-QPoint(20,10))
        QTest.mouseRelease(editor.canvas,Qt.MouseButton.LeftButton,pos=start-QPoint(20,10))
        self.assertLess(editor.template["image"]["w"],width)
        editor.reject()
        self.assertEqual(original.overlay,templates.default_template())
        editor.deleteLater()
