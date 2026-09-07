#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
echo "Starting API at http://127.0.0.1:8787"
exec ./.venv/bin/uvicorn server.app.main:app --host 127.0.0.1 --port 8787
