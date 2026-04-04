#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".env" ]; then
  echo "Missing .env. Create it first (cp .env.example .env)."
  exit 1
fi

TOKEN="$(grep '^JAC_TOKEN=' .env | cut -d '=' -f2-)"
if [ -z "$TOKEN" ] || [ "$TOKEN" = "replace_with_random_shared_token" ]; then
  echo "Set a real JAC_TOKEN in .env before running smoke test."
  exit 1
fi

echo "== Health check =="
curl -sS http://127.0.0.1:8787/health

echo

echo "== Analyze sample job =="
curl -sS -X POST http://127.0.0.1:8787/analyze_job \
  -H "Content-Type: application/json" \
  -H "X-JAC-TOKEN: $TOKEN" \
  -d '{
    "url": "https://example.com/jobs/sample-data-engineer",
    "page_title": "Data Engineer | Example Inc",
    "company_hint": "Example Inc",
    "job_text": "Data Engineer role. Responsibilities: build reliable ETL pipelines, collaborate with analytics, and improve data quality. Requirements: Python, SQL, cloud services, and strong communication."
  }'

echo
