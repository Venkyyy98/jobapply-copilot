from __future__ import annotations

import json
import secrets
import hashlib
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .models import JobActionType, JobStatus

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None

APPLICATION_TIMEZONE = ZoneInfo("America/New_York")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _local_action_date(value: str) -> str:
    return _parse_utc_timestamp(value).astimezone(APPLICATION_TIMEZONE).date().isoformat()


def _local_date_utc_bounds(value: str) -> tuple[str, str]:
    local_start = datetime.fromisoformat(value).replace(tzinfo=APPLICATION_TIMEZONE)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc).isoformat(), local_end.astimezone(timezone.utc).isoformat()


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def _classify_role_family(title: str, job_text: str) -> str:
    title_text = (title or "").lower()
    haystack = f"{title} {job_text}".lower()
    if "data scientist" in title_text or "data science" in title_text or "machine learning" in title_text:
        return "Data Scientist"
    if "data analyst" in title_text or "business analyst" in title_text:
        return "Data Analyst"
    if "data engineer" in title_text or "analytics engineer" in title_text:
        return "Data Engineer"
    if "sap" in title_text or "cpi" in title_text or "s/4" in title_text:
        return "SAP"
    if "sap" in haystack or "cpi" in haystack or "s/4" in haystack or "integration suite" in haystack:
        return "SAP"
    if "data scientist" in haystack or "machine learning" in haystack:
        return "Data Scientist"
    if "data engineer" in haystack or "etl" in haystack or "pipeline" in haystack:
        return "Data Engineer"
    if "data analyst" in haystack or "business intelligence" in haystack or "analytics" in haystack:
        return "Data Analyst"
    return "Other"


def _infer_work_mode(job_text: str, page_title: str, url: str) -> str:
    haystack = f"{job_text} {page_title} {url}".lower()
    if "remote" in haystack:
        return "Remote"
    if "hybrid" in haystack:
        return "Hybrid"
    if "onsite" in haystack or "on-site" in haystack or "on site" in haystack:
        return "Onsite"
    return "Unknown"


def _infer_location(title: str, page_title: str, company_hint: str, job_text: str) -> str:
    sources = [title, page_title, company_hint]
    for source in sources:
        parts = [part.strip() for part in (source or "").split("|") if part.strip()]
        if len(parts) > 1:
            return parts[-1]
    lines = [line.strip() for line in (job_text or "").splitlines() if line.strip()]
    for line in lines[:12]:
        if "," in line and len(line) <= 80:
            return line
    return ""


class _PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.connection.__exit__(*args)

    def execute(self, query: str, params=()):
        query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        query = query.replace("INSERT OR IGNORE", "INSERT")
        query = query.replace("datetime(a.created_at)", "a.created_at")
        query = query.replace("datetime(?)", "%s")
        query = query.replace("?", "%s")
        if "INSERT INTO users" in query and "ON CONFLICT" not in query:
            query = query.rstrip() + " ON CONFLICT (email) DO NOTHING"
        if "PRAGMA table_info(jobs)" in query:
            query = "SELECT column_name AS name FROM information_schema.columns WHERE table_name = 'jobs'"
            params = ()
        return self.connection.execute(query, params)


class Storage:
    def __init__(self, db_path: Path, database_url: str = ""):
        self.db_path = db_path
        self.database_url = database_url
        if not self.database_url:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        if self.database_url:
            if psycopg is None:
                raise RuntimeError("psycopg is required when DATABASE_URL is configured")
            return _PostgresConnection(psycopg.connect(self.database_url, row_factory=dict_row))
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    page_title TEXT NOT NULL,
                    company_hint TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    job_text TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    fit_score INTEGER,
                    company_issue_brief TEXT NOT NULL,
                    fit_reasons TEXT NOT NULL,
                    tailoring_plan TEXT NOT NULL,
                    suggested_bullets TEXT NOT NULL,
                    common_answers TEXT NOT NULL,
                    compliance_notes TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outputs TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "company_issue_brief" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN company_issue_brief TEXT NOT NULL DEFAULT '{}'")
            if "owner_user_id" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN owner_user_id INTEGER")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    image_url TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT 'google',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id INTEGER PRIMARY KEY,
                    candidate_profile TEXT NOT NULL DEFAULT '{}',
                    preferences TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extension_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL DEFAULT 'Chrome extension',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_feed_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_job_id INTEGER,
                    source_url TEXT NOT NULL,
                    canonical_key TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL DEFAULT '',
                    work_mode TEXT NOT NULL DEFAULT 'Unknown',
                    role_family TEXT NOT NULL DEFAULT 'Other',
                    page_title TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    job_text_excerpt TEXT NOT NULL DEFAULT '',
                    fit_score INTEGER,
                    fit_reasons TEXT NOT NULL DEFAULT '[]',
                    tailoring_plan TEXT NOT NULL DEFAULT '[]',
                    suggested_bullets TEXT NOT NULL DEFAULT '[]',
                    suggested_project_ids TEXT NOT NULL DEFAULT '[]',
                    matched_keywords TEXT NOT NULL DEFAULT '[]',
                    missing_keywords TEXT NOT NULL DEFAULT '[]',
                    keyword_coverage_pct INTEGER NOT NULL DEFAULT 0,
                    compliance_ready INTEGER NOT NULL DEFAULT 0,
                    compliance_notes TEXT NOT NULL DEFAULT '[]',
                    visibility TEXT NOT NULL DEFAULT 'public',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_job_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    job_feed_item_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, job_feed_item_id, action_type)
                )
                """
            )

    def ping(self) -> None:
        with self._conn() as conn:
            conn.execute("SELECT 1").fetchone()

    def create_job(self, payload: dict[str, Any]) -> int:
        now = utc_now_iso()
        owner_user_id = None
        if payload.get("user_email"):
            owner_user_id = self.get_or_create_user(
                str(payload.get("user_email", "")),
                name=str(payload.get("user_name", "")),
                image_url=str(payload.get("user_image_url", "")),
            )["id"]
        with self._conn() as conn:
            insert_sql = """
                INSERT INTO jobs (
                    url, page_title, company_hint, title, company, job_text, summary, fit_score,
                    company_issue_brief, fit_reasons, tailoring_plan, suggested_bullets, common_answers, compliance_notes,
                    status, outputs, owner_user_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            if self.database_url:
                insert_sql += " RETURNING id"
            cur = conn.execute(
                insert_sql,
                (
                    payload.get("url", ""),
                    payload.get("page_title", ""),
                    payload.get("company_hint", ""),
                    payload.get("title", "Unknown Role"),
                    payload.get("company", "Unknown Company"),
                    payload.get("job_text", ""),
                    payload.get("summary", ""),
                    payload.get("fit_score"),
                    json.dumps(payload.get("company_issue_brief", {})),
                    json.dumps(payload.get("fit_reasons", [])),
                    json.dumps(payload.get("tailoring_plan", [])),
                    json.dumps(payload.get("suggested_bullets", [])),
                    json.dumps(payload.get("common_answers", {})),
                    json.dumps(payload.get("compliance_notes", [])),
                    JobStatus.NEW.value,
                    json.dumps({}),
                    owner_user_id,
                    now,
                    now,
                ),
            )
            job_id = int(cur.fetchone()["id"] if self.database_url else cur.lastrowid)
        self.upsert_feed_item_from_job(job_id)
        return job_id

    def update_job_analysis(self, job_id: int, analysis: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET title = ?, company = ?, summary = ?, fit_score = ?, company_issue_brief = ?, fit_reasons = ?,
                    tailoring_plan = ?, suggested_bullets = ?, common_answers = ?, compliance_notes = ?,
                    status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    analysis["title"],
                    analysis["company"],
                    analysis["summary"],
                    analysis["fit_score"],
                    json.dumps(analysis.get("company_issue_brief", {})),
                    json.dumps(analysis["fit_reasons"]),
                    json.dumps(analysis["tailoring_plan"]),
                    json.dumps(analysis["suggested_bullets"]),
                    json.dumps(analysis["common_answers"]),
                    json.dumps(analysis["compliance_notes"]),
                    JobStatus.ANALYZED.value,
                    utc_now_iso(),
                    job_id,
                ),
            )
        self.upsert_feed_item_from_job(job_id)

    def update_status(self, job_id: int, status: JobStatus) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, utc_now_iso(), job_id),
            )

    def update_outputs(self, job_id: int, outputs: dict[str, str]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET outputs = ?, updated_at = ? WHERE id = ?",
                (json.dumps(outputs), utc_now_iso(), job_id),
            )

    def update_company_issue_brief(self, job_id: int, issue_brief: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET company_issue_brief = ?, updated_at = ? WHERE id = ?",
                (json.dumps(issue_brief or {}), utc_now_iso(), job_id),
            )

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        record = dict(row)
        for key in ["fit_reasons", "tailoring_plan", "suggested_bullets", "common_answers", "compliance_notes", "outputs", "company_issue_brief"]:
            record[key] = _json_loads(record[key], {} if key in {"common_answers", "outputs", "company_issue_brief"} else [])
        return record

    def get_job_for_user(self, job_id: int, user_email: str | None) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        if not user_email:
            return job
        user = self.get_or_create_user(user_email)
        if job.get("owner_user_id") not in {None, user["id"]}:
            return None
        return job

    def list_jobs(self, limit: int = 20, user_email: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if user_email:
            user = self.get_or_create_user(user_email)
            where = "WHERE owner_user_id = ?"
            params.append(user["id"])
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT id, url, title, company, status, created_at, updated_at, fit_score, company_issue_brief, outputs FROM jobs {where} ORDER BY id DESC LIMIT ?",
                tuple(params + [limit]),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(row)
            rec["company_issue_brief"] = _json_loads(rec["company_issue_brief"], {})
            rec["outputs"] = _json_loads(rec["outputs"], {})
            items.append(rec)
        return items

    def list_applied_jobs(self, user_email: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [JobStatus.MANUAL_SUBMISSION_REQUIRED.value]
        owner_clause = ""
        if user_email:
            user = self.get_or_create_user(user_email)
            owner_clause = "AND owner_user_id = ?"
            params.append(user["id"])
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, url, title, company, status, created_at, updated_at, fit_score
                FROM jobs
                WHERE status = ?
                """ + owner_clause + """
                ORDER BY updated_at DESC
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_feed_item_from_job(self, job_id: int, visibility: str = "private") -> int | None:
        job = self.get_job(job_id)
        if not job:
            return None
        title = str(job.get("title", "")).strip() or str(job.get("page_title", "")).strip() or "Unknown Role"
        company = str(job.get("company", "")).strip() or str(job.get("company_hint", "")).strip() or "Unknown Company"
        location = _infer_location(title, str(job.get("page_title", "")), str(job.get("company_hint", "")), str(job.get("job_text", "")))
        canonical_key = "|".join(
            [
                _normalize_text(company),
                _normalize_text(title),
                _normalize_text(location),
                _normalize_text(str(job.get("url", ""))),
            ]
        )
        now = utc_now_iso()
        summary = str(job.get("summary", "")).strip()
        job_text = str(job.get("job_text", "")).strip()
        excerpt = " ".join(job_text.split())[:1200]
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM job_feed_items WHERE canonical_key = ?",
                (canonical_key,),
            ).fetchone()
            payload = (
                job_id,
                str(job.get("url", "")).strip(),
                canonical_key,
                title,
                company,
                location,
                _infer_work_mode(job_text, str(job.get("page_title", "")), str(job.get("url", ""))),
                _classify_role_family(title, job_text),
                str(job.get("page_title", "")).strip(),
                summary,
                excerpt,
                job.get("fit_score"),
                json.dumps(job.get("fit_reasons", [])),
                json.dumps(job.get("tailoring_plan", [])),
                json.dumps(job.get("suggested_bullets", [])),
                json.dumps(job.get("suggested_project_ids", [])),
                json.dumps(job.get("matched_keywords", [])),
                json.dumps(job.get("missing_keywords", [])),
                int(job.get("keyword_coverage_pct", 0) or 0),
                1 if not job.get("compliance_notes") else 0,
                json.dumps(job.get("compliance_notes", [])),
                visibility,
                now,
                now,
            )
            if existing:
                conn.execute(
                    """
                    UPDATE job_feed_items
                    SET source_job_id = ?, source_url = ?, canonical_key = ?, title = ?, company = ?, location = ?,
                        work_mode = ?, role_family = ?, page_title = ?, summary = ?, job_text_excerpt = ?,
                        fit_score = ?, fit_reasons = ?, tailoring_plan = ?, suggested_bullets = ?,
                        suggested_project_ids = ?, matched_keywords = ?, missing_keywords = ?,
                        keyword_coverage_pct = ?, compliance_ready = ?, compliance_notes = ?, visibility = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    payload[:-2] + (now, existing["id"]),
                )
                return int(existing["id"])
            cur = conn.execute(
                """
                INSERT INTO job_feed_items (
                    source_job_id, source_url, canonical_key, title, company, location, work_mode, role_family,
                    page_title, summary, job_text_excerpt, fit_score, fit_reasons, tailoring_plan,
                    suggested_bullets, suggested_project_ids, matched_keywords, missing_keywords,
                    keyword_coverage_pct, compliance_ready, compliance_notes, visibility, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            return int(cur.lastrowid)

    def upsert_feed_item_from_payload(self, payload: dict[str, Any]) -> int:
        title = str(payload.get("title", "")).strip() or str(payload.get("page_title", "")).strip() or "Unknown Role"
        company = str(payload.get("company", "")).strip() or str(payload.get("company_hint", "")).strip() or "Unknown Company"
        location = str(payload.get("location", "")).strip() or _infer_location(
            title,
            str(payload.get("page_title", "")),
            str(payload.get("company_hint", "")),
            str(payload.get("job_text", "")),
        )
        source_url = str(payload.get("url", "")).strip()
        canonical_key = "|".join(
            [
                _normalize_text(company),
                _normalize_text(title),
                _normalize_text(location),
                _normalize_text(source_url),
            ]
        )
        now = utc_now_iso()
        job_text = str(payload.get("job_text", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        excerpt = " ".join(job_text.split())[:1200]
        row_payload = (
            payload.get("source_job_id"),
            source_url,
            canonical_key,
            title,
            company,
            location,
            str(payload.get("work_mode", "")).strip() or _infer_work_mode(job_text, str(payload.get("page_title", "")), source_url),
            str(payload.get("role_family", "")).strip() or _classify_role_family(title, job_text),
            str(payload.get("page_title", "")).strip(),
            summary,
            excerpt,
            payload.get("fit_score"),
            json.dumps(payload.get("fit_reasons", [])),
            json.dumps(payload.get("tailoring_plan", [])),
            json.dumps(payload.get("suggested_bullets", [])),
            json.dumps(payload.get("suggested_project_ids", [])),
            json.dumps(payload.get("matched_keywords", [])),
            json.dumps(payload.get("missing_keywords", [])),
            int(payload.get("keyword_coverage_pct", 0) or 0),
            1 if payload.get("compliance_ready") else 0,
            json.dumps(payload.get("compliance_notes", [])),
            str(payload.get("visibility", "private")).strip() or "private",
            now,
            now,
        )
        with self._conn() as conn:
            existing = conn.execute("SELECT id FROM job_feed_items WHERE canonical_key = ?", (canonical_key,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE job_feed_items
                    SET source_job_id = ?, source_url = ?, canonical_key = ?, title = ?, company = ?, location = ?,
                        work_mode = ?, role_family = ?, page_title = ?, summary = ?, job_text_excerpt = ?,
                        fit_score = ?, fit_reasons = ?, tailoring_plan = ?, suggested_bullets = ?,
                        suggested_project_ids = ?, matched_keywords = ?, missing_keywords = ?,
                        keyword_coverage_pct = ?, compliance_ready = ?, compliance_notes = ?, visibility = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    row_payload[:-2] + (now, existing["id"]),
                )
                return int(existing["id"])
            cur = conn.execute(
                """
                INSERT INTO job_feed_items (
                    source_job_id, source_url, canonical_key, title, company, location, work_mode, role_family,
                    page_title, summary, job_text_excerpt, fit_score, fit_reasons, tailoring_plan,
                    suggested_bullets, suggested_project_ids, matched_keywords, missing_keywords,
                    keyword_coverage_pct, compliance_ready, compliance_notes, visibility, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row_payload,
            )
            return int(cur.lastrowid)

    def get_feed_item(self, feed_item_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM job_feed_items WHERE id = ?", (feed_item_id,)).fetchone()
        if not row:
            return None
        return self._decode_feed_item(dict(row))

    def get_feed_item_by_job(self, job_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM job_feed_items WHERE source_job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return self._decode_feed_item(dict(row))

    def get_or_create_user(self, email: str, name: str = "", image_url: str = "", provider: str = "google") -> dict[str, Any]:
        normalized_email = (email or "").strip().lower()
        now = utc_now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (email, name, image_url, provider, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (normalized_email, name.strip(), image_url.strip(), provider.strip() or "google", now, now),
            )
            conn.execute(
                """
                UPDATE users
                SET name = COALESCE(NULLIF(?, ''), name),
                    image_url = COALESCE(NULLIF(?, ''), image_url),
                    provider = COALESCE(NULLIF(?, ''), provider),
                    updated_at = ?
                WHERE email = ?
                """,
                (name.strip(), image_url.strip(), provider.strip() or "google", now, normalized_email),
            )
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
        return dict(row)

    def upsert_user_profile(
        self,
        user_email: str,
        candidate_profile: dict[str, Any],
        preferences: dict[str, Any],
        user_name: str = "",
        image_url: str = "",
    ) -> dict[str, Any]:
        user = self.get_or_create_user(user_email, name=user_name, image_url=image_url)
        now = utc_now_iso()
        with self._conn() as conn:
            existing = conn.execute("SELECT user_id FROM user_profiles WHERE user_id = ?", (user["id"],)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE user_profiles
                    SET candidate_profile = ?, preferences = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (json.dumps(candidate_profile or {}), json.dumps(preferences or {}), now, user["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_profiles (user_id, candidate_profile, preferences, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user["id"], json.dumps(candidate_profile or {}), json.dumps(preferences or {}), now, now),
                )
            row = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user["id"],)).fetchone()
        return self._decode_profile(dict(row))

    def get_user_profile(self, user_email: str) -> dict[str, Any] | None:
        user = self.get_or_create_user(user_email)
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user["id"],)).fetchone()
        if not row:
            return None
        return self._decode_profile(dict(row))

    def issue_extension_token(self, user_email: str, user_name: str = "", image_url: str = "") -> dict[str, Any]:
        user = self.get_or_create_user(user_email, name=user_name, image_url=image_url)
        token = f"jac_live_{secrets.token_urlsafe(32)}"
        now = utc_now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO extension_tokens (user_id, token_hash, created_at)
                VALUES (?, ?, ?)
                """,
                (user["id"], _token_hash(token), now),
            )
        return {"token": token, "created_at": now}

    def get_user_by_extension_token(self, token: str) -> dict[str, Any] | None:
        if not token.strip():
            return None
        now = utc_now_iso()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT u.*
                FROM extension_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_hash IN (?, ?) AND t.revoked_at IS NULL
                """,
                (_token_hash(token), token.strip()),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE extension_tokens SET last_used_at = ? WHERE token_hash IN (?, ?)",
                    (now, _token_hash(token), token.strip()),
                )
        return dict(row) if row else None

    def count_usage_since(self, user_email: str, event_type: str, since: datetime) -> int:
        user = self.get_or_create_user(user_email)
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM usage_events
                WHERE user_id = ? AND event_type = ? AND created_at >= ?
                """,
                (user["id"], event_type, since.isoformat()),
            ).fetchone()
        return int(row["count"] if row else 0)

    def record_usage_event(self, user_email: str, event_type: str) -> None:
        user = self.get_or_create_user(user_email)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO usage_events (user_id, event_type, created_at) VALUES (?, ?, ?)",
                (user["id"], event_type, utc_now_iso()),
            )

    def quota_remaining(self, user_email: str, event_type: str, daily_limit: int) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=1)
        return max(0, daily_limit - self.count_usage_since(user_email, event_type, since))

    def export_user_data(self, user_email: str) -> dict[str, Any]:
        user = self.get_or_create_user(user_email)
        profile = self.get_user_profile(user_email)
        with self._conn() as conn:
            job_rows = conn.execute("SELECT * FROM jobs WHERE owner_user_id = ? ORDER BY updated_at DESC", (user["id"],)).fetchall()
            action_rows = conn.execute(
                """
                SELECT f.title, f.company, f.source_url, a.action_type, a.metadata, a.created_at, a.updated_at
                FROM user_job_actions a
                JOIN job_feed_items f ON f.id = a.job_feed_item_id
                WHERE a.user_id = ?
                ORDER BY a.updated_at DESC
                """,
                (user["id"],),
            ).fetchall()
        jobs = []
        for row in job_rows:
            rec = dict(row)
            for key in ["fit_reasons", "tailoring_plan", "suggested_bullets", "common_answers", "compliance_notes", "outputs", "company_issue_brief"]:
                rec[key] = _json_loads(rec[key], {} if key in {"common_answers", "outputs", "company_issue_brief"} else [])
            jobs.append(rec)
        actions = [dict(row) for row in action_rows]
        for action in actions:
            action["metadata"] = _json_loads(action.get("metadata"), {})
        return {"user": dict(user), "profile": profile, "jobs": jobs, "actions": actions}

    def delete_user_data(self, user_email: str) -> None:
        user = self.get_or_create_user(user_email)
        with self._conn() as conn:
            conn.execute("DELETE FROM usage_events WHERE user_id = ?", (user["id"],))
            conn.execute("DELETE FROM extension_tokens WHERE user_id = ?", (user["id"],))
            conn.execute("DELETE FROM user_job_actions WHERE user_id = ?", (user["id"],))
            conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (user["id"],))
            conn.execute("DELETE FROM jobs WHERE owner_user_id = ?", (user["id"],))

    def delete_user_job(self, user_email: str, job_feed_item_id: int) -> dict[str, Any]:
        user = self.get_or_create_user(user_email)
        with self._conn() as conn:
            item = conn.execute(
                "SELECT source_job_id FROM job_feed_items WHERE id = ?",
                (job_feed_item_id,),
            ).fetchone()
            if not item:
                return {"deleted": False, "outputs": {}}
            action = conn.execute(
                "SELECT id FROM user_job_actions WHERE user_id = ? AND job_feed_item_id = ?",
                (user["id"], job_feed_item_id),
            ).fetchone()
            source_job_id = item["source_job_id"]
            outputs: dict[str, Any] = {}
            job_deleted = False
            if source_job_id:
                job = conn.execute(
                    "SELECT outputs FROM jobs WHERE id = ? AND owner_user_id = ?",
                    (source_job_id, user["id"]),
                ).fetchone()
                if job:
                    outputs = _json_loads(job["outputs"], {})
                    conn.execute("DELETE FROM jobs WHERE id = ? AND owner_user_id = ?", (source_job_id, user["id"]))
                    job_deleted = True
            conn.execute("DELETE FROM user_job_actions WHERE user_id = ? AND job_feed_item_id = ?", (user["id"], job_feed_item_id))
            return {"deleted": bool(action or job_deleted), "outputs": outputs}

    def _decode_profile(self, record: dict[str, Any]) -> dict[str, Any]:
        record["candidate_profile"] = _json_loads(record.get("candidate_profile"), {})
        record["preferences"] = _json_loads(record.get("preferences"), {})
        return record

    def record_user_action(
        self,
        user_email: str,
        job_feed_item_id: int,
        action_type: JobActionType,
        metadata: dict[str, Any] | None = None,
        user_name: str = "",
        image_url: str = "",
    ) -> dict[str, Any]:
        user = self.get_or_create_user(user_email, name=user_name, image_url=image_url)
        now = utc_now_iso()
        with self._conn() as conn:
            existing = conn.execute(
                """
                SELECT id FROM user_job_actions
                WHERE user_id = ? AND job_feed_item_id = ? AND action_type = ?
                """,
                (user["id"], job_feed_item_id, action_type.value),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE user_job_actions
                    SET metadata = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (json.dumps(metadata or {}), now, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_job_actions (user_id, job_feed_item_id, action_type, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user["id"], job_feed_item_id, action_type.value, json.dumps(metadata or {}), now, now),
                )
            row = conn.execute(
                """
                SELECT * FROM user_job_actions
                WHERE user_id = ? AND job_feed_item_id = ? AND action_type = ?
                """,
                (user["id"], job_feed_item_id, action_type.value),
            ).fetchone()
        action = dict(row)
        action["metadata"] = _json_loads(action["metadata"], {})
        return action

    def get_action_counts(self, job_feed_item_ids: list[int]) -> dict[int, dict[str, int]]:
        if not job_feed_item_ids:
            return {}
        placeholders = ",".join("?" for _ in job_feed_item_ids)
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT job_feed_item_id, action_type, COUNT(*) AS count
                FROM user_job_actions
                WHERE job_feed_item_id IN ({placeholders})
                GROUP BY job_feed_item_id, action_type
                """,
                tuple(job_feed_item_ids),
            ).fetchall()
        counts: dict[int, dict[str, int]] = {item_id: {} for item_id in job_feed_item_ids}
        for row in rows:
            counts[int(row["job_feed_item_id"])][str(row["action_type"]).lower()] = int(row["count"])
        return counts

    def list_public_feed_items(
        self,
        *,
        search: str = "",
        role_family: str = "",
        location: str = "",
        fit_min: int | None = None,
        fit_max: int | None = None,
        sort: str = "newest",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        conditions = ["visibility = 'public'"]
        params: list[Any] = []
        if search.strip():
            q = f"%{search.strip().lower()}%"
            conditions.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(summary) LIKE ?)")
            params.extend([q, q, q])
        if role_family.strip():
            conditions.append("role_family = ?")
            params.append(role_family.strip())
        if location.strip():
            conditions.append("LOWER(location) LIKE ?")
            params.append(f"%{location.strip().lower()}%")
        if fit_min is not None:
            conditions.append("COALESCE(fit_score, 0) >= ?")
            params.append(fit_min)
        if fit_max is not None:
            conditions.append("COALESCE(fit_score, 0) <= ?")
            params.append(fit_max)
        order_map = {
            "fit": "COALESCE(fit_score, 0) DESC, updated_at DESC",
            "most_applied": "updated_at DESC",
            "most_saved": "updated_at DESC",
            "newest": "updated_at DESC",
        }
        order_by = order_map.get(sort, order_map["newest"])
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM job_feed_items
                WHERE {' AND '.join(conditions)}
                ORDER BY {order_by}
                LIMIT ?
                """,
                tuple(params + [limit]),
            ).fetchall()
        items = [self._decode_feed_item(dict(row)) for row in rows]
        counts = self.get_action_counts([item["id"] for item in items])
        for item in items:
            item["aggregate_counts"] = counts.get(item["id"], {})
        if sort in {"most_applied", "most_saved"}:
            key = "applied" if sort == "most_applied" else "saved"
            items.sort(key=lambda item: (item["aggregate_counts"].get(key, 0), item["updated_at"]), reverse=True)
        return items

    def list_user_jobs(
        self,
        user_email: str,
        *,
        search: str = "",
        status: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        user = self.get_or_create_user(user_email)
        search_term = search.strip().lower()
        search_sql = ""
        search_params: list[Any] = []
        if search_term:
            search_sql = " AND (LOWER(f.title) LIKE ? OR LOWER(f.company) LIKE ?)"
            search_value = f"%{search_term}%"
            search_params.extend([search_value, search_value])
        date_conditions = []
        date_params: list[Any] = []
        if date_from.strip():
            start_utc, _ = _local_date_utc_bounds(date_from.strip())
            date_conditions.append("datetime(a.created_at) >= datetime(?)")
            date_params.append(start_utc)
        if date_to.strip():
            _, end_utc = _local_date_utc_bounds(date_to.strip())
            date_conditions.append("datetime(a.created_at) < datetime(?)")
            date_params.append(end_utc)
        date_sql = "".join(f" AND {condition}" for condition in date_conditions)
        with self._conn() as conn:
            if status.strip():
                rows = conn.execute(
                    f"""
                    SELECT f.*, a.action_type AS user_action, a.metadata AS user_action_metadata, a.updated_at AS action_updated_at
                    FROM user_job_actions a
                    JOIN job_feed_items f ON f.id = a.job_feed_item_id
                    WHERE a.user_id = ? AND a.action_type = ?{date_sql}{search_sql}
                    ORDER BY a.updated_at DESC
                    LIMIT ?
                    """,
                    tuple([user["id"], status.strip().upper(), *date_params, *search_params, limit]),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""
                    WITH ranked_actions AS (
                        SELECT
                            a.*,
                            ROW_NUMBER() OVER (
                                PARTITION BY a.job_feed_item_id
                                ORDER BY
                                    CASE a.action_type
                                        WHEN 'APPLIED' THEN 1
                                        WHEN 'GENERATED_DOCS' THEN 2
                                        WHEN 'OUTREACH_STARTED' THEN 3
                                        WHEN 'SAVED' THEN 4
                                        WHEN 'INTERESTED' THEN 5
                                        WHEN 'ANALYZED' THEN 6
                                        ELSE 9
                                    END,
                                    a.updated_at DESC
                            ) AS rn,
                            MAX(a.updated_at) OVER (PARTITION BY a.job_feed_item_id) AS latest_action_at
                        FROM user_job_actions a
                        WHERE a.user_id = ?{date_sql}
                    )
                    SELECT f.*, a.action_type AS user_action, a.metadata AS user_action_metadata, a.updated_at AS action_updated_at
                    FROM ranked_actions a
                    JOIN job_feed_items f ON f.id = a.job_feed_item_id
                    WHERE a.rn = 1{search_sql}
                    ORDER BY a.latest_action_at DESC
                    LIMIT ?
                    """,
                    tuple([user["id"], *date_params, *search_params, limit]),
                ).fetchall()
        items = [self._decode_feed_item(dict(row)) for row in rows]
        counts = self.get_action_counts([item["id"] for item in items])
        action_dates = self.get_user_action_dates(user["id"], [item["id"] for item in items])
        for item in items:
            item["aggregate_counts"] = counts.get(item["id"], {})
            item["action_dates"] = action_dates.get(item["id"], {})
        return items

    def get_user_action_dates(self, user_id: int, job_feed_item_ids: list[int]) -> dict[int, dict[str, str]]:
        if not job_feed_item_ids:
            return {}
        placeholders = ",".join("?" for _ in job_feed_item_ids)
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT job_feed_item_id, action_type, created_at
                FROM user_job_actions
                WHERE user_id = ? AND job_feed_item_id IN ({placeholders})
                """,
                tuple([user_id, *job_feed_item_ids]),
            ).fetchall()
        dates: dict[int, dict[str, str]] = {item_id: {} for item_id in job_feed_item_ids}
        for row in rows:
            dates[int(row["job_feed_item_id"])][str(row["action_type"]).lower()] = str(row["created_at"])
        return dates

    def get_application_activity(self, user_email: str, date_from: str = "", date_to: str = "") -> dict[str, Any]:
        user = self.get_or_create_user(user_email)
        now = datetime.now(APPLICATION_TIMEZONE)
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT action_type, created_at
                FROM user_job_actions
                WHERE user_id = ? AND action_type IN ('ANALYZED', 'APPLIED')
                """,
                (user["id"],),
            ).fetchall()

        def empty_counts() -> dict[str, int]:
            return {"checked": 0, "applied": 0}

        periods = {
            "today": empty_counts(),
            "week": empty_counts(),
            "month": empty_counts(),
            "all": empty_counts(),
        }
        daily_map: dict[str, dict[str, int]] = {}
        filtered = empty_counts()
        for row in rows:
            action_date = _local_action_date(str(row["created_at"]))
            kind = "checked" if row["action_type"] == JobActionType.ANALYZED.value else "applied"
            periods["all"][kind] += 1
            if action_date >= month_start.isoformat():
                periods["month"][kind] += 1
            if action_date >= week_start.isoformat():
                periods["week"][kind] += 1
            if action_date == today.isoformat():
                periods["today"][kind] += 1
            daily_map.setdefault(action_date, empty_counts())[kind] += 1
            if date_from.strip() and action_date < date_from.strip():
                continue
            if date_to.strip() and action_date > date_to.strip():
                continue
            filtered[kind] += 1

        daily = [
            {"date": action_date, **counts}
            for action_date, counts in sorted(daily_map.items(), reverse=True)[:31]
        ]
        return {"periods": periods, "filtered": filtered, "daily": daily}

    def get_user_stats(self, user_email: str) -> dict[str, Any]:
        user = self.get_or_create_user(user_email)
        with self._conn() as conn:
            action_rows = conn.execute(
                """
                SELECT action_type, COUNT(*) AS count
                FROM user_job_actions
                WHERE user_id = ?
                GROUP BY action_type
                """,
                (user["id"],),
            ).fetchall()
            recent_rows = conn.execute(
                """
                SELECT f.title, f.company, a.action_type, a.updated_at
                FROM user_job_actions a
                JOIN job_feed_items f ON f.id = a.job_feed_item_id
                WHERE a.user_id = ?
                ORDER BY a.updated_at DESC
                LIMIT 8
                """,
                (user["id"],),
            ).fetchall()
        action_counts = {str(row["action_type"]).lower(): int(row["count"]) for row in action_rows}
        return {
            "user": {
                "email": str(user["email"]),
                "name": str(user["name"]),
                "image_url": str(user["image_url"]),
            },
            "counts": action_counts,
            "recent_activity": [dict(row) for row in recent_rows],
            "application_activity": self.get_application_activity(user_email),
        }

    def _decode_feed_item(self, record: dict[str, Any]) -> dict[str, Any]:
        for key in [
            "fit_reasons",
            "tailoring_plan",
            "suggested_bullets",
            "suggested_project_ids",
            "matched_keywords",
            "missing_keywords",
            "compliance_notes",
        ]:
            record[key] = _json_loads(record.get(key), [])
        if "user_action_metadata" in record:
            record["user_action_metadata"] = _json_loads(record.get("user_action_metadata"), {})
        record["compliance_ready"] = bool(record.get("compliance_ready"))
        record["slug"] = _slugify(f"{record.get('title', '')}-{record.get('company', '')}") or f"job-{record.get('id', 0)}"
        return record
