"""Explicit standalone-build diagnostic; never runs on normal launch."""
import argparse
import json
import os
import subprocess
import time
import traceback
from pathlib import Path
from unittest.mock import patch


class TestSource:
    def __init__(self, monitor):
        self.frame = bytes([40, 100, 180, 255]) * monitor["width"] * monitor["height"]
    def __enter__(self):
        return self
    def grab(self):
        return self.frame
    def __exit__(self, *_):
        pass


def run(arguments):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--audio", choices=["none", "microphone", "system", "both"], default="none")
    parser.add_argument("--format", choices=["mp4", "mkv", "webm"], default="mp4")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--window-fixture", action="store_true")
    args = parser.parse_args(arguments)
    directory = Path(args.output).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / f"selftest-{args.format}-{args.audio}.json"
    os.environ["QT_QPA_PLATFORM"] = "windows" if args.window_fixture else "offscreen"
    worker = None
    try:
        from PySide6.QtWidgets import QApplication, QWidget
        from imageio_ffmpeg import get_ffmpeg_exe, count_frames_and_secs
        from .app import ScreenRecApp
        from .config.settings import Settings
        from .recorder.worker import RecordingWorker
        from .recorder.screen import monitors, ScreenSource
        app = QApplication([])
        extension = Path(__file__).parent / "browser_extension"
        for name in ("manifest.json", "background.js", "offscreen.js", "popup.html"):
            assert (extension / name).is_file(), f"Missing extension resource: {name}"
        settings = Settings(output_dir=str(directory), fps=15, file_format=args.format,
                            audio_mode=args.audio, notifications=False)
        from PySide6.QtGui import QImage, QColor
        from .config.templates import default_template
        logo = QImage(40,30,QImage.Format.Format_ARGB32)
        logo.fill(QColor("red"))
        logo_path = directory / "overlay-logo.png"
        assert logo.save(str(logo_path))
        settings.overlay = default_template()
        settings.overlay["image"].update(enabled=True,path=str(logo_path),x=.25,y=.25,w=.5,h=.5)
        settings.overlay["text"].update(enabled=True,text="ScreenRec overlay",size=.06)
        settings.overlay_enabled = True
        settings.filename_prefix = "Custom"
        settings.filename_date = False
        settings.filename_time = False
        settings.filename_uuid = False
        monitor = {"left": 0, "top": 0, "width": 320, "height": 180} if args.synthetic else monitors()[0]
        if args.window_fixture:
            fixture = QWidget()
            fixture.setWindowTitle("ScreenRec native capture diagnostic")
            fixture.setStyleSheet("background: #20b060")
            fixture.resize(480, 320)
            fixture.show()
            app.processEvents()
            monitor = {"kind": "window", "hwnd": int(fixture.winId()), "pid": os.getpid(),
                       "title": fixture.windowTitle(), "left": 0, "top": 0, "width": 480, "height": 320}
        with patch("screenrec.app.Settings.load", return_value=settings), patch("screenrec.app.monitors", return_value=[monitor]):
            controller = ScreenRecApp(app)
            assert not controller.icon.isNull(), "Missing application icon"
            from .ui.themes.theme_manager import THEMES
            from PySide6.QtGui import QIcon
            for name, theme in THEMES.items():
                with patch.object(Settings, "path", return_value=directory / "theme-settings.json"):
                    controller.theme_actions[name].trigger()
                assert json.loads((directory / "theme-settings.json").read_text(encoding="utf-8"))["theme"] == name
                assert controller.theme_actions[name].isChecked()
                assert controller.window.windowIcon().pixmap(32, 32).toImage() == QIcon(str(theme["window_icon_path"])).pixmap(32, 32).toImage()
                assert controller.tray.icon().pixmap(32, 32).toImage() == QIcon(str(theme["tray_icon_path"])).pixmap(32, 32).toImage()
                assert app.styleSheet() == theme["qss_path"].read_text(encoding="utf-8")
                controller.window.resize(820, 660)
                controller.window.grab().save(str(directory / f"theme-{name}.png"))
            controller.set_theme("blue", save=False)
            from .ui.overlay_editor import OverlayEditor
            editor = OverlayEditor(settings,controller.window)
            editor.grab().save(str(directory / "overlay-editor.png"))
            editor.deleteLater()
            from .ui.filename_dialog import FilenameDialog
            naming = FilenameDialog(settings,controller.window)
            assert naming.preview.text() == "Custom." + args.format
            naming.grab().save(str(directory / "filename-editor.png"))
            naming.deleteLater()
            from .ui.settings_dialog import SettingsDialog
            dialog = SettingsDialog(settings, controller.window)
            assert dialog.result_settings() == settings
            dialog.deleteLater()
            from .ui.logging_dialog import LoggingDialog
            logging_dialog = LoggingDialog(settings,controller.window)
            assert not logging_dialog.enabled.isChecked()
            logging_dialog.grab().save(str(directory / "logging-editor.png"))
            logging_dialog.deleteLater()
            controller.timer.stop()
            controller.cleanup()
        from .logger.logger import configure as configure_log, get_logger, get_default_log_path, LEVELS
        import sys
        if getattr(sys,"frozen",False):
            assert get_default_log_path().parent == Path(sys.executable).resolve().parent
        log_path = directory / "diagnostic.log"
        actual, warning = configure_log(True,str(log_path),list(LEVELS))
        assert actual == log_path and warning is None
        diagnostic_log = get_logger("selftest")
        for name,number in LEVELS.items():
            diagnostic_log.logger.log(number,"SELFTEST_LEVEL_%s",name)
        errors, saved, started = [], [], []
        worker = RecordingWorker(monitor, directory, 15, settings=settings)
        worker.failed.connect(errors.append)
        worker.recording_saved.connect(saved.append)
        worker.recording_started.connect(lambda _: started.append(time.monotonic()))
        with patch("screenrec.recorder.worker.ScreenSource", TestSource if args.synthetic else ScreenSource):
            worker.start()
            deadline = time.monotonic() + 60
            while worker.isRunning() and time.monotonic() < deadline:
                app.processEvents()
                if started and time.monotonic() - started[0] >= 2:
                    worker.stop()
                time.sleep(0.01)
            if worker.isRunning():
                raise RuntimeError("Self-test timed out")
            app.processEvents()
        if errors:
            raise RuntimeError("\n".join(errors))
        if not saved:
            raise RuntimeError("No recording returned")
        video = saved[0]
        assert Path(video).stem == "Custom" or Path(video).stem.startswith("Custom_"), video
        count, duration = count_frames_and_secs(video)
        from imageio_ffmpeg import read_frames
        import numpy as np
        reader=read_frames(video,pix_fmt="rgb24")
        try:
            metadata=next(reader)
            w,h=metadata["size"]
            pixel=np.frombuffer(next(reader),np.uint8).reshape(h,w,3)[h//2,w//2]
            assert int(pixel[0])>220 and int(pixel[1])<35, f"Overlay absent: {pixel}"
        finally:
            reader.close()
        decoded = subprocess.run([get_ffmpeg_exe(), "-v", "error", "-i", video, "-f", "null", "-"],
                                 capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert decoded.returncode == 0, decoded.stderr.decode(errors="replace")
        probe = subprocess.run([get_ffmpeg_exe(), "-i", video], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        info = probe.stderr.decode(errors="replace")
        assert ("Audio:" in info) == (args.audio != "none"), info
        from .ui.recordings_view import RecordingsView
        from PySide6.QtMultimedia import QMediaPlayer
        viewer = RecordingsView(directory)
        try:
            viewer.resize(1000,650)
            viewer.show()
            viewer.refresh(select=video)
            deadline = time.monotonic()+15
            while viewer.frame_image is None and time.monotonic()<deadline:
                app.processEvents()
                time.sleep(.01)
            assert viewer.frame_image is not None, viewer.player.errorString()
            assert viewer.player.error() == QMediaPlayer.Error.NoError
            assert viewer.player.duration() > 0
            viewer.frame_image.save(str(directory / "player-frame.png"))
            viewer.grab().save(str(directory / "player.png"))
            viewer.set_muted(True)
            viewer.toggle_play()
            deadline = time.monotonic()+5
            while viewer.player.position()<200 and time.monotonic()<deadline:
                app.processEvents()
                time.sleep(.01)
            assert viewer.player.position() >= 200
            viewer.toggle_play()
            viewer.player.setPosition(500)
            viewer.toggle_fullscreen()
            app.processEvents()
            viewer.leave_fullscreen()
            viewer.stop_playback()
            assert viewer.player.position() == 0
        finally:
            viewer.shutdown()
            viewer.close()
            app.processEvents()
        configure_log(False)
        log_text = log_path.read_text(encoding="utf-8")
        for name in LEVELS:
            assert "SELFTEST_LEVEL_" + name in log_text
        assert "Encoder setup" in log_text and "Capture worker starting" in log_text
        before = log_path.read_bytes()
        diagnostic_log.fatal_error("DISABLED_SENTINEL")
        assert log_path.read_bytes() == before
        report.write_text(json.dumps({"ok": True, "file": video, "frames": count, "seconds": duration,
                                     "audio": args.audio, "overlays": True, "logging": True, "player": True, "ffmpeg": get_ffmpeg_exe(), "streams": info}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    except Exception:
        report.write_text(json.dumps({"ok": False, "error": traceback.format_exc()}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    finally:
        from .logger.logger import shutdown as shutdown_log
        shutdown_log()
        if worker and worker.isRunning():
            worker.stop()
            encoder = worker.encoder
            if encoder:
                encoder.abort()
            worker.wait()
