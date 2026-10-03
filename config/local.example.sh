# Optional overrides; no secrets belong in this file.
export GORILLA_PYTHON="$PWD/.venv/bin/python"
export GORILLA_MODEL_PYTHON="$PWD/.model-venv/bin/python"
# For an existing CUDA installation, set LD_LIBRARY_PATH outside source control.
# The gateway reads a generated secret from state/worker-token.
