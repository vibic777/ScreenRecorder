"""Native audio isolated in processes so a stalled device can be stopped safely."""
import multiprocessing as mp
import platform
import queue
import time
import wave
from pathlib import Path


def devices():
    if platform.system() == "Windows":
        from .audio_windows import devices as windows_devices
        return windows_devices()
    import soundcard as sc
    items = sc.all_microphones(include_loopback=True)
    return [(str(d.id), d.name, d.isloopback) for d in items]


def _capture(kind, device_id, path, ready, gate, stop, result):
    try:
        if platform.system() == "Windows":
            from .audio_windows import capture
            capture(kind, device_id, path, ready, gate, stop, result)
            return
        import numpy as np
        import soundcard as sc
        if platform.system() not in ("Windows", "Linux"):
            raise RuntimeError("Аудиозахват поддерживает Windows/WASAPI и Linux/PulseAudio.")
        if device_id:
            candidates = sc.all_microphones(include_loopback=True)
            device = next((d for d in candidates if str(d.id) == device_id and d.isloopback == (kind == "system")), None)
        elif kind == "system":
            speaker = sc.default_speaker()
            device = sc.get_microphone(id=str(speaker.id), include_loopback=True) if speaker else None
        else:
            device = sc.default_microphone()
        if device is None:
            raise RuntimeError("Выбранное аудиоустройство недоступно. Откройте конфигуратор и выберите другое.")
        with device.recorder(samplerate=48000, blocksize=4800) as recorder, wave.open(str(path), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(48000)
            ready.put(None)
            while not gate.wait(0.05):
                if stop.is_set():
                    return
                recorder.record(numframes=None)
            # Drop buffered audio preceding the video start.
            recorder.record(numframes=None)
            started = time.monotonic()
            while not stop.is_set():
                chunk = recorder.record(numframes=4800)
                if chunk.shape[1] == 1:
                    chunk = np.repeat(chunk, 2, axis=1)
                chunk = np.nan_to_num(chunk[:, :2])
                output.writeframesraw((np.clip(chunk, -1, 1) * 32767).astype("<i2").tobytes())
        result.put((str(path), started, None))
    except Exception as exc:
        message = f"{kind}: {exc}"
        ready.put(message)
        result.put((str(path), 0, message))


from screenrec.logger.logger import get_logger
log = get_logger(__name__)

class AudioSession:
    def __init__(self, settings, directory):
        self.context = mp.get_context("spawn")
        self.gate = self.context.Event()
        self.stop_event = self.context.Event()
        self.items = []
        self.origin = None
        self.finished = False
        kinds = []
        if settings.audio_mode in ("microphone", "both"):
            kinds.append(("microphone", settings.microphone_id))
        if settings.audio_mode in ("system", "both"):
            kinds.append(("system", settings.system_device_id))
        for kind, device in kinds:
            ready, result = self.context.Queue(), self.context.Queue()
            path = Path(directory) / f"{kind}.wav"
            process = self.context.Process(target=_capture, args=(kind, device, path, ready, self.gate, self.stop_event, result), daemon=True)
            self.items.append((process, ready, result))

    def prepare(self):
        log.debug("Preparing audio sources: count=%s",len(self.items))
        try:
            for process, _, _ in self.items:
                process.start()
            for _, ready, _ in self.items:
                try:
                    error = ready.get(timeout=15)
                except queue.Empty:
                    raise RuntimeError("Аудиоустройство не ответило за 15 секунд.")
                if error:
                    raise RuntimeError(error)
        except Exception:
            self.finish(check=False)
            raise

    def start(self, origin):
        log.info("Audio capture started")
        self.origin = origin
        self.gate.set()

    def check(self):
        for process, _, _ in self.items:
            if process.exitcode is not None:
                raise RuntimeError("Захват звука прерван. Проверьте аудиоустройство.")

    def finish(self, check=True):
        if self.finished:
            return []
        self.finished = True
        self.stop_event.set()
        tracks, errors = [], []
        for process, ready, result in self.items:
            if process.pid is None:
                continue
            process.join(3)
            if process.is_alive():
                log.warning("Audio source timeout; terminating child process")
                process.terminate()
                process.join(3)
                if process.is_alive():
                    process.kill()
                    process.join()
                errors.append("Аудиоустройство зависло; захват остановлен принудительно.")
            elif check:
                try:
                    path, started, error = result.get(timeout=1)
                    if error:
                        errors.append(error)
                    else:
                        tracks.append((Path(path), max(0, started - self.origin)))
                except queue.Empty:
                    errors.append("Аудиоустройство не вернуло запись.")
            ready.close()
            result.close()
        log.debug("Audio capture finished: tracks=%s errors=%s",len(tracks),len(errors))
        if errors and check:
            log.error("Audio capture failed")
            raise RuntimeError("\n".join(errors))
        return tracks
