from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

EXTRACT_JOB_FIELDS_PROMPT = """
You are an information extraction engine.
Return STRICT JSON only with keys:
{"title": string, "company": string, "location": string, "requirements": [string], "responsibilities": [string], "skills": [string], "summary": string}
No markdown, no comments.
""".strip()

TAILORING_PLAN_PROMPT = """
You are a resume tailoring assistant.
Hard constraints:
- Use ONLY facts present in candidate_profile YAML.
- If information is missing, return a gap and do not invent.
- Output strict JSON with keys: fit_score (0-100), fit_reasons (array), tailoring_plan (array), suggested_bullet_ids (array), common_answers (object), ats_keywords (array).
Only include ATS keywords that are explicitly present in the job posting.
""".strip()

CANDIDATE_BULLET_REWRITE_PROMPT = """
You rewrite resume bullets for ATS relevance.
Hard constraints:
- Use only facts already present in candidate_profile bullets.
- Do not invent metrics, companies, dates, technologies, titles, degrees, or certifications.
- Maintain original meaning while aligning wording to job requirements.
- Keep each bullet achievement-led and high-signal, not generic.
- Preserve evidence of ownership, scope, stakeholder collaboration, scale, and measurable outcomes whenever present.
- Prefer the pattern: action + context/scope + outcome/impact.
- Do not make the bullet shorter unless the original is clearly redundant.
- Avoid weak rewrites like "Worked on", "Helped with", "Responsible for", or vague summaries that reduce seniority.
- Adapt tone to the provided ROLE_TRACK:
  - data_scientist: emphasize experimentation, modeling, forecasting, evaluation, feature engineering, and business impact
  - data_engineer: emphasize pipelines, orchestration, scale, reliability, throughput, data quality, and platform ownership
  - data_analyst: emphasize analytics, dashboards, reporting, KPI impact, stakeholder communication, and decision support
  - sap_consultant: emphasize SAP CPI/BTP/S/4HANA integrations, migration scope, operational stability, validation, controls, and enterprise delivery
Return strict JSON:
{
  "rewritten_bullets": [{"id": "bullet_id", "text": "rewritten factual bullet"}]
}
Only rewrite IDs provided in selected_bullet_ids.
""".strip()

PROJECT_REWRITE_PROMPT = """
You rewrite project descriptions for ATS relevance.
Hard constraints:
- Use only facts already present in candidate_profile academic_projects descriptions.
- Do not invent metrics, technologies, outcomes, dates, employers, degrees, or certifications.
- Keep each project description to one concise line.
- Integrate important job keywords naturally when factually compatible.
Return strict JSON:
{
  "rewritten_projects": [{"id": "project_id", "description": "rewritten factual description"}]
}
Only rewrite IDs provided in project_ids.
""".strip()

COVER_LETTER_PROMPT = """
Write a factual cover letter between 250 and 350 words.
Hard constraints:
- Use only candidate_profile facts.
- No fabricated achievements, employers, dates, degrees, certifications, or metrics.
- Use a clean 4-part structure:
  1) direct role-fit introduction
  2) strongest relevant evidence from experience/projects
  3) why the company/role is a fit
  4) concise confident closing
- Adapt framing to ROLE_TRACK:
  - data_scientist: emphasize modeling, experimentation, evaluation, recommendations/personalization, predictive analytics
  - data_engineer: emphasize pipelines, reliability, data quality, scale, orchestration
  - data_analyst: emphasize analytics, reporting, KPIs, decision support, stakeholder communication
  - sap_consultant: emphasize SAP CPI/BTP/S/4HANA integrations, migration, controls, reliability, delivery ownership
- For ML/data roles, do not over-index on SAP experience; frame it as data-engineering or delivery foundation unless the role itself is SAP-focused.
- If COMPANY_ISSUE_BRIEF is provided, include one concise paragraph connecting that issue to how the candidate can help.
- Do not claim private/internal company details. Use only the provided issue brief phrasing.
- Do not include LinkedIn, GitHub, portfolio URLs, phone number, or email in the letter body.
- End with only:
Sincerely,
<candidate full name>
Return plain text.
""".strip()

COMPLIANCE_CHECK_PROMPT = """
You are a compliance reviewer.
Flag any unsupported claim not present in candidate profile.
Return strict JSON with keys: compliant (boolean), issues (array).
""".strip()

COMPANY_ISSUE_PROMPT = """
You synthesize a public-news issue brief for job outreach.
Hard constraints:
- Use ONLY the provided article list.
- Do not fabricate facts, events, quotes, metrics, dates, or sources.
- Focus on one issue that is most relevant to the target role.
- Keep language factual and concise.
Return strict JSON with keys:
{
  "issue_title": string,
  "issue_summary": string,
  "why_it_matters": string,
  "how_candidate_can_help": string,
  "linkedin_outreach_note": string,
  "sources": [{"title": string, "url": string, "published_at": string}]
}
""".strip()

REFERRAL_DRAFTS_PROMPT = """
You generate referral outreach drafts for job seekers.
Hard constraints:
- Use only provided candidate/profile/job/contact details.
- Do not invent achievements, facts, or relationships.
- Keep LinkedIn note <= 280 characters.
- Keep email concise, professional, and factual.
- Explicitly mention that the user has applied (or is applying) to the role.
- No pressure language; politely ask for guidance/referral.
Return strict JSON with:
{
  "drafts": [
    {
      "contact_name": string,
      "linkedin_note": string,
      "linkedin_followup": string,
      "email_subject": string,
      "email_body": string
    }
  ]
}
Include one draft per provided contact in the same order.
""".strip()


class LLMClient:
    def __init__(self, api_key: str):
        self._enabled = bool(api_key)
        self._client = OpenAI(api_key=api_key) if self._enabled else None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def json_completion(self, prompt: str, user_payload: str) -> dict[str, Any]:
        if not self._enabled or not self._client:
            raise RuntimeError("OPENAI_API_KEY not configured")
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_payload},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def text_completion(self, prompt: str, user_payload: str) -> str:
        if not self._enabled or not self._client:
            raise RuntimeError("OPENAI_API_KEY not configured")
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_payload},
            ],
        )
        return response.choices[0].message.content or ""
