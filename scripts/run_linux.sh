#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv-linux/bin/activate
exec python -m screenrec.main
