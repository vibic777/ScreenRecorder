import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from screenrec.config.settings import Settings
from screenrec.recorder.browser_tab import TabSession, BrowserWorker
from screenrec.recorder.encoder import Encoder
from screenrec.ui.region_selector import physical_region


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_region_dpi_negative_monitor_and_clamp(self):
        monitor = {"left":-1920, "top":-200, "width":1920, "height":1080}
        region = physical_region(QRect(100,50,400,300), 1280,720,monitor)
        self.assertEqual(region, {"kind":"region","left":-1770,"top":-125,"width":600,"height":450})
        self.assertRaises(ValueError, physical_region, QRect(0,0,1,1), 1920,1080,monitor)
        region = physical_region(QRect(1200,600,500,500),1280,720,monitor)
        self.assertEqual(region["width"],120)
        self.assertEqual(region["height"],180)

    def request(self, session, route, body=None, token=None, origin="chrome-extension://test"):
        request = urllib.request.Request(f"http://127.0.0.1:{session.server.server_port}"+route, data=body,
             headers={"X-ScreenRec-Token":session.token if token is None else token,"Origin":origin})
        return urllib.request.urlopen(request,timeout=3).read()

    def test_bridge_auth_order_retry_and_end(self):
        with tempfile.TemporaryDirectory() as directory:
            session = TabSession(Path(directory)/"video.webm", Settings())
            try:
                session.ready=True
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.request(session,"/config",token="wrong")
                self.assertEqual(error.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError):
                    self.request(session,"/config",origin="https://example.com")
                self.request(session,"/begin",b'{"title":"Test"}')
                self.request(session,"/chunk?seq=0",b"header")
                self.request(session,"/chunk?seq=0",b"header")
                with self.assertRaises(urllib.error.HTTPError):
                    self.request(session,"/chunk?seq=2",b"invalid")
                self.request(session,"/chunk?seq=1",b"tail")
                self.request(session,"/end",b"{}")
                self.assertTrue(session.ended.is_set())
                self.assertEqual(session.sequence,2)
            finally:
                session.close()
            self.assertEqual((Path(directory)/"video.webm").read_bytes(),b"headertail")

    def test_browser_worker_complete_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory)/"input.webm"
            encoder = Encoder(input_file,64,48,15,"webm","balanced")
            for _ in range(15):
                encoder.write(bytes([20,80,140,255])*64*48)
            encoder.finish()
            from PySide6.QtGui import QImage, QColor
            from screenrec.config.templates import default_template
            logo = QImage(32,24,QImage.Format.Format_ARGB32)
            logo.fill(QColor("red"))
            logo_path = Path(directory)/"logo.png"
            logo.save(str(logo_path))
            overlay = default_template()
            overlay["image"].update(enabled=True,path=str(logo_path),x=.25,y=.25,w=.5,h=.5)
            worker = BrowserWorker(Settings(output_dir=directory, audio_mode="none",overlay_enabled=True,overlay=overlay,filename_prefix="TabTest",filename_date=False,filename_time=False,filename_uuid=False))
            errors,saved = [],[]
            worker.failed.connect(errors.append)
            worker.recording_saved.connect(saved.append)
            worker.start()
            deadline=time.monotonic()+15
            try:
                while worker.session is None and time.monotonic()<deadline:
                    self.qt.processEvents()
                    time.sleep(.02)
                self.assertIsNotNone(worker.session)
                session=worker.session
                self.request(session,"/begin",b'{"title":"Pinned tab"}')
                self.request(session,"/chunk?seq=0",input_file.read_bytes())
                self.request(session,"/end",b"{}")
                while worker.isRunning() and time.monotonic()<deadline:
                    self.qt.processEvents()
                    time.sleep(.02)
                self.qt.processEvents()
                self.assertFalse(worker.isRunning())
                self.assertEqual(errors,[])
                self.assertEqual(len(saved),1)
                self.assertEqual(Path(saved[0]).name,"TabTest.mp4")
                self.assertGreater(Path(saved[0]).stat().st_size,100)
                from imageio_ffmpeg import read_frames
                import numpy as np
                reader=read_frames(saved[0],pix_fmt="rgb24")
                try:
                    next(reader)
                    pixel=np.frombuffer(next(reader),np.uint8).reshape(48,64,3)[24,32]
                    self.assertGreater(int(pixel[0]),220)
                    self.assertLess(int(pixel[1]),30)
                finally:
                    reader.close()
                self.assertFalse(list(Path(directory).glob(".*.parts")))
            finally:
                worker.stop()
                worker.wait()

    def test_cancel_tab_before_connection_does_not_record(self):
        with tempfile.TemporaryDirectory() as directory, patch("screenrec.recorder.browser_tab.AudioSession") as audio:
            worker=BrowserWorker(Settings(output_dir=directory))
            saved=[]
            worker.recording_saved.connect(saved.append)
            worker.start()
            time.sleep(.1)
            worker.stop()
            self.assertTrue(worker.wait(5000))
            self.qt.processEvents()
            self.assertEqual(saved,[])
            audio.assert_not_called()
