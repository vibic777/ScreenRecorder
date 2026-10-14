"""Two-second screen/audio diagnostic; artifacts stay in the workspace."""
import multiprocessing
import sys
from pathlib import Path

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.prefix == sys.base_prefix:
        raise SystemExit("Use .venv Python")
    from screenrec.selftest import run
    output = Path(__file__).resolve().parents[1] / ".test-output"
    raise SystemExit(run(["--output", str(output), *sys.argv[1:]]))
