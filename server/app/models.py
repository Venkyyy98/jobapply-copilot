from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    NEW = "NEW"
    ANALYZED = "ANALYZED"
    APPROVED = "APPROVED"
    DOCS_READY = "DOCS_READY"
    PREFILL_READY = "PREFILL_READY"
    MANUAL_SUBMISSION_REQUIRED = "MANUAL_SUBMISSION_REQUIRED"


class JobActionType(str, Enum):
    SAVED = "SAVED"
    ANALYZED = "ANALYZED"
    GENERATED_DOCS = "GENERATED_DOCS"
    APPLIED = "APPLIED"
    OUTREACH_STARTED = "OUTREACH_STARTED"
    INTERESTED = "INTERESTED"


class AnalyzeJobRequest(BaseModel):
    url: str = ""
    job_text: str = Field(min_length=50)
    page_title: str = ""
    company_hint: str = ""


class AnalyzeJobResponse(BaseModel):
    job_id: int
    title: str
    company: str
    summary: str
    fit_score: int
    fit_reasons: list[str]
    tailoring_plan: list[str]
    suggested_bullets: list[str]
    suggested_project_ids: list[str] = Field(default_factory=list)
    common_answers: dict[str, str]
    keyword_coverage_pct: int = 0
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    compliance_ready: bool
    compliance_notes: list[str]


class GenerateDocsRequest(BaseModel):
    job_id: int
    approve: bool = False
    boost_coverage: bool = False


class GenerateDocsResponse(BaseModel):
    job_id: int
    status: JobStatus
    compliance_passed: bool
    compliance_issues: list[str]
    files: dict[str, str]
    diff_summary: list[str]
    suggested_project_ids: list[str] = Field(default_factory=list)
    keyword_coverage_pct: int = 0
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)


class CompanyIssueRequest(BaseModel):
    job_id: int


class CompanyIssueResponse(BaseModel):
    job_id: int
    company: str
    issue_brief: dict[str, Any] = Field(default_factory=dict)


class ReferralContact(BaseModel):
    name: str = ""
    title: str = ""
    linkedin_url: str = ""
    email: str = ""


class ReferralDraftsRequest(BaseModel):
    job_id: int
    contacts: list[ReferralContact] = Field(default_factory=list)


class ReferralDraft(BaseModel):
    contact_name: str
    contact_title: str = ""
    linkedin_url: str = ""
    email: str = ""
    linkedin_note: str
    linkedin_followup: str = ""
    email_subject: str
    email_body: str


class ReferralDraftsResponse(BaseModel):
    job_id: int
    company: str
    role: str
    drafts: list[ReferralDraft] = Field(default_factory=list)


class FindTargetsRequest(BaseModel):
    job_id: int


class TargetContact(BaseModel):
    name: str = ""
    title: str = ""
    linkedin_url: str = ""
    email: str = ""
    source: str = ""
    score: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class FindTargetsResponse(BaseModel):
    job_id: int
    company: str
    role: str
    contacts: list[TargetContact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MarkAppliedRequest(BaseModel):
    job_id: int
    notes: str = ""


class MarkAppliedResponse(BaseModel):
    job_id: int
    status: JobStatus
    applied_at: str


class SavePacketRequest(BaseModel):
    job_id: int


class SavePacketResponse(BaseModel):
    job_id: int
    folder: str
    files: dict[str, str]


class JobRecord(BaseModel):
    id: int
    url: str
    title: str
    company: str
    status: JobStatus
    created_at: str
    updated_at: str
    fit_score: int | None = None
    company_issue_brief: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


class SyncJobRequest(BaseModel):
    source_job_id: int | None = None
    url: str = ""
    page_title: str = ""
    company_hint: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    summary: str = ""
    job_text: str = ""
    fit_score: int | None = None
    fit_reasons: list[str] = Field(default_factory=list)
    tailoring_plan: list[str] = Field(default_factory=list)
    suggested_bullets: list[str] = Field(default_factory=list)
    suggested_project_ids: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    keyword_coverage_pct: int = 0
    compliance_ready: bool = False
    compliance_notes: list[str] = Field(default_factory=list)
    visibility: str = "public"


class AggregateCounts(BaseModel):
    saved: int = 0
    analyzed: int = 0
    generated_docs: int = 0
    applied: int = 0
    outreach_started: int = 0
    interested: int = 0


class PublicJobFeedItem(BaseModel):
    id: int
    slug: str
    source_job_id: int | None = None
    source_url: str
    title: str
    company: str
    location: str = ""
    work_mode: str = "Unknown"
    role_family: str = "Other"
    page_title: str = ""
    summary: str = ""
    job_text_excerpt: str = ""
    fit_score: int | None = None
    fit_reasons: list[str] = Field(default_factory=list)
    tailoring_plan: list[str] = Field(default_factory=list)
    suggested_bullets: list[str] = Field(default_factory=list)
    suggested_project_ids: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    keyword_coverage_pct: int = 0
    compliance_ready: bool = False
    compliance_notes: list[str] = Field(default_factory=list)
    aggregate_counts: AggregateCounts = Field(default_factory=AggregateCounts)
    created_at: str
    updated_at: str


class SyncJobResponse(BaseModel):
    job_feed_item: PublicJobFeedItem


class PublicJobsResponse(BaseModel):
    items: list[PublicJobFeedItem] = Field(default_factory=list)
    available_role_families: list[str] = Field(default_factory=list)
    total: int = 0


class JobActionRequest(BaseModel):
    action: JobActionType
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobActionResponse(BaseModel):
    job_feed_item_id: int
    action: JobActionType
    recorded_at: str
    aggregate_counts: AggregateCounts = Field(default_factory=AggregateCounts)


class PrivateJobFeedItem(PublicJobFeedItem):
    user_action: str = ""
    user_action_metadata: dict[str, Any] = Field(default_factory=dict)
    action_updated_at: str = ""


class UserJobListResponse(BaseModel):
    items: list[PrivateJobFeedItem] = Field(default_factory=list)
    total: int = 0


class UserStatsResponse(BaseModel):
    user: dict[str, str] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    recent_activity: list[dict[str, str]] = Field(default_factory=list)
