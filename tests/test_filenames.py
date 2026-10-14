import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from screenrec.config.settings import Settings
from screenrec.config.filenames import filename,clean_prefix,reserve,DATE_FORMATS
from screenrec.ui.filename_dialog import FilenameDialog

class FilenameTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_date_orders_and_12_hour_boundaries(self):
        settings=Settings(filename_prefix="Lesson",filename_uuid=False)
        moment=datetime(2026,9,13,18,5,9)
        expected=("2026-09-13","13-09-2026","09-13-2026","13.09.2026","20260913","09.13.2026")
        for key,date in zip(DATE_FORMATS,expected):
            settings.filename_date_format=key
            self.assertEqual(filename(settings,moment),f"Lesson_{date}_18-05-09.mp4")
        settings.filename_date=False
        settings.filename_time_format="12h"
        for hour,expected in ((0,"12-05-09_AM"),(12,"12-05-09_PM"),(18,"06-05-09_PM"),(11,"11-05-09_AM")):
            self.assertEqual(filename(settings,moment.replace(hour=hour)),f"Lesson_{expected}.mp4")
        settings.filename_time_format="24h_compact"
        self.assertEqual(filename(settings,moment),"Lesson_180509.mp4")
        settings.filename_time=False
        settings.filename_uuid=True
        self.assertEqual(filename(settings,moment,"fixed"),"Lesson_fixed.mp4")
        settings.filename_prefix=""
        settings.filename_uuid=False
        self.assertEqual(filename(settings,moment),"ScreenRec.mp4")

    def test_safe_prefix_roundtrip_and_dialog_cancel(self):
        self.assertEqual(clean_prefix("CON"),"_CON")
        self.assertEqual(clean_prefix("LPT1.log"),"_LPT1.log")
        unsafe="../bad\\name:\x00?*"
        safe=clean_prefix(unsafe)
        self.assertFalse(any(c in safe for c in '/\\:\x00?*'))
        self.assertFalse(safe.startswith("."))
        self.assertLessEqual(len(clean_prefix("界"*80).encode("utf-8")),128)
        settings=Settings(filename_prefix="Урок",filename_date=False,filename_time_format="12h")
        with TemporaryDirectory() as directory,patch.object(Settings,"path",return_value=Path(directory)/"settings.json"):
            settings.save()
            self.assertEqual(Settings.load(),settings)
        dialog=FilenameDialog(settings)
        dialog.prefix.setText("Changed")
        dialog.time.setChecked(False)
        dialog.uuid.setChecked(False)
        self.assertEqual(dialog.preview.text(),"Changed.mp4")
        dialog.reject()
        self.assertEqual(settings.filename_prefix,"Урок")
        dialog.deleteLater()

    def test_collisions_and_concurrent_reservations(self):
        settings=Settings(filename_prefix="Clip",filename_date=False,filename_time=False,filename_uuid=False)
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"Clip.mp4").write_bytes(b"original")
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda _:reserve(root,settings),range(4)))
            self.assertEqual({path.name for path,_ in results},{"Clip_2.mp4","Clip_3.mp4","Clip_4.mp4","Clip_5.mp4"})
            self.assertEqual((root/"Clip.mp4").read_bytes(),b"original")
            for path,lock in results:
                self.assertEqual(path.parent,root)
                lock.rmdir()
