import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from PySide6.QtWidgets import QApplication
from screenrec.config.settings import Settings
from screenrec.config.recording import CRF, video_options
from screenrec.recorder.encoder import Encoder
from screenrec.recorder.muxer import mux_audio
from screenrec.ui.settings_dialog import SettingsDialog
from screenrec.recorder.worker import RecordingWorker


class RecordingOptionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_formats_audio_mix_and_silence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rate = 48000
            samples = (np.sin(2 * np.pi * 440 * np.arange(rate) / rate) * 8000).astype("<i2")
            wav = root / "tone.wav"
            with wave.open(str(wav), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(rate)
                stream.writeframes(samples.tobytes())
            for fmt in ("mp4", "mkv", "webm"):
                for quality in CRF[fmt]:
                    with self.subTest(format=fmt, quality=quality):
                        video = root / f"{quality}.{fmt}"
                        encoder = Encoder(video, 65, 49, 15, fmt, quality)
                        for _ in range(15):
                            encoder.write(bytes([10, 60, 100, 255]) * 65 * 49)
                        encoder.finish()
                        info = subprocess.run([get_ffmpeg_exe(), "-i", str(video)], capture_output=True).stderr
                        self.assertNotIn(b"Audio:", info)
                        output = root / f"{quality}-audio.{fmt}"
                        mux_audio(video, [(wav, 0), (wav, 0.05)], output,
                                  Settings(file_format=fmt, quality=quality, audio_mode="both"), 1)
                        pcm = subprocess.run([get_ffmpeg_exe(), "-v", "error", "-i", str(output),
                                              "-map", "0:a:0", "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
                                             capture_output=True, timeout=10)
                        self.assertEqual(pcm.returncode, 0, pcm.stderr)
                        values = np.frombuffer(pcm.stdout, dtype="<i2")
                        self.assertGreater(np.abs(values.astype(float)).mean(), 100)
                        self.assertAlmostEqual(len(values) / rate, 1, delta=0.08)

    def test_dialog_explicit_no_audio_and_cancel(self):
        settings = Settings()
        dialog = SettingsDialog(settings)
        self.assertEqual(dialog.audio_mode.currentData(), "none")
        self.assertFalse(dialog.microphone.isEnabled())
        self.assertFalse(dialog.system_device.isEnabled())
        dialog.audio_mode.setCurrentIndex(dialog.audio_mode.findData("both"))
        self.assertTrue(dialog.microphone.isEnabled())
        self.assertTrue(dialog.system_device.isEnabled())
        dialog.reject()
        self.assertEqual(settings.audio_mode, "none")
        self.assertEqual(dialog.result_settings().audio_mode, "both")

    def test_single_instance_setting_is_in_configurator(self):
        settings = Settings()
        dialog = SettingsDialog(settings)
        self.assertFalse(settings.allow_multiple_instances)
        self.assertFalse(dialog.allow_multiple_instances.isChecked())
        dialog.allow_multiple_instances.setChecked(True)
        self.assertTrue(dialog.result_settings().allow_multiple_instances)
        dialog.deleteLater()

    def test_invalid_persisted_options_fall_back(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Settings, "path", return_value=Path(directory) / "settings.json"):
            Settings.path().write_text('{"file_format":"exe","quality":"invalid","audio_mode":"bad","audio_bitrate":-1}')
            self.assertEqual(Settings.load(), Settings())
        with self.assertRaises(ValueError):
            video_options("invalid", "balanced", 30)

    def test_audio_failure_does_not_silently_save_video(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("screenrec.recorder.worker.AudioSession") as session, \
             patch("screenrec.recorder.worker.Encoder") as encoder:
            session.return_value.prepare.side_effect = RuntimeError("Device unavailable")
            session.return_value.origin = None
            worker = RecordingWorker({"width": 64, "height": 48}, directory, 15,
                                      settings=Settings(audio_mode="microphone"))
            errors, saved = [], []
            worker.failed.connect(errors.append)
            worker.recording_saved.connect(saved.append)
            worker.run()
            self.assertIn("Device unavailable", errors[0])
            self.assertEqual(saved, [])
            encoder.assert_not_called()
            session.return_value.finish.assert_called_once()
