from __future__ import annotations

from datetime import datetime
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .llm import COVER_LETTER_PROMPT, LLMClient
from .tailoring import detect_role_track


def _display_link(url: str) -> str:
    clean = str(url or "").strip()
    clean = re.sub(r"^https?://", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^www\.", "", clean, flags=re.IGNORECASE)
    clean = clean.rstrip("/")
    return clean


def _compact_location(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    replacements = {
        "Jersey City, New Jersey, United States": "Jersey City, NJ",
        "New York, New York, United States": "New York, NY",
        "Antioch, California, United States": "Antioch, CA",
    }
    if text in replacements:
        return replacements[text]
    text = text.replace(", United States", "")
    text = text.replace(", New Jersey", ", NJ")
    text = text.replace(", New York", ", NY")
    text = text.replace(", California", ", CA")
    return text


def _sanitize_cover_letter_body(text: str, candidate_name: str) -> str:
    if "Dear Hiring Manager" in text:
        text = text.split("Dear Hiring Manager", 1)[1]
        text = text.lstrip(", \n\t")

    lines = [line.rstrip() for line in text.splitlines()]
    cleaned: list[str] = []
    for line in lines:
        low = line.lower()
        if low.strip() in {"[date]", "date", "dd/mm/yyyy"}:
            continue
        if "linkedin.com" in low or "github.com" in low or "http://" in low or "https://" in low:
            continue
        if "linkedin" in low or "github" in low or "portfolio" in low:
            continue
        if low.strip().startswith(("hiring manager", "dear hiring manager", "dear recruiter", "dear team")):
            continue
        if low.strip() in {"sincerely,", "best regards,", "regards,", "thank you,"}:
            continue
        if candidate_name and low.strip() == candidate_name.lower():
            continue
        cleaned.append(line)

    collapsed = "\n".join(cleaned).strip()
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    for token in ["Sincerely,", "Best regards,", "Regards,", "Thank you,"]:
        if token in collapsed:
            collapsed = collapsed.split(token, 1)[0].rstrip()
    collapsed = re.sub(r"\b(i have worked extensively with|my technical toolkit|i am proficient in)\b.*", "", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _company_display(job_fields: dict[str, Any]) -> str:
    return str(job_fields.get("company", "")).strip() or str(job_fields.get("company_hint", "")).strip() or "the company"


def _role_display(job_fields: dict[str, Any]) -> str:
    return str(job_fields.get("title", "")).strip() or str(job_fields.get("job_title", "")).strip() or "the role"


def _candidate_summary(candidate_profile: dict[str, Any]) -> str:
    return str(candidate_profile.get("summary", "")).strip()


def _education_line(candidate_profile: dict[str, Any]) -> str:
    education = candidate_profile.get("education", []) or []
    if not education:
        return ""
    first = education[0] if isinstance(education[0], dict) else {}
    degree = str(first.get("degree", "")).strip()
    field = str(first.get("field", "")).strip()
    school = str(first.get("school", "")).strip()
    gpa = str(first.get("gpa", "")).strip()
    pieces = []
    if degree:
        pieces.append(degree)
    if field:
        pieces.append(field)
    if school:
        pieces.append(f"at {school}")
    text = " ".join(pieces).strip()
    if gpa:
        text = f"{text} (GPA {gpa})".strip()
    return text


def _find_bullet(candidate_profile: dict[str, Any], bullet_id: str) -> str:
    for exp in candidate_profile.get("experience", []) or []:
        for bullet in exp.get("bullets", []) or []:
            if isinstance(bullet, dict) and str(bullet.get("id", "")).strip() == bullet_id:
                return str(bullet.get("text", "")).strip()
    return ""


def _find_project(candidate_profile: dict[str, Any], project_id: str) -> str:
    for proj in candidate_profile.get("academic_projects", []) or []:
        if isinstance(proj, dict) and str(proj.get("id", "")).strip() == project_id:
            parts = [str(proj.get("name", "")).strip()]
            bullets = [str(x).strip() for x in (proj.get("bullets", []) or []) if str(x).strip()]
            if bullets:
                parts.append(bullets[0])
            elif proj.get("description"):
                parts.append(str(proj.get("description", "")).strip())
            return ": ".join([p for p in parts if p])
    return ""


def _first_relevant_experience(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    suggestions = job_fields.get("suggested_bullets", []) or []
    for bid in suggestions:
        text = _find_bullet(candidate_profile, str(bid))
        if text:
            return text
    experience = candidate_profile.get("experience", []) or []
    for exp in experience:
        bullets = exp.get("bullets", []) or []
        for bullet in bullets:
            if isinstance(bullet, dict) and bullet.get("text"):
                return str(bullet.get("text", "")).strip()
    return ""


def _first_relevant_project(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    suggestions = job_fields.get("suggested_project_ids", []) or []
    for pid in suggestions:
        text = _find_project(candidate_profile, str(pid))
        if text:
            return text
    projects = candidate_profile.get("academic_projects", []) or []
    for proj in projects:
        if isinstance(proj, dict):
            return _find_project(candidate_profile, str(proj.get("id", "")).strip())
    return ""


def _build_role_specific_fallback(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    role = _role_display(job_fields)
    company = _company_display(job_fields)
    role_track = detect_role_track(job_fields)
    summary = _candidate_summary(candidate_profile)
    edu = _education_line(candidate_profile)
    experience_line = _first_relevant_experience(candidate_profile, job_fields)
    project_line = _first_relevant_project(candidate_profile, job_fields)

    intro_base = f"I am excited to apply for the {role} position at {company}."
    if role_track == "sap_consultant":
        intro = (
            f"{intro_base} My background combines SAP integration delivery, enterprise data workflows, and client-facing execution, "
            "which aligns well with roles focused on SAP BTP, CPI, and reliable cross-system integration."
        )
    elif role_track == "data_scientist":
        intro = (
            f"{intro_base} I bring a foundation in machine learning, predictive modeling, and experimentation, supported by "
            f"{edu or 'graduate training in data science'} and hands-on project work tied to real-world datasets."
        )
    elif role_track == "data_engineer":
        intro = (
            f"{intro_base} My experience centers on building reliable data pipelines, improving data quality, and supporting "
            "analytics-ready workflows that scale across teams and systems."
        )
    else:
        intro = (
            f"{intro_base} I bring experience in analytics, reporting, and stakeholder-facing problem solving, with a focus on turning "
            "raw data into clear business insights and operational improvements."
        )
    if summary and role_track != "sap_consultant":
        intro = f"{intro} {summary}"

    if role_track == "sap_consultant":
        evidence = (
            f"In my professional experience, {experience_line.lower() if experience_line else 'I have delivered SAP-focused integration work across enterprise systems'}."
        )
        if project_line:
            evidence += f" I also built {project_line}, which reflects my focus on observability, stability, and proactive issue detection in SAP CPI environments."
    elif role_track == "data_scientist":
        evidence = (
            f"My recent work includes {project_line.lower() if project_line else 'machine learning and forecasting projects using real-world datasets'}, "
            "which strengthened my approach to feature engineering, evaluation, and model performance analysis."
        )
        if experience_line:
            evidence += (
                f" Professionally, {experience_line.lower()}, which also gave me a practical data-engineering foundation for building end-to-end ML workflows."
            )
    elif role_track == "data_engineer":
        evidence = (
            f"In my recent roles, {experience_line.lower() if experience_line else 'I have built and improved data pipelines across enterprise platforms'}, "
            "with emphasis on reliability, throughput, and clean downstream consumption."
        )
        if project_line:
            evidence += f" I have also worked on {project_line.lower()}, which reinforced scalable processing and monitoring patterns."
    else:
        evidence = (
            f"My experience includes {experience_line.lower() if experience_line else 'analytics and data quality work across cross-functional teams'}, "
            "which strengthened my ability to support reporting, KPI tracking, and decision-making."
        )
        if project_line:
            evidence += f" I have also completed {project_line.lower()}, which reflects my ability to analyze patterns and communicate findings clearly."

    why_company = (
        f"I am particularly interested in {company} because this role sits at the intersection of technical execution and measurable business impact."
    )
    if role_track == "data_scientist":
        why_company += " I would be excited to contribute to modeling, experimentation, and data-driven product decisions in a production setting."
    elif role_track == "data_engineer":
        why_company += " I would be excited to contribute to resilient data workflows, quality controls, and scalable platform delivery."
    elif role_track == "data_analyst":
        why_company += " I would be excited to contribute through analysis, reporting, and insight generation that helps teams make better decisions."
    else:
        why_company += " I would be excited to contribute to integration delivery, production stability, and enterprise transformation outcomes."

    closing = "Thank you for your time and consideration. I would welcome the opportunity to discuss how my background can support your team."
    return "\n\n".join([intro.strip(), evidence.strip(), why_company.strip(), closing])


def _format_cover_letter_document(candidate_profile: dict[str, Any], job_fields: dict[str, Any], body: str) -> str:
    identity = candidate_profile.get("identity", {}) or {}
    links = candidate_profile.get("links", {}) or {}
    full_name = str(identity.get("full_name", "")).strip()
    phone = str(identity.get("phone", "")).strip()
    email = str(identity.get("email", "")).strip()
    linkedin = _display_link(str(links.get("linkedin", "")).strip())
    location = _compact_location(str(identity.get("location", "")).strip())
    company = str(job_fields.get("company", "")).strip() or str(job_fields.get("company_hint", "")).strip() or "Company"
    role = str(job_fields.get("title", "")).strip() or str(job_fields.get("job_title", "")).strip() or "Role"
    date_line = datetime.now().strftime("%B %d, %Y")

    contact_parts = [part for part in [phone, email, linkedin, location] if part]
    body_paragraphs = [part.strip() for part in body.split("\n\n") if part.strip()]

    lines = [
        full_name,
        "  |  ".join(contact_parts),
        date_line,
        "Hiring Manager",
        company,
        role,
        "",
        "Dear Hiring Manager,",
        "",
    ]
    for paragraph in body_paragraphs:
        lines.append(paragraph.replace("\n", " ").strip())
        lines.append("")
    lines.extend(
        [
            "Sincerely,",
            "",
            full_name,
            phone + ("  |  " + email if phone and email else email),
        ]
    )
    return "\n".join(lines).strip()


def render_cover_letter_text(
    templates_dir: Path,
    llm: LLMClient,
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    preferences: dict[str, Any],
    company_issue_brief: dict[str, Any] | None = None,
) -> str:
    role_track = detect_role_track(job_fields)
    if llm.enabled:
        payload = (
            "CANDIDATE_PROFILE:\n"
            f"{candidate_profile}\n\n"
            "JOB_FIELDS:\n"
            f"{job_fields}\n\n"
            "ROLE_TRACK:\n"
            f"{role_track}\n\n"
            "PREFERENCES:\n"
            f"{preferences}\n\n"
            "COMPANY_ISSUE_BRIEF:\n"
            f"{company_issue_brief or {}}"
        )
        try:
            generated = llm.text_completion(COVER_LETTER_PROMPT, payload)
            words = len(generated.split())
            if 250 <= words <= 350:
                body = _sanitize_cover_letter_body(generated, candidate_name=str(candidate_profile.get("identity", {}).get("full_name", "")).strip())
                return _format_cover_letter_document(candidate_profile, job_fields, body)
        except Exception:
            pass

    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=False)
    template = env.get_template("cover_letter_template.jinja2")
    fallback = template.render(candidate=candidate_profile, job=job_fields, role_track=role_track)
    if company_issue_brief and company_issue_brief.get("issue_summary"):
        fallback = (
            f"{fallback}\n\n"
            "I have also been following recent company priorities and would be excited to contribute by "
            f"{company_issue_brief.get('how_candidate_can_help', 'supporting measurable execution on key initiatives')}."
        )
    body = _sanitize_cover_letter_body(fallback, candidate_name=str(candidate_profile.get("identity", {}).get("full_name", "")).strip())
    if not body:
        body = _build_role_specific_fallback(candidate_profile, job_fields)
    return _format_cover_letter_document(candidate_profile, job_fields, body)
