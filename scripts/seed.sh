#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"${GORILLA_PYTHON:-.venv/bin/python}" scripts/seed.py
