#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${GORILLA_PYTHON:-.venv/bin/python}" -m gorilla.server --host 127.0.0.1 --port 8091
