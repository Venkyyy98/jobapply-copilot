from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import io
import logging
import re
import shutil
import time
from datetime import datetime, timedelta, timezone

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse

from .company_news import build_company_issue_brief
from .compliance import check_for_unsupported_claims, check_profile_completeness
from .config import settings
from .cover_letter_render import render_cover_letter_text
from .exporters import (
    cover_letter_text_to_docx,
    cover_letter_text_to_pdf,
    resume_text_to_docx,
    resume_text_to_pdf,
    resume_layout_status,
    text_to_docx,
    text_to_pdf,
)
from .llm import LLMClient
from .llm import REFERRAL_DRAFTS_PROMPT
from .models import (
    AnalyzeJobRequest,
    AnalyzeJobResponse,
    AggregateCounts,
    CompanyIssueRequest,
    CompanyIssueResponse,
    DeleteUserDataResponse,
    DemoAnalyzeResponse,
    ExtensionTokenResponse,
    FindTargetsRequest,
    FindTargetsResponse,
    GenerateDocsRequest,
    GenerateDocsResponse,
    JobActionRequest,
    JobActionResponse,
    JobActionType,
    JobRecord,
    JobStatus,
    MarkAppliedRequest,
    MarkAppliedResponse,
    PrivateJobFeedItem,
    PublicJobFeedItem,
    PublicJobsResponse,
    ReferralContact,
    ReferralDraft,
    ReferralDraftsRequest,
    ReferralDraftsResponse,
    SavePacketRequest,
    SavePacketResponse,
    SyncJobRequest,
    SyncJobResponse,
    TestApiKeyResponse,
    TargetContact,
    UserDataExportResponse,
    UserJobListResponse,
    UserProfilePayload,
    UserProfileResponse,
    UserStatsResponse,
)
from .parser import parse_job_fields, validate_job_content
from .resume_render import render_resume_text
from .security import install_log_redaction, public_error_detail, redact_text
from .storage import Storage
from .target_finder import find_target_contacts
from .tailoring import (
    build_diff_summary,
    build_tailoring_plan,
    keyword_coverage_for_text,
    rewrite_project_descriptions,
    rewrite_selected_bullets,
)

install_log_redaction()
logger = logging.getLogger("app.jobapply")

app = FastAPI(title="JobApply Copilot Tailor Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
storage = Storage(settings.db_path, database_url=settings.database_url)
llm = LLMClient(settings.openai_api_key, key_source="server")
settings.output_dir.mkdir(parents=True, exist_ok=True)
_last_retention_cleanup = 0.0


@app.middleware("http")
async def beta_security_middleware(request: Request, call_next):
    request.state.started_at = time.time()
    global _last_retention_cleanup
    now = time.time()
    if now - _last_retention_cleanup > 3600:
        _last_retention_cleanup = now
        cleanup_generated_files()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled request error: %s", public_error_detail(exc))
        return JSONResponse(status_code=500, content={"detail": public_error_detail(exc)})
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    logger.warning("Validation error: %s", redact_text(exc))
    return JSONResponse(status_code=422, content={"detail": "Invalid request body or query parameters."})


def cleanup_generated_files() -> None:
    retention_hours = max(1, settings.generated_file_retention_hours)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    output_root = settings.output_dir.resolve()
    if not output_root.exists():
        return
    for child in output_root.iterdir():
        try:
            if not child.is_dir():
                continue
            modified = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                shutil.rmtree(child)
        except Exception as exc:
            logger.warning("Generated-file cleanup skipped one path: %s", public_error_detail(exc))


def delete_output_files(outputs: dict[str, Any]) -> None:
    output_root = settings.output_dir.resolve()
    parents_to_try: set[Path] = set()
    for raw_path in outputs.values():
        try:
            path = Path(str(raw_path)).resolve()
            if output_root in {path, *path.parents} and path.exists() and path.is_file():
                parents_to_try.add(path.parent)
                path.unlink()
        except Exception as exc:
            logger.warning("Generated-file delete skipped one file: %s", public_error_detail(exc))
    for parent in parents_to_try:
        try:
            if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except Exception:
            pass


def request_llm(x_openai_api_key: str | None = Header(default=None)) -> LLMClient:
    key = (x_openai_api_key or "").strip()
    if key:
        return LLMClient(key, key_source="byok")
    if settings.allow_server_llm_fallback:
        return llm
    return LLMClient("", key_source="none")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _profile_item_key(item: dict[str, Any], fallback: str = "") -> str:
    raw = str(item.get("name") or item.get("id") or fallback).lower()
    if "ragprobe" in raw:
        return "ragprobe"
    if "financial" in raw or "finbert" in raw or "portfolio prediction" in raw:
        return "financial_portfolio_prediction"
    if "sign language" in raw:
        return "sign_language_to_speech"
    if "pneumonia" in raw:
        return "pneumonia_detection"
    if "crime" in raw:
        return "crime_trends_analysis"
    if "sap intelliops" in raw or "sap cpi reliability" in raw:
        return "sap_intelliops"
    if "agentops" in raw:
        return "agentops_copilot"
    if "aws autonomous" in raw:
        return "aws_autonomous_agent"
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_")


def _merge_text_list(primary: list[Any], fallback: list[Any]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*primary, *fallback]:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            merged.append(text)
    return merged


def _merge_skill_groups(primary: list[Any], fallback: list[Any]) -> list[dict[str, Any]]:
    by_category: dict[str, dict[str, Any]] = {}
    for group in [*fallback, *primary]:
        if not isinstance(group, dict):
            continue
        category = str(group.get("category", "")).strip()
        if not category:
            continue
        current = by_category.setdefault(category, {"category": category, "items": []})
        current["items"] = _merge_text_list(list(current.get("items", []) or []), list(group.get("items", []) or []))
    return list(by_category.values())


def _normalize_current_location(candidate: dict[str, Any], base: dict[str, Any]) -> None:
    identity = candidate.setdefault("identity", {})
    current = str(identity.get("location", "")).strip()
    stale = re.search(r"\b(jersey city|hoboken|new jersey|new york|nyc)\b", current, re.I)
    if not current or stale:
        identity["location"] = str(base.get("identity", {}).get("location", "Antioch, CA")).strip() or "Antioch, CA"


def merge_candidate_profile_with_source(stored_candidate: dict[str, Any]) -> dict[str, Any]:
    base = load_yaml(settings.candidate_profile_path)
    candidate = {**base, **dict(stored_candidate or {})}
    candidate["identity"] = {**(base.get("identity", {}) or {}), **(stored_candidate.get("identity", {}) or {})}
    candidate["links"] = {**(base.get("links", {}) or {}), **(stored_candidate.get("links", {}) or {})}
    _normalize_current_location(candidate, base)

    if not str(candidate.get("summary", "")).strip() or "predictive      analytics" in str(candidate.get("summary", "")):
        candidate["summary"] = str(base.get("summary", "")).strip()
    candidate["skills"] = _merge_text_list(list(stored_candidate.get("skills", []) or []), list(base.get("skills", []) or []))
    candidate["certifications"] = _merge_text_list(
        list(stored_candidate.get("certifications", []) or []),
        list(base.get("certifications", []) or []),
    )

    projects: list[dict[str, Any]] = []
    seen_projects: set[str] = set()
    for project in [*(stored_candidate.get("academic_projects", []) or []), *(base.get("academic_projects", []) or [])]:
        if not isinstance(project, dict):
            continue
        key = _profile_item_key(project)
        if key and key not in seen_projects:
            seen_projects.add(key)
            projects.append(project)
    candidate["academic_projects"] = projects
    candidate["technical_skills"] = _merge_skill_groups(
        list(stored_candidate.get("technical_skills", []) or []),
        list(base.get("technical_skills", []) or []),
    )
    return candidate


def load_candidate_context(user: dict[str, str] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if user:
        profile = storage.get_user_profile(user["email"])
        if profile:
            return merge_candidate_profile_with_source(dict(profile.get("candidate_profile") or {})), dict(profile.get("preferences") or {})
        return {}, {}
    return load_yaml(settings.candidate_profile_path), load_yaml(settings.preferences_path)


def require_complete_candidate_context(user: dict[str, str] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate, preferences = load_candidate_context(user)
    if user and not candidate:
        raise HTTPException(
            status_code=409,
            detail="Complete your beta profile on the website before connecting the extension or generating documents.",
        )
    profile_issues = check_profile_completeness(candidate)
    if user and profile_issues:
        raise HTTPException(
            status_code=409,
            detail="Complete required profile fields before generating documents: " + "; ".join(profile_issues),
        )
    return candidate, preferences


def sanitize_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_")
    return cleaned[:60] if cleaned else fallback


def clean_role_for_filename(value: str) -> str:
    role = re.sub(r"\s+", " ", str(value or "").strip())
    role = re.sub(r"^(?:job\s+)?application\s+for\s+", "", role, flags=re.I).strip()
    role = re.sub(r"\s+job\s+in\s+.+$", "", role, flags=re.I).strip()
    role = re.sub(r"\s+in\s+[A-Z][A-Za-z .'-]+,\s*(?:\d{5}|[A-Z]{2})(?:\b.*)?$", "", role).strip()
    role = re.sub(r"\s+in\s+[A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+$", "", role).strip()
    role = re.sub(r"\s+\(?\b(?:remote|hybrid|onsite|on-site)\b\)?$", "", role, flags=re.I).strip()
    return role or "JobRole"


def semantic_document_filename(job: dict[str, Any], candidate: dict[str, Any], doc_type: str, suffix: str) -> str:
    role = sanitize_name(clean_role_for_filename(str(job.get("title", ""))), "JobRole")
    company = sanitize_name(str(job.get("company", "")), "Company")
    name = sanitize_name(str(candidate.get("identity", {}).get("full_name", "")), "Candidate")
    label = "CoverLetter" if "cover" in doc_type else "CV"
    return f"{role}_{company}_{name}_{label}{suffix}"


def _fallback_referral_draft(
    candidate: dict[str, Any],
    job: dict[str, Any],
    role: str,
    company: str,
    contact: ReferralContact,
) -> ReferralDraft:
    identity = candidate.get("identity", {})
    candidate_name = str(identity.get("full_name", "")).strip() or "Candidate"
    phone = str(identity.get("phone", "")).strip() or "(201) 275-6554"
    linkedin = str(candidate.get("links", {}).get("linkedin", "")).strip()
    linkedin = re.sub(r"^https?://(?:www\.)?", "", linkedin).rstrip("/") or "linkedin.com/in/venkateshcmudaliar"
    education = candidate.get("education", [])
    gpa = next((str(item.get("gpa", "")).strip() for item in education if item.get("gpa")), "3.82")
    corpus = " ".join(
        [
            str(job.get("title", "")),
            str(job.get("summary", "")),
            str(job.get("job_text", "")),
        ]
    ).lower()
    if any(term in corpus for term in ["agentic", "llm", "rag", "generative ai", "artificial intelligence"]):
        company_reason = (
            f"{company}'s work applying AI and agentic systems to production business workflows is especially compelling to me."
        )
        relevant_skill = "production LLM applications, RAG pipelines, and AI evaluation"
    elif any(term in corpus for term in ["etl", "pipeline", "data platform", "spark", "databricks"]):
        company_reason = (
            f"{company}'s focus on reliable data platforms and scalable analytics infrastructure is especially compelling to me."
        )
        relevant_skill = "building scalable data pipelines and data-quality systems"
    elif any(term in corpus for term in ["forecast", "predictive", "machine learning", "data scientist", "modeling"]):
        company_reason = (
            f"{company}'s use of data science and predictive modeling to improve products and decisions is especially compelling to me."
        )
        relevant_skill = "machine learning pipelines, model evaluation, and predictive analytics"
    else:
        company_reason = (
            f"{company}'s emphasis on using data and technology to deliver measurable customer impact is especially compelling to me."
        )
        relevant_skill = "applied machine learning, analytics, and production data systems"
    c_name = (contact.name or "there").strip()
    c_title = (contact.title or "").strip()
    first_name = c_name.split()[0] if c_name else "there"
    sender_first_name = candidate_name.split()[0] if candidate_name else "Venkatesh"
    relationship_type = str(contact.relationship_type or "beyond_network").strip()
    shared_context = str(contact.shared_context or "").strip()
    if relationship_type == "previous_company" and shared_context:
        connection_intro = f"having worked at {shared_context} as well"
        email_connection = f"We both have experience at {shared_context}, which is why I especially wanted to reach out."
    elif relationship_type == "school" and shared_context:
        connection_intro = f"having studied at {shared_context} as well"
        email_connection = f"As a fellow {shared_context} alum, I especially wanted to reach out."
    else:
        connection_intro = f"I came across your profile while researching {company}"
        email_connection = ""
    linkedin_note = (
        f"Hi {first_name}, {connection_intro}, I wanted to connect because I'm interested in the {role} role at {company} "
        f"and would appreciate any help getting in touch with the right contact. Thank you! {sender_first_name}."
    )
    linkedin_note = linkedin_note[:280]
    linkedin_followup = (
        f"Hi {first_name}, following up on my note about the {role} application at {company}. "
        "If you have a minute, I would really appreciate any guidance or referral."
    )[:280]
    email_subject = f"Referral request: {role} at {company}"
    connection_paragraph = f"{email_connection}\n\n" if email_connection else ""
    email_body = (
        f"Hi {first_name},\n\n"
        f"I applied for the {role} role at {company} and came across your profile while researching the team.\n\n"
        f"{connection_paragraph}"
        f"A bit about me - I'm completing my M.S. in Data Science at Stevens Institute (GPA {gpa}) and have 4+ years "
        "of experience building ML pipelines, LLM evaluation frameworks, and predictive analytics systems at Accenture "
        "and LTIMindtree. I'm also an AWS Certified AI Practitioner.\n\n"
        f"I'm genuinely interested in {company} specifically because {company_reason} "
        f"I think my background in {relevant_skill} maps well to what the team needs.\n\n"
        "If you're open to it, I'd love a 15-minute call to learn more about the team's work and what you look for in "
        "candidates - and if it makes sense, I'd really appreciate a referral.\n\n"
        "Either way, thank you for your time.\n\n"
        f"Best,\n{candidate_name}\n{phone} | {linkedin}"
    )
    return ReferralDraft(
        contact_name=c_name,
        contact_title=c_title,
        linkedin_url=str(contact.linkedin_url or "").strip(),
        email=str(contact.email or "").strip(),
        relationship_type=relationship_type,
        shared_context=shared_context,
        linkedin_note=linkedin_note,
        linkedin_followup=linkedin_followup,
        email_subject=email_subject,
        email_body=email_body,
    )


def require_token(x_jac_token: str | None = Header(default=None)) -> None:
    if not settings.jac_token:
        raise HTTPException(status_code=500, detail="Server token not configured (JAC_TOKEN missing).")
    if x_jac_token != settings.jac_token:
        raise HTTPException(status_code=401, detail="Invalid X-JAC-TOKEN")


def require_api_user(
    authorization: str | None = Header(default=None),
    x_jac_token: str | None = Header(default=None),
    x_web_user_email: str | None = Header(default=None),
    x_web_user_name: str | None = Header(default=""),
    x_web_user_image: str | None = Header(default=""),
) -> dict[str, str] | None:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        user = storage.get_user_by_extension_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired extension token.")
        return {
            "email": str(user["email"]),
            "name": str(user["name"]),
            "image_url": str(user["image_url"]),
        }
    if x_web_user_email:
        user = storage.get_or_create_user(
            x_web_user_email,
            name=x_web_user_name or "",
            image_url=x_web_user_image or "",
        )
        return {
            "email": str(user["email"]),
            "name": str(user["name"]),
            "image_url": str(user["image_url"]),
        }
    if settings.jac_token and x_jac_token == settings.jac_token:
        return None
    raise HTTPException(status_code=401, detail="Missing authenticated user token.")


def enforce_daily_quota(user: dict[str, str] | None, event_type: str, daily_limit: int) -> None:
    if not user:
        return
    if storage.quota_remaining(user["email"], event_type, daily_limit) <= 0:
        raise HTTPException(status_code=429, detail=f"Daily beta quota reached for {event_type}.")


def require_web_user(
    x_web_user_email: str | None = Header(default=None),
    x_web_user_name: str | None = Header(default=""),
    x_web_user_image: str | None = Header(default=""),
) -> dict[str, str]:
    email = (x_web_user_email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Missing authenticated web user.")
    return {
        "email": email,
        "name": (x_web_user_name or "").strip(),
        "image_url": (x_web_user_image or "").strip(),
    }


def get_web_user_optional(
    x_web_user_email: str | None = Header(default=None),
    x_web_user_name: str | None = Header(default=""),
    x_web_user_image: str | None = Header(default=""),
) -> dict[str, str] | None:
    email = (x_web_user_email or "").strip().lower()
    if not email:
        return None
    return {
        "email": email,
        "name": (x_web_user_name or "").strip(),
        "image_url": (x_web_user_image or "").strip(),
    }


def to_aggregate_counts(raw: dict[str, int] | None) -> AggregateCounts:
    raw = raw or {}
    return AggregateCounts(
        saved=int(raw.get("saved", 0)),
        analyzed=int(raw.get("analyzed", 0)),
        generated_docs=int(raw.get("generated_docs", 0)),
        applied=int(raw.get("applied", 0)),
        outreach_started=int(raw.get("outreach_started", 0)),
        interested=int(raw.get("interested", 0)),
    )


def to_public_job_feed_item(record: dict[str, Any]) -> PublicJobFeedItem:
    payload = dict(record)
    payload["aggregate_counts"] = to_aggregate_counts(record.get("aggregate_counts", {}))
    return PublicJobFeedItem(**payload)


def to_private_job_feed_item(record: dict[str, Any]) -> PrivateJobFeedItem:
    payload = dict(record)
    payload["aggregate_counts"] = to_aggregate_counts(record.get("aggregate_counts", {}))
    return PrivateJobFeedItem(**payload)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    storage.ping()
    return {"status": "ready", "database": "ok"}


@app.post("/ai/test_key", response_model=TestApiKeyResponse)
def test_api_key(active_llm: LLMClient = Depends(request_llm)) -> TestApiKeyResponse:
    if not active_llm.enabled:
        raise HTTPException(status_code=400, detail="Provide an OpenAI API key to test.")
    try:
        active_llm.test_key()
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=public_error_detail(exc)) from None
    return TestApiKeyResponse(ok=True, message="OpenAI API key authenticated successfully.")


@app.get("/demo/sample")
def demo_sample() -> dict[str, Any]:
    return {
        "notice": "Sample demo data only. No account, personal resume, or real API key is used.",
        "job": {
            "title": "AI Engineer Consultant",
            "company": "Demo Analytics Co",
            "location": "Remote",
            "job_text": (
                "Build production LLM applications, RAG pipelines, evaluation telemetry, secure APIs, "
                "and document-ingestion workflows for enterprise analytics teams."
            ),
        },
        "candidate": {
            "summary": "Sample AI/ML engineer profile with production LLM, RAG, and data engineering experience.",
            "projects": ["RAGProbe", "AgentOps Copilot", "SAP IntelliOps"],
        },
    }


@app.post("/demo/analyze_job", response_model=DemoAnalyzeResponse)
def demo_analyze_job(payload: AnalyzeJobRequest) -> DemoAnalyzeResponse:
    title = clean_role_for_filename(payload.title_hint or payload.page_title) or "AI Engineer Consultant"
    company = payload.company_hint.strip() or "Demo Analytics Co"
    return DemoAnalyzeResponse(
        job_id=0,
        title=title,
        company=company,
        location="Remote",
        summary="Sample analysis: this role emphasizes LLM applications, RAG, secure APIs, and evaluation telemetry.",
        fit_score=84,
        fit_reasons=[
            "Sample profile includes production LLM and RAG project experience.",
            "Sample profile includes data pipelines, API delivery, and cloud deployment language.",
            "Compliance note: demo output is intentionally not tied to real personal claims.",
        ],
        tailoring_plan=[
            "Highlight RAGProbe for retrieval evaluation and hallucination testing.",
            "Use AgentOps Copilot for agent/tool-calling and observability alignment.",
            "Keep SAP experience framed as enterprise data integration delivery.",
        ],
        suggested_bullets=["sample_exp_1", "sample_exp_2"],
        suggested_project_ids=["sample_ragprobe", "sample_agentops"],
        common_answers={"work_authorization": "Sample answer: confirm manually."},
        keyword_coverage_pct=78,
        matched_keywords=["LLM Applications", "RAG", "Evaluation", "APIs"],
        missing_keywords=["Vector Search", "LLMOps"],
        compliance_ready=True,
        compliance_notes=["Demo-generated output is sample content only."],
        ai_assisted=False,
        generation_warnings=["Demo mode used deterministic sample output and did not call an AI provider."],
    )


@app.post("/analyze_job", response_model=AnalyzeJobResponse)
def analyze_job(
    payload: AnalyzeJobRequest,
    api_user: dict[str, str] | None = Depends(require_api_user),
    active_llm: LLMClient = Depends(request_llm),
) -> AnalyzeJobResponse:
    enforce_daily_quota(api_user, "analyze_job", settings.analyze_daily_quota)
    candidate, preferences = require_complete_candidate_context(api_user)

    invalid_job_reason = validate_job_content(payload.job_text, payload.page_title, payload.company_hint)
    if invalid_job_reason:
        raise HTTPException(status_code=400, detail=invalid_job_reason)

    active_llm.reset_diagnostics()
    profile_issues = check_profile_completeness(candidate)
    job_fields = parse_job_fields(
        llm=active_llm,
        job_text=payload.job_text,
        page_title=payload.page_title,
        company_hint=payload.company_hint,
        url=payload.url,
        title_hint=payload.title_hint,
    )
    tailoring = build_tailoring_plan(active_llm, job_fields, candidate, preferences)
    llm_diagnostics = active_llm.diagnostics
    ai_assisted = bool(llm_diagnostics["successful_calls"])
    generation_warnings = []
    if active_llm.enabled and llm_diagnostics["attempts"] and not ai_assisted:
        generation_warnings.append(
            "AI analysis failed and heuristic fallback was used. Verify OPENAI_API_KEY/network and analyze again before generating final documents."
        )
    elif not active_llm.enabled:
        generation_warnings.append("No request API key was provided; heuristic analysis was used.")
    elif active_llm.key_source == "server":
        generation_warnings.append("Using server-configured OpenAI key because JAC_ALLOW_SERVER_LLM_FALLBACK is enabled.")
    record_id = storage.create_job(
        {
            "url": payload.url,
            "page_title": payload.page_title,
            "company_hint": payload.company_hint,
            "title": job_fields.get("title", "Unknown Role"),
            "company": job_fields.get("company", "Unknown Company"),
            "location": job_fields.get("location", ""),
            "job_text": payload.job_text,
            "summary": job_fields.get("summary", ""),
            "fit_score": tailoring["fit_score"],
            "company_issue_brief": {},
            "fit_reasons": tailoring["fit_reasons"],
            "tailoring_plan": tailoring["tailoring_plan"],
            "suggested_bullets": tailoring["suggested_bullets"],
            "common_answers": tailoring["common_answers"],
            "compliance_notes": profile_issues,
            "user_email": api_user["email"] if api_user else "",
            "user_name": api_user["name"] if api_user else "",
            "user_image_url": api_user["image_url"] if api_user else "",
        }
    )
    storage.update_job_analysis(
        record_id,
        {
            "title": job_fields.get("title", "Unknown Role"),
            "company": job_fields.get("company", "Unknown Company"),
            "summary": job_fields.get("summary", ""),
            "fit_score": tailoring["fit_score"],
            "company_issue_brief": {},
            "fit_reasons": tailoring["fit_reasons"],
            "tailoring_plan": tailoring["tailoring_plan"],
            "suggested_bullets": tailoring["suggested_bullets"],
            "common_answers": tailoring["common_answers"],
            "compliance_notes": profile_issues,
        },
    )
    feed_id = storage.upsert_feed_item_from_job(record_id)
    if api_user:
        if feed_id:
            storage.record_user_action(
                api_user["email"],
                feed_id,
                JobActionType.ANALYZED,
                metadata={"source_job_id": record_id},
                user_name=api_user["name"],
                image_url=api_user["image_url"],
            )
        storage.record_usage_event(api_user["email"], "analyze_job")

    return AnalyzeJobResponse(
        job_id=record_id,
        title=job_fields.get("title", "Unknown Role"),
        company=job_fields.get("company", "Unknown Company"),
        location=str(job_fields.get("location", "")),
        summary=job_fields.get("summary", ""),
        fit_score=tailoring["fit_score"],
        fit_reasons=tailoring["fit_reasons"],
        tailoring_plan=tailoring["tailoring_plan"],
        suggested_bullets=tailoring["suggested_bullets"],
        suggested_project_ids=list(tailoring.get("suggested_project_ids", [])),
        common_answers=tailoring["common_answers"],
        keyword_coverage_pct=int(tailoring.get("keyword_coverage_pct", 0)),
        matched_keywords=list(tailoring.get("matched_keywords", [])),
        missing_keywords=list(tailoring.get("missing_keywords", [])),
        compliance_ready=not profile_issues,
        compliance_notes=profile_issues,
        ai_assisted=ai_assisted,
        ai_key_source=active_llm.key_source,
        generation_warnings=generation_warnings,
    )


@app.post("/generate_docs", response_model=GenerateDocsResponse)
def generate_docs(
    payload: GenerateDocsRequest,
    api_user: dict[str, str] | None = Depends(require_api_user),
    active_llm: LLMClient = Depends(request_llm),
) -> GenerateDocsResponse:
    enforce_daily_quota(api_user, "generate_docs", settings.docs_daily_quota)
    if not payload.approve:
        raise HTTPException(status_code=400, detail="Explicit approve=true is required before final doc generation.")

    job = storage.get_job_for_user(payload.job_id, api_user["email"] if api_user else None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    invalid_job_reason = validate_job_content(
        str(job.get("job_text", "")),
        str(job.get("page_title", "")),
        str(job.get("company_hint", "")),
    )
    if invalid_job_reason:
        raise HTTPException(status_code=400, detail=f"Cannot generate documents: {invalid_job_reason}")

    candidate, preferences = require_complete_candidate_context(api_user)
    templates_dir = Path(__file__).resolve().parents[1] / "data" / "templates"

    storage.update_status(payload.job_id, JobStatus.APPROVED)
    active_llm.reset_diagnostics()

    selected_bullet_ids = list(job.get("suggested_bullets", []))
    all_bullet_ids = [
        b.get("id")
        for exp in candidate.get("experience", [])
        for b in exp.get("bullets", [])
        if isinstance(b, dict) and b.get("id")
    ]

    job_fields = parse_job_fields(
        llm=active_llm,
        job_text=str(job.get("job_text", "")),
        page_title=str(job.get("page_title", "")),
        company_hint=str(job.get("company_hint", "")),
        url=str(job.get("url", "")),
        title_hint=str(job.get("title", "")),
    )
    tailoring = build_tailoring_plan(active_llm, job_fields, candidate, preferences)
    selected_bullet_ids = selected_bullet_ids or list(tailoring.get("suggested_bullets", []))
    selected_project_ids = list(tailoring.get("suggested_project_ids", []))
    priority_keywords = list(tailoring.get("missing_keywords", []))[:12] if payload.boost_coverage else []
    rewritten_bullets = rewrite_selected_bullets(
        active_llm,
        candidate,
        job_fields,
        selected_bullet_ids,
        role_track=str(tailoring.get("role_track", "")),
        priority_keywords=priority_keywords,
    )
    rewritten_projects = rewrite_project_descriptions(
        active_llm,
        candidate,
        job_fields,
        priority_keywords=priority_keywords,
        selected_project_ids=selected_project_ids,
    )

    resume_text = render_resume_text(
        templates_dir=templates_dir,
        candidate_profile=candidate,
        job_fields=job_fields,
        selected_bullet_ids=selected_bullet_ids,
        suggested_project_ids=selected_project_ids,
        rewritten_bullets=rewritten_bullets,
        rewritten_projects=rewritten_projects,
        ats_keywords=tailoring.get("ats_keywords", []),
    )
    cover_text = render_cover_letter_text(
        templates_dir=templates_dir,
        llm=active_llm,
        candidate_profile=candidate,
        job_fields=job_fields,
        preferences=preferences,
        company_issue_brief={},
    )
    llm_diagnostics = active_llm.diagnostics
    ai_assisted = bool(llm_diagnostics["successful_calls"])
    generation_warnings = []
    if active_llm.enabled and llm_diagnostics["attempts"] and not ai_assisted:
        generation_warnings.append(
            "AI document tailoring failed and template fallback was used. Check the API connection before using these documents."
        )
    elif not active_llm.enabled:
        generation_warnings.append("No request API key was provided; template documents were generated.")
    elif active_llm.key_source == "server":
        generation_warnings.append("Using server-configured OpenAI key because JAC_ALLOW_SERVER_LLM_FALLBACK is enabled.")

    if resume_layout_status(resume_text) == "overflow":
        generation_warnings.append("This resume needs multiple pages at readable font sizes. Review the content length before applying.")

    compliance_issues = check_for_unsupported_claims(candidate, [resume_text, cover_text])
    if compliance_issues:
        return GenerateDocsResponse(
            job_id=payload.job_id,
            status=JobStatus.APPROVED,
            compliance_passed=False,
            compliance_issues=compliance_issues,
            files={},
            diff_summary=[],
            suggested_project_ids=selected_project_ids,
            keyword_coverage_pct=0,
            matched_keywords=[],
            missing_keywords=[],
            ai_assisted=ai_assisted,
            ai_key_source=active_llm.key_source,
            generation_warnings=generation_warnings,
        )

    job_dir = settings.output_dir / str(payload.job_id)
    resume_pdf = job_dir / "resume.pdf"
    cover_pdf = job_dir / "cover_letter.pdf"
    resume_docx = job_dir / "resume.docx"
    cover_docx = job_dir / "cover_letter.docx"
    resume_txt = job_dir / "resume.txt"
    cover_txt = job_dir / "cover_letter.txt"

    resume_txt.parent.mkdir(parents=True, exist_ok=True)
    resume_txt.write_text(resume_text, encoding="utf-8")
    cover_txt.write_text(cover_text, encoding="utf-8")
    try:
        resume_text_to_pdf(resume_text, resume_pdf)
        resume_text_to_docx(resume_text, resume_docx)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Resume formatting failed. Please retry generation; no plain-format substitute was returned.") from exc
    try:
        cover_letter_text_to_pdf(cover_text, cover_pdf)
    except Exception:
        text_to_pdf(cover_text, cover_pdf)
    try:
        cover_letter_text_to_docx(cover_text, cover_docx)
    except Exception:
        text_to_docx(cover_text, cover_docx)

    outputs = {
        "resume_pdf": str(resume_pdf),
        "cover_letter_pdf": str(cover_pdf),
        "resume_docx": str(resume_docx),
        "cover_letter_docx": str(cover_docx),
        "resume_txt": str(resume_txt),
        "cover_letter_txt": str(cover_txt),
    }

    storage.update_outputs(payload.job_id, outputs)
    storage.update_status(payload.job_id, JobStatus.DOCS_READY)
    storage.update_status(payload.job_id, JobStatus.PREFILL_READY)
    storage.upsert_feed_item_from_job(payload.job_id)
    if api_user:
        storage.record_usage_event(api_user["email"], "generate_docs")

    diff_summary = build_diff_summary(all_bullet_ids, selected_bullet_ids)
    coverage = keyword_coverage_for_text(list(tailoring.get("ats_keywords", [])), resume_text)
    original_fit = int(job.get("fit_score") or 0)
    tailored_fit_score = min(100, max(original_fit, round(original_fit + max(0, coverage.get("keyword_coverage_pct", 0) - int(job.get("keyword_coverage_pct") or 0)) * 0.35)))

    return GenerateDocsResponse(
        job_id=payload.job_id,
        status=JobStatus.PREFILL_READY,
        compliance_passed=True,
        compliance_issues=[],
        files={
            "resume_pdf": f"/download/{payload.job_id}/resume_pdf",
            "cover_letter_pdf": f"/download/{payload.job_id}/cover_letter_pdf",
            "resume_docx": f"/download/{payload.job_id}/resume_docx",
            "cover_letter_docx": f"/download/{payload.job_id}/cover_letter_docx",
            "resume_txt": f"/download/{payload.job_id}/resume_txt",
            "cover_letter_txt": f"/download/{payload.job_id}/cover_letter_txt",
        },
        diff_summary=diff_summary,
        suggested_project_ids=selected_project_ids,
        keyword_coverage_pct=int(coverage.get("keyword_coverage_pct", 0)),
        tailored_fit_score=tailored_fit_score,
        matched_keywords=list(coverage.get("matched_keywords", [])),
        missing_keywords=list(coverage.get("missing_keywords", [])),
        ai_assisted=ai_assisted,
        ai_key_source=active_llm.key_source,
        generation_warnings=generation_warnings,
    )


@app.post("/company_issue", response_model=CompanyIssueResponse)
def company_issue(
    payload: CompanyIssueRequest,
    api_user: dict[str, str] | None = Depends(require_api_user),
    active_llm: LLMClient = Depends(request_llm),
) -> CompanyIssueResponse:
    job = storage.get_job_for_user(payload.job_id, api_user["email"] if api_user else None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    brief = build_company_issue_brief(
        llm=active_llm,
        company=str(job.get("company", "") or job.get("company_hint", "")),
        job_title=str(job.get("title", "") or job.get("page_title", "")),
        job_text=str(job.get("job_text", "")),
    )
    storage.update_company_issue_brief(payload.job_id, brief)
    return CompanyIssueResponse(
        job_id=payload.job_id,
        company=str(job.get("company", "")),
        issue_brief=brief,
    )


@app.post("/find_targets", response_model=FindTargetsResponse)
def find_targets(payload: FindTargetsRequest, api_user: dict[str, str] | None = Depends(require_api_user)) -> FindTargetsResponse:
    enforce_daily_quota(api_user, "outreach", settings.outreach_daily_quota)
    if not settings.linkedin_discovery_enabled:
        raise HTTPException(
            status_code=403,
            detail="LinkedIn contact discovery is disabled for beta. Use draft generation with contacts you provide.",
        )
    job = storage.get_job_for_user(payload.job_id, api_user["email"] if api_user else None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    company = str(job.get("company", "") or job.get("company_hint", "")).strip()
    role = str(job.get("title", "")).strip()
    if not company:
        raise HTTPException(status_code=400, detail="Company is missing for this job.")

    candidate, _preferences = load_candidate_context(api_user)
    contacts, warnings = find_target_contacts(
        serpapi_key=settings.serpapi_key,
        hunter_api_key=settings.hunter_api_key,
        company=company,
        role=role,
        job_url=str(job.get("url", "")).strip(),
        candidate_profile=candidate,
        limit=12,
    )
    if api_user:
        storage.record_usage_event(api_user["email"], "outreach")
    return FindTargetsResponse(
        job_id=payload.job_id,
        company=company,
        role=role,
        contacts=[
            TargetContact(
                name=c.name,
                title=c.title,
                linkedin_url=c.linkedin_url,
                email=c.email,
                source=c.source,
                score=c.score,
                evidence=c.evidence[:3],
                relationship_type=c.relationship_type,
                shared_context=c.shared_context,
            )
            for c in contacts
        ],
        warnings=warnings,
    )


@app.post("/referral_drafts", response_model=ReferralDraftsResponse)
def referral_drafts(
    payload: ReferralDraftsRequest,
    api_user: dict[str, str] | None = Depends(require_api_user),
    active_llm: LLMClient = Depends(request_llm),
) -> ReferralDraftsResponse:
    enforce_daily_quota(api_user, "outreach", settings.outreach_daily_quota)
    job = storage.get_job_for_user(payload.job_id, api_user["email"] if api_user else None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not payload.contacts:
        raise HTTPException(status_code=400, detail="At least one contact is required.")

    candidate, _preferences = load_candidate_context(api_user)
    role = str(job.get("title", "")).strip() or "this role"
    company = str(job.get("company", "")).strip() or "the company"

    drafts: list[ReferralDraft] = [
        _fallback_referral_draft(candidate, job, role, company, contact)
        for contact in payload.contacts
    ]

    if active_llm.enabled:
        try:
            user_payload = (
                "CANDIDATE_NAME:\n"
                f"{str(candidate.get('identity', {}).get('full_name', '')).strip() or 'Candidate'}\n\n"
                "CANDIDATE_PROFILE:\n"
                f"{candidate}\n\n"
                "ROLE:\n"
                f"{role}\n\n"
                "COMPANY:\n"
                f"{company}\n\n"
                "JOB:\n"
                f"{job}\n\n"
                "CONTACTS:\n"
                f"{[c.model_dump() for c in payload.contacts]}"
            )
            response = active_llm.json_completion(REFERRAL_DRAFTS_PROMPT, user_payload)
            llm_drafts = response.get("drafts", [])
            merged: list[ReferralDraft] = []
            for idx, contact in enumerate(payload.contacts):
                base = drafts[idx]
                item = llm_drafts[idx] if idx < len(llm_drafts) and isinstance(llm_drafts[idx], dict) else {}
                note = str(item.get("linkedin_note", "")).strip() or base.linkedin_note
                if len(note) > 280:
                    note = note[:280]
                merged.append(
                    ReferralDraft(
                        contact_name=str(contact.name or base.contact_name),
                        contact_title=str(contact.title or base.contact_title),
                        linkedin_url=str(contact.linkedin_url or base.linkedin_url),
                        email=str(contact.email or base.email),
                        relationship_type=contact.relationship_type,
                        shared_context=contact.shared_context,
                        linkedin_note=base.linkedin_note if contact.relationship_type != "beyond_network" else note,
                        linkedin_followup=str(item.get("linkedin_followup", "")).strip() or base.linkedin_followup,
                        email_subject=base.email_subject,
                        email_body=base.email_body,
                    )
                )
            if merged:
                drafts = merged
        except Exception:
            pass

    if api_user:
        storage.record_usage_event(api_user["email"], "outreach")
    return ReferralDraftsResponse(
        job_id=payload.job_id,
        company=company,
        role=role,
        drafts=drafts,
    )


@app.get("/download/{job_id}/{doc_type}")
def download(job_id: int, doc_type: str, api_user: dict[str, str] | None = Depends(require_api_user)) -> FileResponse:
    job = storage.get_job_for_user(job_id, api_user["email"] if api_user else None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    outputs = job.get("outputs", {})
    path = outputs.get(doc_type)
    if not path:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(path)
    try:
        resolved_file = file_path.resolve()
        output_root = settings.output_dir.resolve()
        if output_root not in {resolved_file, *resolved_file.parents}:
            raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found") from None
    if not resolved_file.exists():
        raise HTTPException(status_code=404, detail="Document missing on disk")

    if resolved_file.suffix == ".pdf":
        media_type = "application/pdf"
    elif resolved_file.suffix == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "text/plain"
    candidate, _preferences = load_candidate_context(api_user)
    filename = semantic_document_filename(job, candidate, doc_type, resolved_file.suffix)
    return FileResponse(path=resolved_file, media_type=media_type, filename=filename)


@app.get("/jobs", response_model=list[JobRecord])
def jobs(api_user: dict[str, str] | None = Depends(require_api_user)) -> list[JobRecord]:
    return [JobRecord(**row) for row in storage.list_jobs(limit=20, user_email=api_user["email"] if api_user else None)]


@app.post("/sync_job", response_model=SyncJobResponse)
def sync_job(
    payload: SyncJobRequest,
    api_user: dict[str, str] | None = Depends(require_api_user),
    web_user: dict[str, str] | None = Depends(get_web_user_optional),
) -> SyncJobResponse:
    source_job_id = payload.source_job_id
    if source_job_id:
        if not storage.get_job_for_user(source_job_id, api_user["email"] if api_user else None):
            raise HTTPException(status_code=404, detail="Source job not found")
        feed_id = storage.upsert_feed_item_from_job(source_job_id, visibility=payload.visibility)
    else:
        feed_id = storage.upsert_feed_item_from_payload(payload.model_dump())
    if not feed_id:
        raise HTTPException(status_code=500, detail="Unable to sync job feed item.")
    action_user = web_user or api_user
    if action_user:
        storage.record_user_action(
            action_user["email"],
            feed_id,
            JobActionType.ANALYZED,
            metadata={"source_job_id": source_job_id},
            user_name=action_user["name"],
            image_url=action_user["image_url"],
        )
    item = storage.get_feed_item(feed_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feed item not found after sync.")
    item["aggregate_counts"] = storage.get_action_counts([feed_id]).get(feed_id, {})
    return SyncJobResponse(job_feed_item=to_public_job_feed_item(item))


@app.get("/web/jobs", response_model=PublicJobsResponse)
def web_jobs(
    q: str = Query(default=""),
    role_family: str = Query(default=""),
    location: str = Query(default=""),
    fit_min: int | None = Query(default=None),
    fit_max: int | None = Query(default=None),
    sort: str = Query(default="newest"),
    limit: int = Query(default=24, ge=1, le=100),
) -> PublicJobsResponse:
    items = storage.list_public_feed_items(
        search=q,
        role_family=role_family,
        location=location,
        fit_min=fit_min,
        fit_max=fit_max,
        sort=sort,
        limit=limit,
    )
    families = sorted({item.get("role_family", "Other") for item in items if item.get("role_family")})
    return PublicJobsResponse(
        items=[to_public_job_feed_item(item) for item in items],
        available_role_families=families,
        total=len(items),
    )


@app.get("/web/jobs/{job_feed_item_id}", response_model=PublicJobFeedItem)
def web_job_detail(job_feed_item_id: int) -> PublicJobFeedItem:
    item = storage.get_feed_item(job_feed_item_id)
    if not item or item.get("visibility") != "public":
        raise HTTPException(status_code=404, detail="Job not found")
    item["aggregate_counts"] = storage.get_action_counts([job_feed_item_id]).get(job_feed_item_id, {})
    return to_public_job_feed_item(item)


@app.post("/web/jobs/{job_feed_item_id}/actions", response_model=JobActionResponse)
def web_job_action(
    job_feed_item_id: int,
    payload: JobActionRequest,
    web_user: dict[str, str] = Depends(require_web_user),
) -> JobActionResponse:
    item = storage.get_feed_item(job_feed_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Job not found")
    action = storage.record_user_action(
        web_user["email"],
        job_feed_item_id,
        payload.action,
        metadata=payload.metadata,
        user_name=web_user["name"],
        image_url=web_user["image_url"],
    )
    counts = storage.get_action_counts([job_feed_item_id]).get(job_feed_item_id, {})
    return JobActionResponse(
        job_feed_item_id=job_feed_item_id,
        action=payload.action,
        recorded_at=str(action["updated_at"]),
        aggregate_counts=to_aggregate_counts(counts),
    )


@app.get("/web/me/jobs", response_model=UserJobListResponse)
def web_me_jobs(
    q: str = Query(default=""),
    status: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    limit: int = Query(default=500, ge=1, le=2000),
    web_user: dict[str, str] = Depends(require_web_user),
) -> UserJobListResponse:
    items = storage.list_user_jobs(
        web_user["email"],
        search=q,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return UserJobListResponse(
        items=[to_private_job_feed_item(item) for item in items],
        total=len(items),
        activity=storage.get_application_activity(web_user["email"], date_from=date_from, date_to=date_to),
    )


@app.get("/web/me/stats", response_model=UserStatsResponse)
def web_me_stats(web_user: dict[str, str] = Depends(require_web_user)) -> UserStatsResponse:
    return UserStatsResponse(**storage.get_user_stats(web_user["email"]))


@app.get("/web/me/profile", response_model=UserProfileResponse)
def web_me_profile(web_user: dict[str, str] = Depends(require_web_user)) -> UserProfileResponse:
    profile = storage.get_user_profile(web_user["email"])
    if not profile:
        return UserProfileResponse(
            candidate_profile={},
            preferences={},
            profile_complete=False,
            compliance_notes=["Complete your candidate profile before generating documents."],
            updated_at="",
        )
    candidate = merge_candidate_profile_with_source(dict(profile.get("candidate_profile") or {}))
    notes = check_profile_completeness(candidate)
    return UserProfileResponse(
        candidate_profile=candidate,
        preferences=dict(profile.get("preferences") or {}),
        profile_complete=not notes,
        compliance_notes=notes,
        updated_at=str(profile.get("updated_at", "")),
    )


@app.put("/web/me/profile", response_model=UserProfileResponse)
def update_web_me_profile(
    payload: UserProfilePayload,
    web_user: dict[str, str] = Depends(require_web_user),
) -> UserProfileResponse:
    profile = storage.upsert_user_profile(
        web_user["email"],
        payload.candidate_profile,
        payload.preferences,
        user_name=web_user["name"],
        image_url=web_user["image_url"],
    )
    candidate = merge_candidate_profile_with_source(dict(profile.get("candidate_profile") or {}))
    notes = check_profile_completeness(candidate)
    return UserProfileResponse(
        candidate_profile=candidate,
        preferences=dict(profile.get("preferences") or {}),
        profile_complete=not notes,
        compliance_notes=notes,
        updated_at=str(profile.get("updated_at", "")),
    )


@app.post("/web/me/extension-token", response_model=ExtensionTokenResponse)
def issue_web_extension_token(web_user: dict[str, str] = Depends(require_web_user)) -> ExtensionTokenResponse:
    require_complete_candidate_context(web_user)
    token = storage.issue_extension_token(
        web_user["email"],
        user_name=web_user["name"],
        image_url=web_user["image_url"],
    )
    return ExtensionTokenResponse(
        token=str(token["token"]),
        api_base_url=settings.public_api_base_url,
        created_at=str(token["created_at"]),
    )


@app.get("/web/me/export", response_model=UserDataExportResponse)
def export_web_me_data(web_user: dict[str, str] = Depends(require_web_user)) -> UserDataExportResponse:
    data = storage.export_user_data(web_user["email"])
    profile = data.get("profile")
    profile_response = None
    if profile:
        notes = check_profile_completeness(dict(profile.get("candidate_profile") or {}))
        profile_response = UserProfileResponse(
            candidate_profile=dict(profile.get("candidate_profile") or {}),
            preferences=dict(profile.get("preferences") or {}),
            profile_complete=not notes,
            compliance_notes=notes,
            updated_at=str(profile.get("updated_at", "")),
        )
    return UserDataExportResponse(
        user={
            "email": str(data["user"].get("email", "")),
            "name": str(data["user"].get("name", "")),
            "image_url": str(data["user"].get("image_url", "")),
        },
        profile=profile_response,
        jobs=list(data.get("jobs", [])),
        actions=list(data.get("actions", [])),
    )


@app.delete("/web/me", response_model=DeleteUserDataResponse)
def delete_web_me_data(web_user: dict[str, str] = Depends(require_web_user)) -> DeleteUserDataResponse:
    exported = storage.export_user_data(web_user["email"])
    for job in exported.get("jobs", []):
        delete_output_files(dict(job.get("outputs") or {}))
    storage.delete_user_data(web_user["email"])
    return DeleteUserDataResponse(deleted=True, message="Your beta workspace data has been deleted.")


@app.delete("/web/me/jobs/{job_feed_item_id}", response_model=DeleteUserDataResponse)
def delete_web_me_job(
    job_feed_item_id: int,
    web_user: dict[str, str] = Depends(require_web_user),
) -> DeleteUserDataResponse:
    result = storage.delete_user_job(web_user["email"], job_feed_item_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="Tracked job not found for this user.")
    delete_output_files(dict(result.get("outputs") or {}))
    return DeleteUserDataResponse(deleted=True, message="Tracked application and generated documents were deleted.")


@app.post("/save_packet", response_model=SavePacketResponse)
def save_packet(payload: SavePacketRequest, api_user: dict[str, str] | None = Depends(require_api_user)) -> SavePacketResponse:
    job = storage.get_job_for_user(payload.job_id, api_user["email"] if api_user else None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    outputs = job.get("outputs", {})
    resume_src = outputs.get("resume_pdf")
    cover_src = outputs.get("cover_letter_pdf")
    resume_docx_src = outputs.get("resume_docx")
    cover_docx_src = outputs.get("cover_letter_docx")
    if not resume_src or not cover_src:
        raise HTTPException(status_code=400, detail="Documents not generated yet.")

    candidate, _preferences = load_candidate_context(api_user)
    role = sanitize_name(clean_role_for_filename(str(job.get("title", ""))), "JobRole")
    company = sanitize_name(str(job.get("company", "")), "Company")
    name = sanitize_name(str(candidate.get("identity", {}).get("full_name", "")), "Candidate")
    folder = settings.packet_dir / f"{role}_{company}_{name}"
    folder.mkdir(parents=True, exist_ok=True)

    resume_dst = folder / f"{role}_{company}_{name}_CV.pdf"
    cover_dst = folder / f"{role}_{company}_{name}_CoverLetter.pdf"
    shutil.copy2(Path(resume_src), resume_dst)
    shutil.copy2(Path(cover_src), cover_dst)
    files = {
        "resume_pdf": str(resume_dst),
        "cover_letter_pdf": str(cover_dst),
    }
    if resume_docx_src and Path(resume_docx_src).exists():
        resume_docx_dst = folder / f"{role}_{company}_{name}_CV.docx"
        shutil.copy2(Path(resume_docx_src), resume_docx_dst)
        files["resume_docx"] = str(resume_docx_dst)
    if cover_docx_src and Path(cover_docx_src).exists():
        cover_docx_dst = folder / f"{role}_{company}_{name}_CoverLetter.docx"
        shutil.copy2(Path(cover_docx_src), cover_docx_dst)
        files["cover_letter_docx"] = str(cover_docx_dst)
    return SavePacketResponse(
        job_id=payload.job_id,
        folder=str(folder),
        files=files,
    )


@app.post("/mark_applied", response_model=MarkAppliedResponse)
def mark_applied(payload: MarkAppliedRequest, api_user: dict[str, str] | None = Depends(require_api_user)) -> MarkAppliedResponse:
    job = storage.get_job_for_user(payload.job_id, api_user["email"] if api_user else None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    storage.update_status(payload.job_id, JobStatus.MANUAL_SUBMISSION_REQUIRED)
    feed_id = storage.upsert_feed_item_from_job(payload.job_id)
    if api_user and feed_id:
        storage.record_user_action(
            api_user["email"],
            feed_id,
            JobActionType.APPLIED,
            metadata={"source_job_id": payload.job_id, "notes": payload.notes},
            user_name=api_user["name"],
            image_url=api_user["image_url"],
        )
    updated = storage.get_job(payload.job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found after update")
    return MarkAppliedResponse(
        job_id=payload.job_id,
        status=JobStatus.MANUAL_SUBMISSION_REQUIRED,
        applied_at=str(updated.get("updated_at", "")),
    )


@app.get("/export/applied.csv")
def export_applied_csv(api_user: dict[str, str] | None = Depends(require_api_user)) -> Response:
    rows = storage.list_applied_jobs(user_email=api_user["email"] if api_user else None)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["job_id", "title", "company", "url", "fit_score", "status", "created_at", "applied_at"])
    for row in rows:
        writer.writerow(
            [
                row.get("id", ""),
                row.get("title", ""),
                row.get("company", ""),
                row.get("url", ""),
                row.get("fit_score", ""),
                row.get("status", ""),
                row.get("created_at", ""),
                row.get("updated_at", ""),
            ]
        )
    csv_text = output.getvalue()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobapply-applied-jobs.csv"},
    )
