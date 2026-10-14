"""Build and verify both Windows profiles from one clean commit (Modern venv)."""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def add_extension(archive, source, prefix=""):
    for path in sorted(source.rglob("*")):
        if path.is_file():
            archive.write(path, arcname=prefix + path.relative_to(source).as_posix())


def region_capture_unavailable(report):
    error = report.get("error", "")
    if not isinstance(error, str) or "BitBlt" not in error:
        return False
    lowered = error.casefold()
    return "winerror 5" in lowered or "denied" in lowered or "отказано в доступе" in lowered


def main():
    if sys.prefix == sys.base_prefix or platform.system() != "Windows":
        raise SystemExit("Use Windows and the Modern .venv")
    if platform.machine().lower() not in ("amd64", "x86_64"):
        raise SystemExit("Windows x64 is required")
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    git = ["git", "-c", f"safe.directory={root.as_posix()}"]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    from packaging.version import Version
    if str(Version(version)) != version or any(c not in "0123456789." for c in version):
        raise SystemExit("Use a numeric release version")
    if run(*git, "status", "--porcelain", capture_output=True, text=True).stdout.strip():
        raise SystemExit("Commit changes before releasing")
    commit = run(*git, "rev-parse", "HEAD", capture_output=True, text=True).stdout.strip()
    target = root / "releases" / version
    if target.exists():
        raise SystemExit(f"Release exists: {target}")
    profiles = (("modern", root / ".venv/Scripts/python.exe", "PySide6", "Windows10-11"),
                ("legacy", root / ".venv-legacy/Scripts/python.exe", "PySide2", "Windows8-8.1"))
    for _, python, _, _ in profiles:
        if not python.is_file():
            raise SystemExit(f"Missing build environment: {python}")
    pending = target.with_name(version + ".pending")
    pending.mkdir(parents=True, exist_ok=False)
    manifest = {"version": version, "commit": commit, "platform": platform.platform(), "profiles": {}}
    documents = ["README.md", "README.ru.md", "AGENT.md", "CHANGELOG.md", "RELEASE.md", "LICENSE"]
    documents.extend(path.name for path in root.glob(f"AUDIT_{version}*.md"))
    extension = root / "src/screenrec/browser_extension"
    for name in documents:
        shutil.copy2(root / name, pending / name)
    for profile, python, backend, windows in profiles:
        print(f"Building and testing {profile}", flush=True)
        env = dict(os.environ, PYTHONPATH=str(root / "src"), SCREENREC_QT=backend)
        run(str(python), "-c", "import sys; assert sys.prefix != sys.base_prefix", env=env)
        # Check the selected venv's installed distributions. PYTHONPATH points
        # at the source tree, whose stale ignored egg-info can otherwise shadow
        # the actual Legacy package set and report false dependency failures.
        run(str(python), "-m", "pip", "check")
        if profile == "modern":
            run(str(python), "-m", "unittest", "discover", "-s", "tests", "-v", env=env)
        else:
            run(str(python), "-m", "compileall", "-q", "src", env=env)
            run(str(python), "-c", "import screenrec.app, screenrec.recorder.browser_tab, screenrec.config.profiles", env=env)
        build_output = root / "dist" / profile
        run(str(python), "scripts/build.py", "--output-dir", str(build_output), env=env)
        exe = pending / f"ScreenRec-{version}-{windows}-x64.exe"
        shutil.copy2(build_output / "ScreenRec.exe", exe)
        lockfile = pending / f"requirements-{profile}-lock.txt"
        lockfile.write_text(run(str(python), "-m", "pip", "freeze", "--exclude-editable", env=env,
                                capture_output=True, text=True).stdout, encoding="utf-8")
        runtime = json.loads(run(str(python), "-c",
            "import json, platform, importlib.metadata as m; print(json.dumps({'python': platform.python_version(), 'pyinstaller': m.version('pyinstaller')}))",
            env=env, capture_output=True, text=True).stdout)
        standalone_env = dict(os.environ)
        for key in ("PYTHONPATH", "PYTHONHOME", "IMAGEIO_FFMPEG_EXE", "SCREENREC_QT", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
            standalone_env.pop(key, None)
        standalone_env["PATH"] = os.pathsep.join([str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]])
        reports = {}
        for mode, options in (("synthetic", ("--synthetic",)), ("window", ("--window-fixture",)),
                              ("region", ("--region-fixture",))):
            diagnostic = root / ".test-output" / f"release-{version}-{profile}" / mode
            report_path = diagnostic / "selftest-mp4-none.json"
            try:
                run(str(exe), "--self-test", "--output", str(diagnostic), *options,
                    cwd=pending, env=standalone_env, timeout=120)
            except subprocess.CalledProcessError:
                if mode != "region" or not report_path.is_file():
                    raise
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if not region_capture_unavailable(report):
                    raise
                reports[mode] = {"ok": False,
                                 "skipped": "Windows denied BitBlt screen capture in the build session"}
                print(f"Skipped {profile} region self-test: screen capture is unavailable in this session", flush=True)
                continue
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not report.get("ok"):
                raise RuntimeError(f"Standalone test failed: {profile} {mode}")
            reports[mode] = {key: report[key] for key in ("ok", "frames", "seconds", "audio", "overlays", "logging", "player")}
        manifest["profiles"][profile] = {**runtime, "exe": exe.name, "tests": reports}
        with zipfile.ZipFile(pending / f"ScreenRec-{version}-{windows}-x64.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in [exe, lockfile, *(pending / name for name in documents)]:
                archive.write(path, arcname=path.name)
            add_extension(archive, extension, "browser-extension/")
    with zipfile.ZipFile(pending / f"ScreenRec-{version}-browser-extension.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        add_extension(archive, extension)
    run(*git, "archive", "--format=zip", f"--output={pending / f'ScreenRec-{version}-source.zip'}", commit)
    if run(*git, "rev-parse", "HEAD", capture_output=True, text=True).stdout.strip() != commit or run(
            *git, "status", "--porcelain", capture_output=True, text=True).stdout.strip():
        raise RuntimeError("Source changed during release; refusing to label this build with the original commit")
    manifest["built_at_utc"] = datetime.now(timezone.utc).isoformat()
    (pending / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    hashes = []
    for path in sorted(pending.iterdir()):
        if path.is_file() and not path.name.endswith((".log", ".log.1", ".log.2", ".log.3")):
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            hashes.append(f"{digest}  {path.name}")
    (pending / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    pending.rename(target)
    print(f"Release ready: {target}\nCommit: {commit}", flush=True)


if __name__ == "__main__":
    main()
