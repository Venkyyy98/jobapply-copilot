from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from app import main
from app.llm import LLMClient
from app.security import redact_text
from app.storage import Storage


def test_extension_tokens_are_hashed_at_rest(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    issued = storage.issue_extension_token("alice@example.com")

    with sqlite3.connect(tmp_path / "jobapply.db") as conn:
        row = conn.execute("SELECT token_hash FROM extension_tokens").fetchone()

    assert issued["token"].startswith("jac_live_")
    assert row is not None
    assert row[0] != issued["token"]
    assert len(row[0]) == 64
    assert storage.get_user_by_extension_token(issued["token"])["email"] == "alice@example.com"


def test_redaction_removes_api_keys_and_tokens():
    raw = "Authorization: Bearer jac_live_abc123456789000 X-OpenAI-API-Key: sk-secretvalue123456789"
    redacted = redact_text(raw)

    assert "jac_live_" not in redacted
    assert "sk-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_demo_mode_is_deterministic_and_does_not_require_auth():
    client = TestClient(main.app)
    response = client.post(
        "/demo/analyze_job",
        json={
            "title_hint": "AI Engineer",
            "company_hint": "Demo Co",
            "job_text": "Build production LLM applications, RAG pipelines, secure APIs, and evaluation telemetry.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["demo"] is True
    assert payload["job_id"] == 0
    assert payload["ai_assisted"] is False
    assert "Demo mode" in payload["generation_warnings"][0]


def test_byok_header_creates_request_scoped_client_without_storage(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "jobapply.db")
    monkeypatch.setattr(main, "storage", storage)
    active = main.request_llm(x_openai_api_key="sk-testbyok123456789")

    assert isinstance(active, LLMClient)
    assert active.enabled
    with sqlite3.connect(tmp_path / "jobapply.db") as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    assert rows
    with open(tmp_path / "jobapply.db", "rb") as db_file:
        assert b"sk-testbyok" not in db_file.read()


def test_delete_user_job_is_scoped_to_owner(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    job_id = storage.create_job(
        {
            "url": "https://example.com/job",
            "title": "Data Engineer",
            "company": "Example Co",
            "job_text": "Data engineer role with Python, SQL, Spark, and AWS.",
            "user_email": "alice@example.com",
        }
    )
    feed_item = storage.get_feed_item_by_job(job_id)
    assert feed_item is not None

    bob_delete = storage.delete_user_job("bob@example.com", feed_item["id"])
    alice_delete = storage.delete_user_job("alice@example.com", feed_item["id"])

    assert bob_delete["deleted"] is False
    assert alice_delete["deleted"] is True
