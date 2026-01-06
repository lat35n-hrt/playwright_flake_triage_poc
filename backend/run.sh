#!/usr/bin/env bash
set -euo pipefail

# venv: source .venv/bin/activate is expected
export PYTHONPATH="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8000}"

uvicorn app.main:app --host 127.0.0.1 --port "${PORT}" --reload
