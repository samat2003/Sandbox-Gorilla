#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
exec "${GORILLA_MODEL_PYTHON:-.model-venv/bin/python}" scripts/run_mini.py "$@"
