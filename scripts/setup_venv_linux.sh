#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv-linux/bin/python ]; then python3 -m venv .venv-linux; fi
source .venv-linux/bin/activate
python -m pip install -e .
