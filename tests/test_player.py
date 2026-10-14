import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import time
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from screenrec.recorder.encoder import Encoder
from screenrec.ui.recordings_view import RecordingsView

class PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def wait_for(self,predicate,seconds=10):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(.01)
        self.fail("Player timeout")
    def make_video(self,path,format="mp4"):
        encoder=Encoder(path,160,120,15,format)
        for _ in range(45):
            encoder.write(bytes([20,180,40,255])*160*120)
        encoder.finish()
    def test_real_decode_seek_pause_stop_all_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            for format in ("mp4","mkv","webm"):
                path=Path(directory)/f"test.{format}"
                self.make_video(path,format)
            view=RecordingsView(directory)
            view.show()
            try:
                for format in ("mp4","mkv","webm"):
                    view.refresh(select=Path(directory)/f"test.{format}")
                    self.wait_for(lambda:view.frame_image is not None and not view.priming)
                    self.assertEqual(view.player.error(),QMediaPlayer.Error.NoError)
                    self.assertEqual(view.player.playbackState(),QMediaPlayer.PlaybackState.PausedState)
                    self.assertGreater(view.player.duration(),2500)
                    self.assertGreater(view.frame_image.pixelColor(80,60).green(),140)
                    view.set_muted(True)
                    view.toggle_play()
                    self.wait_for(lambda:view.player.position()>200)
                    view.toggle_play()
                    self.assertEqual(view.player.playbackState(),QMediaPlayer.PlaybackState.PausedState)
                    view.seek(1000)
                    self.wait_for(lambda:view.player.position()>1000)
                    view.stop_playback()
                    self.assertEqual(view.player.position(),0)
                    self.assertEqual(view.player.playbackState(),QMediaPlayer.PlaybackState.StoppedState)
                view.toggle_fullscreen()
                self.app.processEvents()
                self.assertIsNotNone(view.fullscreen)
                view.leave_fullscreen()
                self.assertIsNone(view.fullscreen)
                view.set_recording(True)
                view.toggle_play()
                self.assertEqual(view.player.playbackState(),QMediaPlayer.PlaybackState.StoppedState)
            finally:
                view.shutdown()
                view.close()
                self.app.processEvents()
    def test_catalogue_filters_active_files_and_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ("a.mp4","b.mp4","active.mp4"):
                self.make_video(root/name)
            (root/".active.mp4.recording").mkdir()
            (root/"note.txt").write_text("not video")
            view=RecordingsView(directory)
            try:
                view.sort.setCurrentIndex(2)
                self.assertEqual(view.list.topLevelItemCount(),2)
                view.list.setCurrentItem(view.list.topLevelItem(0))
                self.assertEqual(view.current.name,"a.mp4")
                view.adjacent(1)
                self.assertEqual(view.current.name,"b.mp4")
                view.adjacent(-1)
                self.assertEqual(view.current.name,"a.mp4")
                view.search.setText("b.")
                self.assertTrue(view.list.topLevelItem(0).isHidden())
                self.assertFalse(view.list.topLevelItem(1).isHidden())
            finally:
                view.shutdown()
                view.close()
                self.app.processEvents()

    def test_changing_directory_reloads_catalogue(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.make_video(Path(second)/"moved.mp4")
            view=RecordingsView(first)
            try:
                self.assertEqual(view.list.topLevelItemCount(),0)
                view.set_directory(second)
                self.assertEqual(view.folder.text(),str(Path(second)))
                self.assertEqual(view.list.topLevelItemCount(),1)
                self.assertIsNone(view.current)
            finally:
                view.shutdown()
                view.close()
                self.app.processEvents()

    def test_audio_controls_and_invalid_file(self):
        import subprocess
        from imageio_ffmpeg import get_ffmpeg_exe
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"audio.mp4"
            subprocess.run([get_ffmpeg_exe(),"-v","error","-f","lavfi","-i","color=c=green:s=160x120:r=15",
                            "-f","lavfi","-i","sine=frequency=440:sample_rate=48000","-t","2",
                            "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(path)],
                           check=True,timeout=30,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            view=RecordingsView(directory)
            view.set_muted(True)
            try:
                view.refresh(select=path)
                self.wait_for(lambda:view.frame_image is not None)
                self.assertTrue(view.player.hasAudio())
                self.assertTrue(view.audio.isMuted())
                view.volume.setValue(25)
                self.assertAlmostEqual(view.audio.volume(),.25)
                view.speed.setCurrentIndex(3)
                self.assertEqual(view.player.playbackRate(),1.5)
                self.assertTrue(view.frame_image.save(str(Path(directory)/"frame.png")))
                bad=Path(directory)/"broken.mp4"
                bad.write_bytes(b"invalid video")
                view.load(bad)
                self.wait_for(lambda:view.player.error()!=QMediaPlayer.Error.NoError and "Playback failed" in view.info.text())
                self.assertIn("Playback failed",view.info.text())
            finally:
                view.shutdown()
                view.close()
                self.app.processEvents()
