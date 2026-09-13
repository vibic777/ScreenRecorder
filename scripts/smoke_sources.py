"""Native-window/region fixture: no capture of unrelated windows is required."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QTimer, QEventLoop
from screenrec.recorder.worker import RecordingWorker
from screenrec.recorder.screen import ScreenSource, monitors
from screenrec.ui.region_selector import screen_for_monitor
from imageio_ffmpeg import get_ffmpeg_exe


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/".test-output"/"sources"
    output.mkdir(parents=True,exist_ok=True)
    app=QApplication([])
    target=QWidget()
    target.setWindowTitle("ScreenRec capture fixture")
    target.setStyleSheet("background:#20b060")
    target.setGeometry(150,150,420,260)
    target.show()
    cover=QWidget()
    cover.setStyleSheet("background:#e02020")
    cover.setGeometry(130,130,480,340)
    app.processEvents()
    source={"kind":"window","hwnd":int(target.winId()),"pid":os.getpid(),"width":420,"height":260}
    worker=RecordingWorker(source,output,15)
    errors,saved=[],[]
    worker.failed.connect(errors.append)
    worker.recording_saved.connect(saved.append)
    worker.recording_started.connect(lambda _: QTimer.singleShot(200,cover.show))
    worker.recording_started.connect(lambda _: QTimer.singleShot(2200,worker.stop))
    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    QTimer.singleShot(200,worker.start)
    QTimer.singleShot(15000,worker.stop)
    loop.exec()
    worker.wait()
    if errors:
        raise RuntimeError(errors)
    assert saved, "No video"
    decoded=subprocess.run([get_ffmpeg_exe(),"-v","error","-i",saved[0],"-vf","select=eq(n\\,20)","-frames:v","1",
                            "-f","rawvideo","-pix_fmt","bgra","-"],capture_output=True,check=True)
    import numpy as np
    pixels=np.frombuffer(decoded.stdout,dtype=np.uint8).reshape(-1,4)
    green=((pixels[:,1]>120)&(pixels[:,1]>pixels[:,2]*1.2)).mean()
    assert green>.7, f"Occluding window leaked into recording: green ratio {green}"
    cover.hide()
    target.raise_()
    app.processEvents()
    time.sleep(.2)
    app.processEvents()
    monitor=monitors()[0]
    screen_for_monitor(monitor,0)
    # Capture a known client rectangle of the green fixture, in native pixel coordinates.
    import ctypes
    from ctypes import wintypes as wt
    point=wt.POINT(40,40)
    ctypes.windll.user32.ClientToScreen(wt.HWND(int(target.winId())),ctypes.byref(point))
    region={"left":point.x,"top":point.y,"width":120,"height":80}
    with ScreenSource(region) as capture:
        frame=capture.grab()
    pixels=np.frombuffer(frame,dtype=np.uint8).reshape(-1,4)
    print("Region diagnostic", region, "visible", target.isVisible(), "pixel", pixels[0].tolist(), "green", float((pixels[:,1]>120).mean()), flush=True)
    from PySide6.QtGui import QImage
    QImage(frame,120,80,480,QImage.Format.Format_RGB32).save(str(output/"region.png"))
    target.grab().save(str(output/"fixture.png"))
    assert (pixels[:,1]>120).mean()>.9
    target.hide()
    (output/"report.json").write_text(json.dumps({"ok":True,"video":saved[0],"green_ratio":float(green),"region":region},indent=2))
    print("Native window under occlusion and region capture passed.")


if __name__=="__main__":
    main()
