from __future__ import annotations

from datetime import datetime
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .llm import COVER_LETTER_PROMPT, SAP_COVER_LETTER_PROMPT, LLMClient
from .tailoring import detect_role_track, detect_sector, extract_ats_keywords, rank_project_ids


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
        if "linkedin" in low or "github" in low or re.match(r"^\s*portfolio\s*:", low):
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
    collapsed = re.sub(
        r"\b(?:currently\s+)?(?:based|located|living)\s+in\s+(?:Jersey City|Hoboken|New Jersey|New York|NYC)[^.!?]*(?:[.!?]|$)",
        "",
        collapsed,
        flags=re.IGNORECASE,
    )
    collapsed = re.sub(
        r"\bI\s+(?:currently\s+)?(?:live|reside)\s+in\s+(?:Jersey City|Hoboken|New Jersey|New York|NYC)[^.!?]*(?:[.!?]|$)",
        "",
        collapsed,
        flags=re.IGNORECASE,
    )
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return _polish_paragraphs(collapsed.strip())


def _polish_cover_letter_text(text: str) -> str:
    replacements = [
        (r"\bsap\s+cpi\b", "SAP CPI"),
        (r"\bsap\s+s/4hana\b", "SAP S/4HANA"),
        (r"\bs/4hana\b", "S/4HANA"),
        (r"\bsap\b", "SAP"),
        (r"\bllm\b", "LLM"),
        (r"\bai/ml\b", "AI/ML"),
        (r"\bai\b", "AI"),
        (r"\bml\b", "ML"),
        (r"\bkpi\b", "KPI"),
        (r"\bpython\b", "Python"),
        (r"\bpyspark\b", "PySpark"),
        (r"\bfinbert\b", "FinBERT"),
        (r"\bmysql\b", "MySQL"),
        (r"\bvuejs\b", "Vue.js"),
        (r"\bjavascript\b", "JavaScript"),
        (r"\bphp\b", "PHP"),
        (r"\baws\b", "AWS"),
        (r"\bsql\b", "SQL"),
        (r"\bgit\b", "Git"),
    ]
    polished = str(text or "").strip()
    for pattern, value in replacements:
        polished = re.sub(pattern, value, polished, flags=re.IGNORECASE)
    polished = re.sub(r"\s+", " ", polished)
    polished = re.sub(r"\s+([,.;:])", r"\1", polished)
    polished = re.sub(r"\bLLM-Based\b", "LLM-based", polished)
    polished = re.sub(r"([.!?]),", r"\1", polished)
    polished = re.sub(r"\.\s+(which|and|while|with)\b", r", \1", polished, flags=re.IGNORECASE)
    polished = re.sub(r"%\.", "%", polished)
    polished = re.sub(r"\.{2,}", ".", polished)
    polished = re.sub(r"\s*/\s*", "/", polished)
    return polished.strip()


def _polish_paragraphs(text: str) -> str:
    paragraphs = [p.strip() for p in str(text or "").split("\n\n") if p.strip()]
    return "\n\n".join(_polish_cover_letter_text(p) for p in paragraphs if p.strip())


def _company_display(job_fields: dict[str, Any]) -> str:
    return str(job_fields.get("company", "")).strip() or str(job_fields.get("company_hint", "")).strip() or "the company"


def _role_display(job_fields: dict[str, Any]) -> str:
    return str(job_fields.get("title", "")).strip() or str(job_fields.get("job_title", "")).strip() or "the role"


def _job_location_corpus(job_fields: dict[str, Any]) -> str:
    return " ".join(
        str(job_fields.get(key, ""))
        for key in ("location", "title", "summary", "job_text", "description")
    ).lower()


def _is_bay_area_role(job_fields: dict[str, Any]) -> bool:
    hay = _job_location_corpus(job_fields)
    bay_terms = (
        "san francisco",
        "bay area",
        "sf bay",
        "south bay",
        "east bay",
        "san jose",
        "mountain view",
        "palo alto",
        "menlo park",
        "redwood city",
        "san mateo",
        "oakland",
        "berkeley",
        "sunnyvale",
        "santa clara",
        "fremont",
        "cupertino",
    )
    return any(term in hay for term in bay_terms)


def _is_remote_role(job_fields: dict[str, Any]) -> bool:
    return bool(re.search(r"\b(remote|work from home|distributed)\b", _job_location_corpus(job_fields)))


def _cover_letter_location(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    if _is_bay_area_role(job_fields):
        return "San Francisco Bay Area"
    identity = candidate_profile.get("identity", {}) or {}
    current = _compact_location(str(identity.get("location", "")).strip()) or "Antioch, CA"
    if _is_remote_role(job_fields):
        return current
    return current


def _location_sentence(job_fields: dict[str, Any]) -> str:
    if _is_bay_area_role(job_fields):
        return "Already based in the San Francisco Bay Area, I can contribute with useful proximity to Bay Area teams and customers."
    if _is_remote_role(job_fields):
        return "I am based in Antioch, CA and comfortable collaborating with distributed teams."
    return ""


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


def _project_records(candidate_profile: dict[str, Any], job_fields: dict[str, Any], limit: int = 2) -> list[dict[str, Any]]:
    projects = [p for p in (candidate_profile.get("academic_projects", []) or []) if isinstance(p, dict)]
    by_id = {str(p.get("id", "")).strip(): p for p in projects}
    ordered: list[dict[str, Any]] = []
    suggested = [str(pid).strip() for pid in (job_fields.get("suggested_project_ids", []) or []) if str(pid).strip()]
    if not suggested:
        suggested = rank_project_ids(
            candidate_profile,
            job_fields,
            extract_ats_keywords(job_fields),
            detect_sector(job_fields),
            detect_role_track(job_fields),
        )
    for project_id in suggested:
        project = by_id.get(str(project_id).strip())
        if project and project not in ordered:
            ordered.append(project)
    for project in projects:
        if project not in ordered:
            ordered.append(project)
    return ordered[: max(1, limit)]


def _project_sentence(project: dict[str, Any]) -> str:
    name = _polish_cover_letter_text(str(project.get("name", "")).strip())
    description = _polish_cover_letter_text(str(project.get("description", "")).strip()).rstrip(".")
    if not description:
        bullets = [str(item).strip() for item in (project.get("bullets", []) or []) if str(item).strip()]
        description = _polish_cover_letter_text(bullets[0]).rstrip(".") if bullets else ""
    if name and description:
        return f"{name}, where I {description[0].lower() + description[1:] if len(description) > 1 else description.lower()}"
    return name or description


def _certification_summary(candidate_profile: dict[str, Any]) -> str:
    certifications = [str(item).strip() for item in (candidate_profile.get("certifications", []) or []) if str(item).strip()]
    preferred = [
        cert
        for cert in certifications
        if any(term in cert.lower() for term in ("aws certified ai", "ibm data science", "aws data engineering"))
    ]
    if not preferred:
        return ""
    cleaned = [re.sub(r"\s*\(\d{4}\)\s*$", "", cert).strip() for cert in preferred[:2]]
    if len(cleaned) == 1:
        return f"I also hold the {cleaned[0]} certification."
    return f"I also hold the {cleaned[0]} certification and the {cleaned[1]}."


def _contact_closing(candidate_profile: dict[str, Any]) -> str:
    identity = candidate_profile.get("identity", {}) or {}
    phone = str(identity.get("phone", "")).strip()
    email = str(identity.get("email", "")).strip()
    contact = " or ".join(part for part in (phone, email) if part)
    closing = "I would welcome the opportunity to discuss how my skills and projects align with what your team is building."
    if contact:
        closing += f" I am available at your convenience and can be reached at {contact}."
    return closing


def _build_sap_fallback(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    role = _role_display(job_fields)
    company = _company_display(job_fields)
    facts = candidate_profile.get("cover_letter_facts", {}).get("sap", {}) or {}
    identity = candidate_profile.get("identity", {}) or {}
    phone = str(identity.get("phone", "")).strip()
    email = str(identity.get("email", "")).strip()
    experience = str(facts.get("experience_summary", "")).strip()
    standout = str(facts.get("standout_work", "")).strip()
    delivery = [str(item).strip().rstrip(".") for item in (facts.get("delivery_evidence", []) or []) if str(item).strip()]
    principle = str(facts.get("delivery_principle", "")).strip()
    certifications = [str(item).strip() for item in (facts.get("preferred_certifications", []) or []) if str(item).strip()]
    education = str(facts.get("education_summary", "")).strip()

    if not experience:
        experience = (
            "I am an SAP integration and enterprise data professional with 4+ years of industry experience building "
            "reliable integrations and production data workflows across SAP enterprise systems."
        )
    if not standout:
        sap_projects = [
            project
            for project in (candidate_profile.get("academic_projects", []) or [])
            if isinstance(project, dict)
            and any(
                term in " ".join(str(project.get(key, "")) for key in ("name", "description", "bullets")).lower()
                for term in ("sap", "cpi", "s/4hana", "pi/po", "integration suite")
            )
        ]
        if sap_projects:
            standout = _project_sentence(sap_projects[0])
    if not delivery:
        delivery = [
            _polish_cover_letter_text(str(bullet.get("text", ""))).rstrip(".")
            for exp in (candidate_profile.get("experience", []) or [])
            if isinstance(exp, dict)
            for bullet in (exp.get("bullets", []) or [])
            if isinstance(bullet, dict)
            and any(
                term in str(bullet.get("text", "")).lower()
                for term in ("sap", "cpi", "s/4hana", "pi/po", "integration")
            )
        ][:4]
    if not certifications:
        certifications = [
            str(item).strip()
            for item in (candidate_profile.get("certifications", []) or [])
            if "sap" in str(item).lower() or "integration suite" in str(item).lower()
        ][:3]
    if not education:
        education_line = _education_line(candidate_profile)
        if education_line:
            education = f"I completed {education_line}."

    intro = (
        f"{company}'s {role} role is compelling because dependable SAP integration work only creates value when it is stable, "
        "traceable, and easy for teams to operate after launch."
    )
    if experience:
        intro += f" {experience}"

    evidence = "My standout work for this role is " + (standout or "my SAP integration delivery across enterprise environments")
    evidence = evidence.rstrip(".") + "."

    broader = "Beyond that, I have delivered across the full integration lifecycle."
    if delivery:
        broader += " " + ". ".join(delivery) + "."
    if principle:
        broader += f" {principle}"

    why_company = (
        f"I want to bring this experience to {company} because the {role} role combines enterprise integration depth "
        "with dependable, measurable delivery."
    )
    if certifications:
        if len(certifications) == 1:
            why_company += f" I hold the {certifications[0]} certification."
        else:
            why_company += f" I hold {', '.join(certifications[:-1])}, along with {certifications[-1]}."
    if education:
        why_company += f" {education}"
    why_company += " I am ready to contribute from day one."

    closing = "I would welcome the opportunity to discuss how my experience aligns with what your team is building."
    contact = " or ".join(part for part in (phone, email) if part)
    if contact:
        closing += f" I am available at your convenience and can be reached at {contact}."
    return "\n\n".join([intro, evidence, broader, why_company, closing])


def _company_interest(company: str, role_track: str, job_fields: dict[str, Any]) -> str:
    corpus = " ".join(
        str(job_fields.get(key, ""))
        for key in ("title", "summary", "job_text", "description")
    ).lower()
    if role_track == "genai_engineer":
        themes = []
        if any(term in corpus for term in ("rag", "retrieval", "embedding", "vector")):
            themes.append("retrieval and grounded generation")
        if any(term in corpus for term in ("evaluation", "observability", "monitoring", "governance")):
            themes.append("evaluation and operational governance")
        if any(term in corpus for term in ("real-time", "inference", "api", "service")):
            themes.append("production AI services")
        selected = themes[:3]
        if len(selected) > 1:
            focus = ", ".join(selected[:-1]) + f", and {selected[-1]}"
        else:
            focus = selected[0] if selected else "production GenAI delivery"
        return f"I want to bring this experience to {company} because this role's focus on {focus} matches the way I build: end to end, measurable, and production-minded."
    if role_track == "data_scientist":
        return f"I want to bring this experience to {company} because the role connects applied modeling and evaluation with decisions and products that create measurable value."
    if role_track == "data_engineer":
        return f"I want to bring this experience to {company} because the role emphasizes reliable data foundations, scalable pipelines, and production systems that downstream teams can trust."
    if role_track == "sap_consultant":
        return f"I want to bring this experience to {company} because the role combines enterprise integration, dependable delivery, and measurable transformation outcomes."
    return f"I want to bring this experience to {company} because the role combines hands-on technical execution with measurable business impact."


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


def _first_genai_experience(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    preferred_terms = ("llm", "generative ai", "gemini", "prompt", "model", "evaluation", "reasoning")
    sap_terms = ("sap", "cpi", "s/4hana", "btp")
    suggested = [str(item) for item in (job_fields.get("suggested_bullets", []) or [])]
    candidates: list[str] = []
    for bullet_id in suggested:
        text = _find_bullet(candidate_profile, bullet_id)
        if text:
            candidates.append(text)
    for exp in candidate_profile.get("experience", []) or []:
        for bullet in exp.get("bullets", []) or []:
            if isinstance(bullet, dict) and bullet.get("text"):
                candidates.append(str(bullet.get("text", "")).strip())
    for text in candidates:
        lowered = text.lower()
        if any(term in lowered for term in preferred_terms) and not any(term in lowered for term in sap_terms):
            return text
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


def _evidence_phrase(text: str, fallback: str) -> str:
    clean = _polish_cover_letter_text(text or fallback)
    if not clean:
        return fallback
    clean = clean.rstrip(" .")
    return clean[0].lower() + clean[1:] if len(clean) > 1 else clean.lower()


def _project_evidence_phrase(text: str) -> str:
    clean = _polish_cover_letter_text(text)
    if not clean:
        return ""
    if ":" in clean:
        name, detail = [part.strip() for part in clean.split(":", 1)]
        name = re.sub(r"\bLLM-Based\b", "LLM-based", name)
        name = name.replace("Financial Sentiment Analysis", "financial sentiment analysis")
        name = name.replace("Using", "using")
        detail = detail.rstrip(" .")
        if detail:
            detail = detail[0].lower() + detail[1:] if len(detail) > 1 else detail.lower()
            article = "an" if name[:1].lower() in {"a", "e", "i", "o", "u"} or name.lower().startswith("llm") else "a"
            if " using " in name.lower():
                before, after = re.split(r"\s+using\s+", name, maxsplit=1, flags=re.IGNORECASE)
                return f"{article} {before} project using {after} where I {detail}"
            return f"{article} {name} project where I {detail}"
    return _evidence_phrase(clean, clean)


def _build_role_specific_fallback(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    role = _role_display(job_fields)
    company = _company_display(job_fields)
    role_track = detect_role_track(job_fields)
    if role_track == "sap_consultant":
        return _build_sap_fallback(candidate_profile, job_fields)
    edu = _education_line(candidate_profile)
    experience_line = (
        _first_genai_experience(candidate_profile, job_fields)
        if role_track == "genai_engineer"
        else _first_relevant_experience(candidate_profile, job_fields)
    )
    projects = _project_records(candidate_profile, job_fields)
    primary_project = _project_sentence(projects[0]) if projects else ""
    supporting_projects = [_project_sentence(project) for project in projects[1:2]]
    supporting_projects = [item for item in supporting_projects if item]

    if role_track == "sap_consultant":
        intro = (
            f"{company}'s {role} role stands out because it calls for SAP integration work that is reliable in production, not just correct in a test flow. "
            "I am an enterprise integration and data engineering professional with 4+ years of industry experience "
            "building reliable SAP integrations, automated data workflows, and production monitoring systems. My background combines "
            "hands-on delivery at Accenture and LTIMindtree with independently built engineering projects."
        )
    elif role_track == "genai_engineer":
        intro = (
            f"{company}'s {role} role is interesting to me because it sits where useful AI systems are actually proven: retrieval, agents, evaluation, and production delivery. "
            "I am an applied AI and machine learning engineer with 4+ years of industry experience building "
            "LLM applications, RAG pipelines, evaluation workflows, and production data systems. My background combines hands-on "
            "data engineering at Accenture and LTIMindtree, applied ML research at Stevens Institute of Technology, and independently built AI systems."
        )
    elif role_track == "data_scientist":
        intro = (
            f"{company}'s {role} role is compelling because it connects modeling decisions with measurable product and business outcomes. "
            "I am a data scientist and machine learning engineer with 4+ years of industry experience across "
            f"analytics, production data pipelines, and applied modeling, supported by {edu or 'graduate training in data science'}."
        )
    elif role_track == "data_engineer":
        intro = (
            f"{company}'s {role} role stands out because strong data engineering is the difference between models, dashboards, and operations people can trust. "
            "I am a data engineer with 4+ years of industry experience building reliable pipelines, improving "
            "data quality, and delivering analytics-ready workflows across enterprise systems."
        )
    elif role_track == "business_analyst":
        intro = (
            f"{company}'s {role} role interests me because it depends on turning ambiguous business needs into clear requirements, metrics, and decisions. "
            "My background combines analytics, reporting, and stakeholder-facing problem solving, which aligns well "
            "with roles that require translating business needs into measurable decisions and process improvements."
        )
    elif role_track == "market_analyst":
        intro = (
            f"{company}'s {role} role is interesting to me because it depends on finding patterns early and turning them into practical decisions. "
            "My experience in analytics and forecasting aligns well with roles focused on market trends, performance analysis, "
            "and turning data into strategic recommendations."
        )
    else:
        intro = (
            f"{company}'s {role} role interests me because it combines hands-on technical execution with measurable business impact. "
            "I bring a practical analytics and engineering foundation, with experience turning raw data into "
            "clear insights, reliable workflows, and stakeholder-ready reporting."
        )

    if primary_project:
        evidence = (
            f"My standout project for this role is {primary_project}. I built it to address a practical engineering problem, "
            "with emphasis on repeatable evaluation, reliable implementation, and results that can be inspected rather than assumed."
        )
    elif role_track == "sap_consultant":
        evidence = f"In my professional experience, {_evidence_phrase(experience_line, 'I have delivered SAP-focused integration work across enterprise systems')}."
    else:
        evidence = f"My strongest relevant work reflects {_evidence_phrase(experience_line, 'hands-on technical delivery across data and analytics systems')}."

    if supporting_projects:
        project_list = "; ".join(supporting_projects)
        broader_evidence = f"A second relevant project is {project_list}."
    else:
        broader_evidence = "Beyond individual projects, I bring production experience across data quality, automation, monitoring, and cross-functional delivery."
    if experience_line:
        broader_evidence += f" In my professional work, I {_evidence_phrase(experience_line, experience_line)}."
    if role_track == "genai_engineer":
        broader_evidence += " I focus on systems that are grounded, testable, observable, and ready to support real users."
    elif role_track == "data_engineer":
        broader_evidence += " I focus on systems that remain reliable under real operational demands."
    elif role_track == "sap_consultant":
        broader_evidence += " I focus on integrations that remain stable, traceable, and maintainable in production."
    elif role_track == "business_analyst":
        broader_evidence += (
            f"My experience includes {_evidence_phrase(experience_line, 'analytics and reporting work across cross-functional teams')}, "
            "which strengthened my ability to connect stakeholder needs with structured analysis, KPI reporting, and decision support."
        )
    elif role_track == "market_analyst":
        broader_evidence += (
            f"My experience includes {_evidence_phrase(experience_line, 'forecasting and analytics work tied to business outcomes')}, "
            "which strengthened my ability to analyze trends, interpret patterns, and support strategic decisions with data."
        )

    why_company = _company_interest(company, role_track, job_fields)
    location_line = _location_sentence(job_fields)
    if location_line:
        why_company += f" {location_line}"
    certification_line = _certification_summary(candidate_profile)
    if certification_line:
        why_company += f" {certification_line}"
    if edu:
        why_company += f" I completed {edu}."
    why_company += " I am ready to contribute from day one."

    closing = _contact_closing(candidate_profile)
    return "\n\n".join([intro.strip(), evidence.strip(), broader_evidence.strip(), why_company.strip(), closing])


def _format_cover_letter_document(candidate_profile: dict[str, Any], job_fields: dict[str, Any], body: str) -> str:
    identity = candidate_profile.get("identity", {}) or {}
    links = candidate_profile.get("links", {}) or {}
    full_name = str(identity.get("full_name", "")).strip()
    phone = str(identity.get("phone", "")).strip()
    email = str(identity.get("email", "")).strip()
    linkedin = _display_link(str(links.get("linkedin", "")).strip())
    location = _cover_letter_location(candidate_profile, job_fields)
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
        lines.append(_polish_cover_letter_text(paragraph.replace("\n", " ").strip()))
        lines.append("")
    lines.extend(
        [
            "Sincerely,",
            "",
            full_name,
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
            prompt = SAP_COVER_LETTER_PROMPT if role_track == "sap_consultant" else COVER_LETTER_PROMPT
            generated = llm.text_completion(prompt, payload)
            words = len(generated.split())
            min_words, max_words = (375, 525) if role_track == "sap_consultant" else (250, 350)
            if min_words <= words <= max_words:
                body = _sanitize_cover_letter_body(generated, candidate_name=str(candidate_profile.get("identity", {}).get("full_name", "")).strip())
                return _format_cover_letter_document(candidate_profile, job_fields, body)
        except Exception:
            pass

    fallback = _build_role_specific_fallback(candidate_profile, job_fields)
    if not fallback.strip():
        env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=False)
        template = env.get_template("cover_letter_template.jinja2")
        fallback = template.render(candidate=candidate_profile, job=job_fields, role_track=role_track)
    if (
        company_issue_brief
        and str(company_issue_brief.get("issue_summary", "")).strip()
        and str(company_issue_brief.get("how_candidate_can_help", "")).strip()
    ):
        fallback = (
            f"{fallback}\n\n"
            "I have also been following recent company priorities and would be excited to contribute by "
            f"{company_issue_brief.get('how_candidate_can_help', 'supporting measurable execution on key initiatives')}."
    )
    body = _sanitize_cover_letter_body(fallback, candidate_name=str(candidate_profile.get("identity", {}).get("full_name", "")).strip())
    if not body:
        body = _build_role_specific_fallback(candidate_profile, job_fields)
    return _format_cover_letter_document(candidate_profile, job_fields, _polish_paragraphs(body))
