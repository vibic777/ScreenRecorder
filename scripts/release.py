"""Build a traceable Windows release from a clean commit."""
import hashlib
import importlib.metadata as metadata
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


def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)


def main():
    if sys.prefix == sys.base_prefix or platform.system() != "Windows":
        raise SystemExit("Use Windows and .venv")
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
    pending = target.with_name(version + ".pending")
    pending.mkdir(parents=True, exist_ok=True)
    run(sys.executable, "-m", "pip", "check")
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    run(sys.executable, "scripts/build.py")
    shutil.copy2(root / "dist/ScreenRec.exe", pending / "ScreenRec.exe")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("IMAGEIO_FFMPEG_EXE", None)
    env["PATH"] = os.pathsep.join([str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]])
    diagnostic = root / ".test-output" / f"release-{version}"
    run(str(pending / "ScreenRec.exe"), "--self-test", "--output", str(diagnostic), "--synthetic",
        cwd=pending, env=env, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
    report = json.loads((diagnostic / "selftest-mp4-none.json").read_text(encoding="utf-8"))
    if not report.get("ok"):
        raise RuntimeError("Standalone test failed")
    window_diagnostic = diagnostic / "window"
    run(str(pending / "ScreenRec.exe"), "--self-test", "--window-fixture", "--output", str(window_diagnostic),
        cwd=pending, env=env, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
    window_report = json.loads((window_diagnostic / "selftest-mp4-none.json").read_text(encoding="utf-8"))
    if not window_report.get("ok"):
        raise RuntimeError("Standalone window test failed")
    for name in ("README.md", "AGENT.md", "CHANGELOG.md", "RELEASE.md"):
        shutil.copy2(root / name, pending / name)
    extension_source = root / "src/screenrec/browser_extension"
    with zipfile.ZipFile(pending / f"ScreenRec-{version}-browser-extension.zip", "w", compression=zipfile.ZIP_DEFLATED) as extension_archive:
        for path in sorted(extension_source.iterdir()):
            if path.is_file():
                extension_archive.write(path, arcname=path.name)
    from packaging.requirements import Requirement
    todo = (root / "requirements.txt").read_text().splitlines()
    deps = {}
    while todo:
        line = todo.pop().strip()
        if not line or line.startswith("#"):
            continue
        req = Requirement(line)
        if req.marker and not req.marker.evaluate({"extra": ""}):
            continue
        dist = metadata.distribution(req.name)
        name = dist.metadata["Name"]
        if name.lower() in deps:
            continue
        deps[name.lower()] = f"{name}=={dist.version}"
        todo.extend(dist.requires or [])
    (pending / "requirements-windows-lock.txt").write_text("\n".join(sorted(deps.values())) + "\n", encoding="utf-8")
    with zipfile.ZipFile(pending / f"ScreenRec-{version}-windows-x64.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("ScreenRec.exe", "README.md", "AGENT.md", "CHANGELOG.md", "RELEASE.md", "requirements-windows-lock.txt"):
            archive.write(pending / name, arcname=name)
        for path in sorted(extension_source.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"browser-extension/{path.name}")
    run(*git, "archive", "--format=zip", f"--output={pending / f'ScreenRec-{version}-source.zip'}", commit)
    manifest = {"version": version, "commit": commit, "built_at_utc": datetime.now(timezone.utc).isoformat(),
                "platform": platform.platform(), "python": platform.python_version(), "pyinstaller": metadata.version("pyinstaller"),
                "window_capture_test": {key: window_report[key] for key in ("ok", "frames", "seconds", "audio", "overlays")},
                "standalone_test": {key: report[key] for key in ("ok", "frames", "seconds", "audio", "overlays")}}
    (pending / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    hashes = []
    for path in sorted(pending.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            hashes.append(f"{digest}  {path.name}")
    (pending / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    pending.rename(target)
    print(f"Release ready: {target}\nCommit: {commit}")


if __name__ == "__main__":
    main()
