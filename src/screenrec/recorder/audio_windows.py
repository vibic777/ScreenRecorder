"""Windows native WASAPI capture using device-native sample rates and channel counts."""
from screenrec.localization import tr
import json
import queue
import time
import wave


def device_key(device):
    # Persist the name and API, never a volatile enumeration index.
    return json.dumps([device["name"], bool(device["isLoopbackDevice"])], ensure_ascii=False)


def inputs(manager):
    import pyaudiowpatch as pa
    api = manager.get_host_api_info_by_type(pa.paWASAPI)
    return [d for d in manager.get_device_info_generator()
            if d["hostApi"] == api["index"] and d["maxInputChannels"] > 0]


def devices():
    import pyaudiowpatch as pa
    with pa.PyAudio() as manager:
        return [(device_key(d), d["name"], d["isLoopbackDevice"]) for d in inputs(manager)]


def capture(kind, device_id, path, ready, gate, stop, result):
    import pyaudiowpatch as pa
    with pa.PyAudio() as manager:
        if device_id:
            device = next((d for d in inputs(manager) if device_key(d) == device_id
                           and d["isLoopbackDevice"] == (kind == "system")), None)
        elif kind == "system":
            device = manager.get_default_wasapi_loopback()
        else:
            api = manager.get_host_api_info_by_type(pa.paWASAPI)
            device = manager.get_device_info_by_index(api["defaultInputDevice"])
        if device is None:
            raise RuntimeError(tr("error.audio_device_refresh"))
        rate, channels = int(device["defaultSampleRate"]), int(device["maxInputChannels"])
        chunks = queue.Queue(maxsize=200)
        overflow = []

        def callback(data, frame_count, time_info, status):
            try:
                chunks.put_nowait(data)
                if status:
                    overflow.append(status)
            except queue.Full:
                overflow.append("queue full")
            return None, pa.paContinue

        with wave.open(str(path), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(2)
            output.setframerate(rate)
            with manager.open(format=pa.paInt16, channels=channels, rate=rate, input=True,
                              input_device_index=device["index"], frames_per_buffer=max(128, rate // 100),
                              stream_callback=callback, start=False) as stream:
                ready.put(None)
                while not gate.wait(0.05):
                    if stop.is_set():
                        return
                started = time.monotonic()
                stream.start_stream()
                frames = 0
                while not stop.is_set():
                    if overflow:
                        raise RuntimeError(tr("error.audio_overflow"))
                    try:
                        data = chunks.get(timeout=0.1)
                    except queue.Empty:
                        # WASAPI loopback may deliver no packets while the speaker is silent.
                        missing = int(max(0, time.monotonic() - started - 0.2) * rate) - frames
                        if missing > 0:
                            output.writeframesraw(bytes(missing * channels * 2))
                            frames += missing
                        continue
                    output.writeframesraw(data)
                    frames += len(data) // (channels * 2)
                stream.stop_stream()
                while not chunks.empty():
                    output.writeframesraw(chunks.get_nowait())
        result.put((str(path), started, None))
