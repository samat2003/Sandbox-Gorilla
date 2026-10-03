#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"${GORILLA_PYTHON:-.venv/bin/python}" -m unittest discover -s tests -v
if command -v node >/dev/null 2>&1; then node tests/observer_polling.js; fi
