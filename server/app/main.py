from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import io
import re
import shutil

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from .company_news import build_company_issue_brief
from .compliance import check_for_unsupported_claims, check_profile_completeness
from .config import settings
from .cover_letter_render import render_cover_letter_text
from .exporters import (
    cover_letter_text_to_docx,
    cover_letter_text_to_pdf,
    resume_text_to_docx,
    resume_text_to_pdf,
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
    TargetContact,
    UserJobListResponse,
    UserStatsResponse,
)
from .parser import parse_job_fields
from .resume_render import render_resume_text
from .storage import Storage
from .target_finder import find_target_contacts
from .tailoring import (
    build_diff_summary,
    build_tailoring_plan,
    keyword_coverage_for_text,
    rewrite_project_descriptions,
    rewrite_selected_bullets,
)

app = FastAPI(title="JobApply Copilot Tailor Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
storage = Storage(settings.db_path)
llm = LLMClient(settings.openai_api_key)
settings.output_dir.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def sanitize_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_")
    return cleaned[:60] if cleaned else fallback


def _fallback_referral_draft(
    candidate_name: str,
    role: str,
    company: str,
    contact: ReferralContact,
) -> ReferralDraft:
    c_name = (contact.name or "there").strip()
    c_title = (contact.title or "").strip()
    title_suffix = f", {c_title}" if c_title else ""
    linkedin_note = (
        f"Hi {c_name}, I applied for the {role} role at {company} and found your profile while researching the team. "
        "If you are open to it, I would value a quick referral or guidance on how to best position my application. Thank you."
    )
    linkedin_note = linkedin_note[:280]
    linkedin_followup = (
        f"Hi {c_name}, following up on my note about the {role} application at {company}. "
        "If you have a minute, I would really appreciate any guidance or referral."
    )[:280]
    email_subject = f"Referral request: {role} at {company}"
    email_body = (
        f"Hi {c_name}{title_suffix},\n\n"
        f"I hope you are doing well. I recently applied for the {role} position at {company} and wanted to reach out respectfully.\n\n"
        "If you feel my background could be relevant, I would be grateful for a referral or any guidance on the hiring process. "
        "I can share my tailored resume and cover letter if helpful.\n\n"
        f"Thank you for your time,\n{candidate_name}"
    )
    return ReferralDraft(
        contact_name=c_name,
        contact_title=c_title,
        linkedin_url=str(contact.linkedin_url or "").strip(),
        email=str(contact.email or "").strip(),
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


@app.post("/analyze_job", response_model=AnalyzeJobResponse, dependencies=[Depends(require_token)])
def analyze_job(payload: AnalyzeJobRequest) -> AnalyzeJobResponse:
    candidate = load_yaml(settings.candidate_profile_path)
    preferences = load_yaml(settings.preferences_path)

    profile_issues = check_profile_completeness(candidate)
    job_fields = parse_job_fields(
        llm=llm,
        job_text=payload.job_text,
        page_title=payload.page_title,
        company_hint=payload.company_hint,
        url=payload.url,
    )
    tailoring = build_tailoring_plan(llm, job_fields, candidate, preferences)
    record_id = storage.create_job(
        {
            "url": payload.url,
            "page_title": payload.page_title,
            "company_hint": payload.company_hint,
            "title": job_fields.get("title", "Unknown Role"),
            "company": job_fields.get("company", "Unknown Company"),
            "job_text": payload.job_text,
            "summary": job_fields.get("summary", ""),
            "fit_score": tailoring["fit_score"],
            "company_issue_brief": {},
            "fit_reasons": tailoring["fit_reasons"],
            "tailoring_plan": tailoring["tailoring_plan"],
            "suggested_bullets": tailoring["suggested_bullets"],
            "common_answers": tailoring["common_answers"],
            "compliance_notes": profile_issues,
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
    storage.upsert_feed_item_from_job(record_id)

    return AnalyzeJobResponse(
        job_id=record_id,
        title=job_fields.get("title", "Unknown Role"),
        company=job_fields.get("company", "Unknown Company"),
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
    )


@app.post("/generate_docs", response_model=GenerateDocsResponse, dependencies=[Depends(require_token)])
def generate_docs(payload: GenerateDocsRequest) -> GenerateDocsResponse:
    if not payload.approve:
        raise HTTPException(status_code=400, detail="Explicit approve=true is required before final doc generation.")

    job = storage.get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidate = load_yaml(settings.candidate_profile_path)
    preferences = load_yaml(settings.preferences_path)
    templates_dir = Path(__file__).resolve().parents[1] / "data" / "templates"

    storage.update_status(payload.job_id, JobStatus.APPROVED)

    selected_bullet_ids = list(job.get("suggested_bullets", []))
    all_bullet_ids = [
        b.get("id")
        for exp in candidate.get("experience", [])
        for b in exp.get("bullets", [])
        if isinstance(b, dict) and b.get("id")
    ]

    job_fields = parse_job_fields(
        llm=llm,
        job_text=str(job.get("job_text", "")),
        page_title=str(job.get("page_title", "")),
        company_hint=str(job.get("company_hint", "")),
        url=str(job.get("url", "")),
    )
    tailoring = build_tailoring_plan(llm, job_fields, candidate, preferences)
    selected_bullet_ids = selected_bullet_ids or list(tailoring.get("suggested_bullets", []))
    selected_project_ids = list(tailoring.get("suggested_project_ids", []))
    priority_keywords = list(tailoring.get("missing_keywords", []))[:12] if payload.boost_coverage else []
    rewritten_bullets = rewrite_selected_bullets(
        llm,
        candidate,
        job_fields,
        selected_bullet_ids,
        role_track=str(tailoring.get("role_track", "")),
        priority_keywords=priority_keywords,
    )
    rewritten_projects = rewrite_project_descriptions(
        llm,
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
        llm=llm,
        candidate_profile=candidate,
        job_fields=job_fields,
        preferences=preferences,
        company_issue_brief={},
    )

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
    except Exception:
        # Fallback to plain converter instead of failing the full request.
        text_to_pdf(resume_text, resume_pdf)
    try:
        cover_letter_text_to_pdf(cover_text, cover_pdf)
    except Exception:
        text_to_pdf(cover_text, cover_pdf)
    try:
        resume_text_to_docx(resume_text, resume_docx)
    except Exception:
        text_to_docx(resume_text, resume_docx)
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

    diff_summary = build_diff_summary(all_bullet_ids, selected_bullet_ids)
    coverage = keyword_coverage_for_text(list(tailoring.get("ats_keywords", [])), resume_text)

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
        matched_keywords=list(coverage.get("matched_keywords", [])),
        missing_keywords=list(coverage.get("missing_keywords", [])),
    )


@app.post("/company_issue", response_model=CompanyIssueResponse, dependencies=[Depends(require_token)])
def company_issue(payload: CompanyIssueRequest) -> CompanyIssueResponse:
    job = storage.get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    brief = build_company_issue_brief(
        llm=llm,
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


@app.post("/find_targets", response_model=FindTargetsResponse, dependencies=[Depends(require_token)])
def find_targets(payload: FindTargetsRequest) -> FindTargetsResponse:
    job = storage.get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    company = str(job.get("company", "") or job.get("company_hint", "")).strip()
    role = str(job.get("title", "")).strip()
    if not company:
        raise HTTPException(status_code=400, detail="Company is missing for this job.")

    contacts, warnings = find_target_contacts(
        serpapi_key=settings.serpapi_key,
        hunter_api_key=settings.hunter_api_key,
        company=company,
        role=role,
        job_url=str(job.get("url", "")).strip(),
        limit=12,
    )
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
            )
            for c in contacts
        ],
        warnings=warnings,
    )


@app.post("/referral_drafts", response_model=ReferralDraftsResponse, dependencies=[Depends(require_token)])
def referral_drafts(payload: ReferralDraftsRequest) -> ReferralDraftsResponse:
    job = storage.get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not payload.contacts:
        raise HTTPException(status_code=400, detail="At least one contact is required.")

    candidate = load_yaml(settings.candidate_profile_path)
    candidate_name = str(candidate.get("identity", {}).get("full_name", "")).strip() or "Candidate"
    role = str(job.get("title", "")).strip() or "this role"
    company = str(job.get("company", "")).strip() or "the company"

    drafts: list[ReferralDraft] = [
        _fallback_referral_draft(candidate_name, role, company, contact)
        for contact in payload.contacts
    ]

    if llm.enabled:
        try:
            user_payload = (
                "CANDIDATE_NAME:\n"
                f"{candidate_name}\n\n"
                "ROLE:\n"
                f"{role}\n\n"
                "COMPANY:\n"
                f"{company}\n\n"
                "CONTACTS:\n"
                f"{[c.model_dump() for c in payload.contacts]}"
            )
            response = llm.json_completion(REFERRAL_DRAFTS_PROMPT, user_payload)
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
                        linkedin_note=note,
                        linkedin_followup=str(item.get("linkedin_followup", "")).strip() or base.linkedin_followup,
                        email_subject=str(item.get("email_subject", "")).strip() or base.email_subject,
                        email_body=str(item.get("email_body", "")).strip() or base.email_body,
                    )
                )
            if merged:
                drafts = merged
        except Exception:
            pass

    return ReferralDraftsResponse(
        job_id=payload.job_id,
        company=company,
        role=role,
        drafts=drafts,
    )


@app.get("/download/{job_id}/{doc_type}", dependencies=[Depends(require_token)])
def download(job_id: int, doc_type: str) -> FileResponse:
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    outputs = job.get("outputs", {})
    path = outputs.get(doc_type)
    if not path:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document missing on disk")

    if file_path.suffix == ".pdf":
        media_type = "application/pdf"
    elif file_path.suffix == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "text/plain"
    return FileResponse(path=file_path, media_type=media_type, filename=file_path.name)


@app.get("/jobs", response_model=list[JobRecord], dependencies=[Depends(require_token)])
def jobs() -> list[JobRecord]:
    return [JobRecord(**row) for row in storage.list_jobs(limit=20)]


@app.post("/sync_job", response_model=SyncJobResponse, dependencies=[Depends(require_token)])
def sync_job(
    payload: SyncJobRequest,
    web_user: dict[str, str] | None = Depends(get_web_user_optional),
) -> SyncJobResponse:
    source_job_id = payload.source_job_id
    if source_job_id:
        feed_id = storage.upsert_feed_item_from_job(source_job_id, visibility=payload.visibility)
    else:
        feed_id = storage.upsert_feed_item_from_payload(payload.model_dump())
    if not feed_id:
        raise HTTPException(status_code=500, detail="Unable to sync job feed item.")
    if web_user:
        storage.record_user_action(
            web_user["email"],
            feed_id,
            JobActionType.ANALYZED,
            metadata={"source_job_id": source_job_id},
            user_name=web_user["name"],
            image_url=web_user["image_url"],
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
    status: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    web_user: dict[str, str] = Depends(require_web_user),
) -> UserJobListResponse:
    items = storage.list_user_jobs(web_user["email"], status=status, limit=limit)
    return UserJobListResponse(
        items=[to_private_job_feed_item(item) for item in items],
        total=len(items),
    )


@app.get("/web/me/stats", response_model=UserStatsResponse)
def web_me_stats(web_user: dict[str, str] = Depends(require_web_user)) -> UserStatsResponse:
    return UserStatsResponse(**storage.get_user_stats(web_user["email"]))


@app.post("/save_packet", response_model=SavePacketResponse, dependencies=[Depends(require_token)])
def save_packet(payload: SavePacketRequest) -> SavePacketResponse:
    job = storage.get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    outputs = job.get("outputs", {})
    resume_src = outputs.get("resume_pdf")
    cover_src = outputs.get("cover_letter_pdf")
    resume_docx_src = outputs.get("resume_docx")
    cover_docx_src = outputs.get("cover_letter_docx")
    if not resume_src or not cover_src:
        raise HTTPException(status_code=400, detail="Documents not generated yet.")

    candidate = load_yaml(settings.candidate_profile_path)
    role = sanitize_name(str(job.get("title", "")), "JobRole")
    company = sanitize_name(str(job.get("company", "")), "Company")
    name = sanitize_name(str(candidate.get("identity", {}).get("full_name", "")), "Candidate")
    folder = settings.packet_dir / f"{role}_{company}_{name}"
    folder.mkdir(parents=True, exist_ok=True)

    resume_dst = folder / f"{role}_{company}_{name}.pdf"
    cover_dst = folder / f"{role}_{company}_{name}_CoverLetter.pdf"
    shutil.copy2(Path(resume_src), resume_dst)
    shutil.copy2(Path(cover_src), cover_dst)
    files = {
        "resume_pdf": str(resume_dst),
        "cover_letter_pdf": str(cover_dst),
    }
    if resume_docx_src and Path(resume_docx_src).exists():
        resume_docx_dst = folder / f"{role}_{company}_{name}.docx"
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


@app.post("/mark_applied", response_model=MarkAppliedResponse, dependencies=[Depends(require_token)])
def mark_applied(payload: MarkAppliedRequest) -> MarkAppliedResponse:
    job = storage.get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    storage.update_status(payload.job_id, JobStatus.MANUAL_SUBMISSION_REQUIRED)
    updated = storage.get_job(payload.job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found after update")
    return MarkAppliedResponse(
        job_id=payload.job_id,
        status=JobStatus.MANUAL_SUBMISSION_REQUIRED,
        applied_at=str(updated.get("updated_at", "")),
    )


@app.get("/export/applied.csv", dependencies=[Depends(require_token)])
def export_applied_csv() -> Response:
    rows = storage.list_applied_jobs()
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
