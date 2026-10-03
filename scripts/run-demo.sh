#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${GORILLA_PYTHON:-.venv/bin/python}" scripts/run_demo.py
