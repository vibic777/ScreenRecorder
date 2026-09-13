FORMATS = {"mp4": "MP4 (H.264)", "mkv": "MKV (H.264)", "webm": "WebM (VP9)"}
QUALITIES = {"high": "Высокое", "balanced": "Сбалансированное", "compact": "Компактный файл"}
AUDIO_MODES = {"none": "Без звука", "microphone": "Микрофон", "system": "Системный звук", "both": "Микрофон + системный звук"}
CRF = {"mp4": {"high": 18, "balanced": 23, "compact": 30},
       "mkv": {"high": 18, "balanced": 23, "compact": 30},
       "webm": {"high": 24, "balanced": 32, "compact": 40}}


def video_options(file_format, quality, fps):
    if file_format not in FORMATS or quality not in QUALITIES:
        raise ValueError("Неизвестный формат или качество записи")
    if file_format == "webm":
        codec = ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "6", "-b:v", "0"]
    else:
        codec = ["-c:v", "libx264", "-preset", "ultrafast"]
    return codec + ["-crf", str(CRF[file_format][quality]), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    "-pix_fmt", "yuv420p", "-g", str(fps * 2)] + container_options(file_format)


def container_options(file_format):
    return ["-movflags", "+frag_keyframe+empty_moov+default_base_moof"] if file_format == "mp4" else []
