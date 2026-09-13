import subprocess
from imageio_ffmpeg import get_ffmpeg_exe
from screenrec.config.recording import container_options


def mux_audio(video, tracks, output, settings, duration):
    """Copy encoded video; align, mix and encode only audio, preserving video duration."""
    command = [get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n", "-i", str(video)]
    filters = []
    for index, (path, offset) in enumerate(tracks, 1):
        command += ["-i", str(path)]
        filters.append(f"[{index}:a]adelay={round(offset * 1000)}:all=1,apad[a{index}]")
    inputs = "".join(f"[a{i}]" for i in range(1, len(tracks) + 1))
    filters.append(f"{inputs}amix=inputs={len(tracks)}:normalize=1[audio]")
    codec = "libopus" if settings.file_format == "webm" else "aac"
    command += ["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[audio]",
                "-c:v", "copy", "-c:a", codec, "-b:a", f"{settings.audio_bitrate}k",
                "-t", f"{duration:.6f}"] + container_options(settings.file_format) + [str(output)]
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, timeout=max(120, duration),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace") or "Не удалось добавить звук.")
