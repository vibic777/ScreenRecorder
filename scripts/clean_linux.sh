#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf build dist .test-output ./*.spec
find . -type d \( -name '__pycache__' -o -name '*.egg-info' \) -prune -exec rm -rf {} +
echo "Project cleaned."
