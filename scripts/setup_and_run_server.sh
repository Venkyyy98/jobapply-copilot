#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade setuptools wheel
if ! pip install -e './server[dev]'; then
  echo "Editable install with build isolation failed, retrying without build isolation..."
  pip install --no-build-isolation -e './server[dev]'
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Update OPENAI_API_KEY and JAC_TOKEN before use."
fi

echo "Starting FastAPI on http://127.0.0.1:8787"
uvicorn server.app.main:app --host 127.0.0.1 --port 8787 --reload
