from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


MONTH_NAME = {
    "01": "Jan",
    "02": "Feb",
    "03": "Mar",
    "04": "Apr",
    "05": "May",
    "06": "Jun",
    "07": "Jul",
    "08": "Aug",
    "09": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dec",
}


def _is_sap_role(job_fields: dict[str, Any]) -> bool:
    title = str(job_fields.get("job_title") or job_fields.get("title") or "").lower()
    text = str(job_fields.get("job_text") or job_fields.get("description") or "").lower()
    hay = f"{title}\n{text}"
    sap_terms = ("sap", "cpi", "s/4hana", "s4hana", "integration suite", "btp")
    return any(term in hay for term in sap_terms)


def _resolve_header_location(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    base = str(candidate_profile.get("identity", {}).get("location", "")).strip()
    loc = str(job_fields.get("location") or "").lower()
    title = str(job_fields.get("job_title") or job_fields.get("title") or "").lower()
    text = str(job_fields.get("job_text") or job_fields.get("description") or "").lower()
    hay = f"{loc}\n{title}\n{text}"
    if _is_india_job(job_fields):
        return "Mumbai, India"
    if "new york" in hay or re.search(r"\bny\b", hay):
        return "NY"
    if "california" in hay or re.search(r"\bca\b", hay):
        return "Antioch, CA"
    if "new jersey" in hay or re.search(r"\bnj\b", hay):
        return "Jersey City"
    return base


def _is_india_job(job_fields: dict[str, Any]) -> bool:
    loc = str(job_fields.get("location") or "").lower()
    title = str(job_fields.get("job_title") or job_fields.get("title") or "").lower()
    text = str(job_fields.get("job_text") or job_fields.get("description") or "").lower()
    hay = f"{loc}\n{title}\n{text}"
    india_terms = (
        "india",
        "mumbai",
        "pune",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "chennai",
        "gurgaon",
        "gurugram",
        "noida",
        "delhi",
    )
    return any(term in hay for term in india_terms)


def _resolve_header_phone(candidate_profile: dict[str, Any], job_fields: dict[str, Any]) -> str:
    if _is_india_job(job_fields):
        return "+91 7350902697"
    return str(candidate_profile.get("identity", {}).get("phone", "")).strip()


def _to_mmm_yyyy(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower() in {"present", "current"}:
        return "Present"
    m = re.match(r"^(\d{4})[-/](\d{2})$", raw)
    if m:
        mm = m.group(2)
        return f"{MONTH_NAME.get(mm, mm)} {m.group(1)}"
    m = re.match(r"^([A-Za-z]{3,9})\s+(\d{4})$", raw)
    if m:
        mm = MONTH_MAP.get(m.group(1)[:3].lower())
        if mm:
            return f"{MONTH_NAME.get(mm, mm)} {m.group(2)}"
    return raw


def render_resume_text(
    templates_dir: Path,
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    selected_bullet_ids: list[str],
    suggested_project_ids: list[str],
    rewritten_bullets: dict[str, str],
    rewritten_projects: dict[str, str],
    ats_keywords: list[str],
) -> str:
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=False)
    template = env.get_template("resume_template.jinja2")

    experience = []
    for entry in candidate_profile.get("experience", []):
        selected = entry.get("bullets", [])
        revised = []
        for bullet in selected:
            bid = bullet.get("id")
            revised.append(
                {
                    **bullet,
                    "text": rewritten_bullets.get(bid, bullet.get("text", "")),
                }
            )
        filtered = {
            **entry,
            "start_date_fmt": _to_mmm_yyyy(str(entry.get("start_date", ""))),
            "end_date_fmt": _to_mmm_yyyy(str(entry.get("end_date", ""))),
            "bullets": revised,
        }
        experience.append(filtered)

    education = []
    for edu in candidate_profile.get("education", []):
        education.append(
            {
                **edu,
                "start_date_fmt": _to_mmm_yyyy(str(edu.get("start_date", ""))),
                "end_date_fmt": _to_mmm_yyyy(str(edu.get("end_date", "") or edu.get("graduation_date", ""))),
            }
        )

    projects = []
    ordered_project_ids = [pid for pid in suggested_project_ids if pid]
    if not ordered_project_ids:
        ordered_project_ids = [str(p.get("id", "")) for p in candidate_profile.get("academic_projects", [])]
    project_map = {
        str(proj.get("id", "")): proj
        for proj in candidate_profile.get("academic_projects", [])
        if isinstance(proj, dict) and proj.get("id")
    }
    chosen_project_ids: list[str] = []
    for pid in ordered_project_ids:
        if pid in project_map and pid not in chosen_project_ids:
            chosen_project_ids.append(pid)
    for pid in project_map.keys():
        if pid not in chosen_project_ids:
            chosen_project_ids.append(pid)
    chosen_project_ids = chosen_project_ids[:3]
    for pid in chosen_project_ids:
        proj = project_map.get(pid, {})
        default_desc = str(proj.get("description", "")).strip()
        original_bullets = [
            str(x).strip()
            for x in (proj.get("bullets", []) or [])
            if str(x).strip()
        ]
        rewritten = rewritten_projects.get(pid, "").strip()
        if rewritten:
            bullets = [rewritten]
        elif original_bullets:
            bullets = [original_bullets[0]]
        else:
            bullets = [default_desc] if default_desc else []
        projects.append(
            {
                **proj,
                "description": rewritten or default_desc,
                "bullets": bullets,
            }
        )

    base_skills = [str(s).strip() for s in candidate_profile.get("skills", []) if str(s).strip()]
    prioritized_skills = []
    for keyword in ats_keywords:
        if keyword and keyword not in prioritized_skills:
            prioritized_skills.append(keyword)
    for skill in base_skills:
        if skill not in prioritized_skills:
            prioritized_skills.append(skill)

    tech_groups = candidate_profile.get("technical_skills", []) or []
    normalized_existing = {
        str(item).strip().lower()
        for group in tech_groups
        if isinstance(group, dict)
        for item in (group.get("items", []) or [])
    }
    missing_keywords = [k for k in ats_keywords if str(k).strip().lower() not in normalized_existing]
    missing_keywords = missing_keywords[:12]
    technical_skills = []
    injected = False
    for group in tech_groups:
        if not isinstance(group, dict):
            continue
        items = [str(x).strip() for x in (group.get("items", []) or []) if str(x).strip()]
        if not injected and missing_keywords and "Data Engineering" in str(group.get("category", "")):
            items.extend([kw for kw in missing_keywords if kw not in items])
            injected = True
        technical_skills.append({**group, "items": items[:24]})
    if not injected and missing_keywords:
        technical_skills.append({"category": "Role-Aligned Keywords", "items": missing_keywords[:12]})

    certifications = [str(c).strip() for c in candidate_profile.get("certifications", []) if str(c).strip()]
    if _is_sap_role(job_fields):
        sap_certs = [c for c in certifications if "sap" in c.lower()]
        non_sap_certs = [c for c in certifications if "sap" not in c.lower()]
        certifications = sap_certs + non_sap_certs

    payload = {
        "candidate": {
            **candidate_profile,
            "identity": {
                **candidate_profile.get("identity", {}),
                "location": _resolve_header_location(candidate_profile, job_fields),
                "phone": _resolve_header_phone(candidate_profile, job_fields),
            },
            "experience": experience,
            "education": education,
            "academic_projects": projects,
            "technical_skills": technical_skills,
            "skills": prioritized_skills[:24],
            "certifications": certifications,
        },
        "job": job_fields,
    }
    return template.render(**payload)
