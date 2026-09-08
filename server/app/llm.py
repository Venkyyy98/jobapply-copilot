from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .security import public_error_detail, redact_text

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
  - genai_engineer: emphasize LLM applications, RAG, tool calling, evaluation, secure APIs, observability, and production delivery
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
Write a factual, human-sounding cover letter around 250 to 350 words.

TONE RULES (mandatory):
- Never write more than TWO consecutive sentences that begin with "I". After two "I" sentences, vary the opener: "This experience...", "The result was...", "What that taught me...", "Working on this...", "Your team...", "That project...", etc.
- Do NOT open with "I am applying for the <role> at <company>" — that is formulaic. Open with 1–2 sentences that lead with value to the employer: what you bring, why this specific role fits.
- Do NOT list achievements as a series of "I [verb]..." sentences. Develop 2–3 key facts as brief stories: what was the problem, what you did, what changed.
- Do NOT use weak phrases like "I have experience in", "I have worked on", or "I have done" — show through concrete examples instead.
- At least one sentence in the body must address the employer directly: "your team", "your platform", "your customers", or similar.
- Vary sentence length: mix short punchy statements with longer explanatory ones.
- Avoid repetitive AI-style phrases such as "leveraging cutting-edge technology", "passionate about innovation", "delve", "dynamic", and "seamlessly".
- Begin with a direct reason the company's problem, role, or technical work is interesting to the candidate.

JOB REQUIREMENTS ALIGNMENT:
- Read JOB_FIELDS.requirements and JOB_FIELDS.responsibilities carefully.
- Each body paragraph must visibly map to at least one requirement or responsibility from the posting.
- The letter must feel written for THIS job — the hiring manager should see you read their description.

STRUCTURE:
1) "Dear Hiring Manager,"
2) Opening hook (2–3 sentences): professional identity and strongest fit signal, framed from the employer's perspective.
3) Story paragraph: the most relevant project or achievement. What was the problem, what did the candidate build or do, what was the result. Keep it concrete, brief, and narrative — not a list.
4) Broader fit paragraph: connect 1–2 additional relevant facts to specific job requirements. Use "your team" or "your company" framing to show you understand their context.
5) Company-specific paragraph: why this role at this company is compelling, grounded in actual job requirements. Include relevant certifications and education only when present in the profile.
6) Closing: invite discussion, include profile-supported phone and email.
7) "Sincerely," followed by the candidate's full name.

Hard constraints:
- Use only candidate_profile facts.
- Use "Venkatesh Mudaliar" as the candidate name.
- No fabricated achievements, employers, dates, degrees, certifications, or metrics.
- Never copy a metric from an example or template unless that exact metric is present in candidate_profile.
- Mention no more than TWO projects total, selected according to JOB_FIELDS and ROLE_TRACK; do not reuse the same projects for every job.
- Clearly distinguish personal, academic, research, and professional work. Do not turn projects into paid experience.
- Location rules: the current location is Antioch, California. For Bay Area roles, it is acceptable to say the candidate is based in the San Francisco Bay Area. For remote roles, use Antioch, CA. For New York/New Jersey roles, do not claim the candidate currently lives locally; mention relocation openness only if preferences explicitly support it. For other locations, do not invent relocation plans.
- Adapt framing to ROLE_TRACK:
  - genai_engineer: emphasize LLM applications, RAG, retrieval evaluation, tool calling, secure APIs, observability, and production delivery
  - data_scientist: emphasize modeling, experimentation, evaluation, recommendations/personalization, predictive analytics
  - data_engineer: emphasize pipelines, reliability, data quality, scale, orchestration
  - data_analyst: emphasize analytics, reporting, KPIs, decision support, stakeholder communication
  - business_analyst: emphasize stakeholder communication, business process understanding, requirements thinking, KPI impact, and decision support
  - market_analyst: emphasize market trends, forecasting, segmentation, reporting, and strategic insights
  - sap_consultant: emphasize SAP CPI/BTP/S/4HANA integrations, migration, controls, reliability, delivery ownership
- Make clear why hiring the candidate is advantageous for this role and team, not just what tools they know.
- For ML/data roles, do not over-index on SAP experience; frame it as data-engineering or delivery foundation unless the role itself is SAP-focused.
- If COMPANY_ISSUE_BRIEF contains a credible public issue summary, weave one concise connection into the company-specific paragraph.
- Do not claim private/internal company details. Use only the provided issue brief phrasing.
- Do not include LinkedIn, GitHub, or portfolio URLs in the letter body.
- End with only:
Sincerely,
<candidate full name>
Return plain text.
""".strip()

SAP_COVER_LETTER_PROMPT = """
Write a factual, human-sounding SAP-focused cover letter between 375 and 525 words.

TONE RULES (mandatory):
- Never write more than TWO consecutive sentences that begin with "I". After two "I" sentences, shift the opener: "That migration...", "The result was...", "What made this complex...", "Working across...", "For your team...", "That experience...", etc.
- Do NOT open with "I am applying for the <role> at <company>" — that is formulaic. Open with 1–2 sentences that lead with the candidate's value: what they bring to SAP integration work, why this specific role is a strong fit.
- Do NOT list achievements as a series of "I [verb]..." sentences. Tell brief stories: what was the situation, what did you do, what changed — so the reader understands the context, not just the action.
- Do NOT use weak phrases like "I have experience in", "I have worked with", "I have done" — show through concrete examples instead.
- At least one paragraph must reference "your integration landscape", "your team", or similar — showing you understand the employer's context.
- Vary sentence length: mix short declarative statements with longer explanatory ones to create natural rhythm.

JOB REQUIREMENTS ALIGNMENT:
- Read JOB_FIELDS.requirements and JOB_FIELDS.responsibilities carefully.
- Each body paragraph must map to at least one specific requirement or responsibility from the posting.
- The letter must feel written for THIS job at THIS company — adapt role title, company name, and selected evidence every time.

STRUCTURE:
1) "Dear Hiring Manager,"
2) Opening hook (2–3 sentences): SAP integration professional identity and strongest fit signal, framed from the employer's perspective. No formulaic opener.
3) Standout story paragraph: the PI/PO-to-CPI migration on the Puma account. Tell it as a story — the problem (legacy PI/PO, complex mappings), what you redesigned, the monitoring and error-tracing work you built, and what the operational lesson was (integrations must fail visibly, not silently). Do not list steps; explain why it mattered. Adapt wording naturally each time.
4) Broader delivery paragraph: 1–2 additional profile-supported SAP achievements most relevant to JOB_FIELDS. Choose from: BHP integration delivery, 50+ S/4HANA interface migration, US-to-Canada migration, procurement/MM automation, Principal Propagation/OAuth 2.0, Snowflake-to-CPI incident tracing. Connect each to a specific job requirement.
5) Company-specific paragraph: why this role at this company is compelling, grounded in actual job requirements. Weave in profile-supported certifications (SAP Integration Suite, SAP Blackbelt Integration Suite, AWS AI Practitioner) and education (Stevens M.S. Data Science, GPA) naturally — not as a bullet list.
6) Closing: invite discussion, include profile-supported phone and email.
7) "Sincerely," followed by the candidate's full name.

Hard constraints:
- Use only facts present in CANDIDATE_PROFILE, especially cover_letter_facts.sap.
- Never leave placeholders such as [Company Name] — always substitute from JOB_FIELDS.
- Never invent achievements, clients, metrics, employers, dates, technologies, degrees, certifications, or company initiatives.
- Do not weaken or omit the strongest SAP evidence merely to sound concise.
- Do not include LinkedIn, GitHub, portfolio URLs, or a mailing-address block in the letter body.
- Return plain text only.
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
- Write the LinkedIn note as a short connection request, not a company research summary.
- If a verified shared company or school is provided, lead with that shared connection.
- Explicitly mention that the user is interested in the role, but do not mention lawsuits, legal challenges, scandals, news, or company risks in the LinkedIn note.
- Never use placeholders such as "Name", "[Name]", "Title", or "there" when a contact is missing; use the contact's supplied name or omit the draft with a clear validation error.
- The email must follow this exact paragraph structure:
  1. "Hi <first name>,"
  2. State that the candidate applied for the role at the company and found the contact while researching the team.
  3. Start "A bit about me -" and summarize the factual M.S., GPA, 4+ years of experience, Accenture/LTIMindtree work, and AWS AI certification.
  4. Start "I'm genuinely interested in <company> specifically because" and include one sentence grounded in the supplied job/company context, followed by one sentence connecting the most relevant factual skill.
  5. Ask for a 15-minute call and, if it makes sense, a referral.
  6. "Either way, thank you for your time."
  7. End with "Best," then the candidate name, phone, and LinkedIn.
- Do not leave brackets, placeholders, or research instructions in the email.
- No pressure language.
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
    def __init__(self, api_key: str, key_source: str = "none"):
        self._enabled = bool(api_key)
        self._key_source = key_source if api_key else "none"
        self._client = OpenAI(api_key=api_key) if self._enabled else None
        self._attempts = 0
        self._successful_calls = 0
        self._errors: list[str] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def key_source(self) -> str:
        return self._key_source

    def reset_diagnostics(self) -> None:
        self._attempts = 0
        self._successful_calls = 0
        self._errors = []

    @property
    def diagnostics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "attempts": self._attempts,
            "successful_calls": self._successful_calls,
            "errors": [redact_text(error) for error in self._errors],
            "key_source": self._key_source,
        }

    def test_key(self) -> bool:
        if not self._enabled or not self._client:
            raise RuntimeError("OPENAI_API_KEY not configured")
        try:
            self._client.models.list()
            return True
        except Exception as exc:
            self._errors.append(public_error_detail(exc))
            raise RuntimeError(public_error_detail(exc)) from None

    def json_completion(self, prompt: str, user_payload: str) -> dict[str, Any]:
        if not self._enabled or not self._client:
            raise RuntimeError("OPENAI_API_KEY not configured")
        self._attempts += 1
        try:
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
            parsed = json.loads(content)
            self._successful_calls += 1
            return parsed
        except Exception as exc:
            self._errors.append(public_error_detail(exc)[:240])
            raise

    def text_completion(self, prompt: str, user_payload: str) -> str:
        if not self._enabled or not self._client:
            raise RuntimeError("OPENAI_API_KEY not configured")
        self._attempts += 1
        try:
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.2,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_payload},
                ],
            )
            self._successful_calls += 1
            return response.choices[0].message.content or ""
        except Exception as exc:
            self._errors.append(public_error_detail(exc)[:240])
            raise
