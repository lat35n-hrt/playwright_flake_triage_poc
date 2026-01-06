#!/usr/bin/env bash
set -euo pipefail

# venv: source .venv/bin/activate enabled in advanced
export PYTHONPATH="$(cd "$(dirname "$0")" && pwd)"

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
