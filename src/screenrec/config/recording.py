from screenrec.localization import tr

FORMATS = {"mp4": "MP4 (H.264)", "mkv": "MKV (H.264)", "webm": "WebM (VP9)"}
# Display labels live in the locales: settings.quality.<key>, settings.audio_mode.<key>.
QUALITIES = ("high", "balanced", "compact")
AUDIO_MODES = ("none", "microphone", "system", "both")
CRF = {"mp4": {"high": 18, "balanced": 23, "compact": 30},
       "mkv": {"high": 18, "balanced": 23, "compact": 30},
       "webm": {"high": 24, "balanced": 32, "compact": 40}}


def video_options(file_format, quality, fps):
    if file_format not in FORMATS or quality not in QUALITIES:
        raise ValueError(tr("error.recording_options"))
    if file_format == "webm":
        codec = ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "6", "-b:v", "0"]
    else:
        codec = ["-c:v", "libx264", "-preset", "ultrafast"]
    return codec + ["-crf", str(CRF[file_format][quality]), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    "-pix_fmt", "yuv420p", "-g", str(fps * 2)] + container_options(file_format)


def container_options(file_format):
    if file_format != "mp4":
        return []
    # Qt5/WMF on Windows 8.1 is unreliable with fragmented MP4.  Keep the
    # streaming-friendly container for Qt6, but write a regular MP4 for the
    # legacy player so it can open recordings through QMediaPlayer.
    if os.environ.get("SCREENREC_QT") == "PySide2":
        return []
    return ["-movflags", "+frag_keyframe+empty_moov+default_base_moof"]
import os
