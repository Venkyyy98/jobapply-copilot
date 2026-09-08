from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .tailoring import detect_role_track


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
    # Prefer the parsed job location over full page text so "similar jobs" does not change the resume header.
    hay = f"{loc}\n{title}\n{text[:2000]}"
    if _is_india_job(job_fields):
        return "Mumbai, India"
    if re.search(r"\b(san francisco|bay area|mountain view|palo alto|san jose|sunnyvale|santa clara|fremont|oakland|california|ca)\b", hay):
        return "San Francisco Bay Area, CA"
    if "remote" in hay:
        return "Antioch, CA"
    return base


def _is_india_job(job_fields: dict[str, Any]) -> bool:
    loc = str(job_fields.get("location") or "").lower()
    title = str(job_fields.get("job_title") or job_fields.get("title") or "").lower()
    text = str(job_fields.get("job_text") or job_fields.get("description") or "").lower()
    hay = loc if loc else f"{title}\n{text[:2000]}"
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
    raw = str(candidate_profile.get("identity", {}).get("phone", "")).strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


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


def _normalize_target_title(job_fields: dict[str, Any]) -> str:
    raw_title = str(job_fields.get("title") or job_fields.get("job_title") or "").strip()
    lowered = raw_title.lower()
    if re.search(r"\b(ai\s*/\s*ml|ml|machine learning)\b", lowered) and re.search(
        r"\b(engineer|engineering|developer|architect|consultant)\b", lowered
    ):
        return "Machine Learning Engineer"
    if re.search(r"\b(ai|artificial intelligence|genai|generative ai)\b", lowered) and re.search(
        r"\b(engineer|engineering|developer|architect|consultant)\b", lowered
    ):
        return "AI Engineer"
    if "senior data analyst" in lowered:
        return "Senior Data Analyst"
    if "data scientist" in lowered:
        return "Data Scientist"
    if "data engineer" in lowered or "analytics engineer" in lowered:
        return "Data Engineer"
    if "business analyst" in lowered:
        return "Business Analyst"
    if "market analyst" in lowered:
        return "Market Analyst"
    if "data analyst" in lowered:
        return "Data Analyst"
    if "sap" in lowered:
        return "SAP Consultant"
    if "software engineer" in lowered or "software developer" in lowered:
        return "Software Engineer"
    if "research scientist" in lowered or "applied scientist" in lowered:
        return "Research Scientist"
    if "quantitative" in lowered:
        return "Quantitative Analyst"
    if "product analyst" in lowered:
        return "Product Analyst"
    if "business intelligence" in lowered or "bi analyst" in lowered:
        return "Business Intelligence Analyst"

    role_track = detect_role_track(job_fields)
    return {
        "software_engineer": "Software Engineer",
        "genai_engineer": "AI Engineer",
        "data_scientist": "Data Scientist",
        "data_engineer": "Data Engineer",
        "data_analyst": "Data Analyst",
        "business_analyst": "Business Analyst",
        "market_analyst": "Market Analyst",
        "sap_consultant": "SAP Consultant",
    }.get(role_track, raw_title or "Data Analyst")


ACTION_VERBS = {
    "applied",
    "automated",
    "built",
    "collected",
    "conducted",
    "converted",
    "designed",
    "developed",
    "directed",
    "engineered",
    "implemented",
    "improved",
    "integrated",
    "led",
    "partnered",
    "refactored",
}


def _clean_resume_line(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^[•\\-]\\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_fragment_bullet(text: str, previous: str | None = None) -> bool:
    clean = _clean_resume_line(text)
    if not clean:
        return False
    first_word = re.split(r"\s+", clean, maxsplit=1)[0].lower().strip(",;:")
    if first_word in ACTION_VERBS and len(clean.split()) >= 5:
        return False
    if previous and previous[-1:] not in {".", "!", "?"}:
        return True
    if clean[0].islower():
        return True
    if len(clean.split()) <= 4 and first_word not in ACTION_VERBS:
        return True
    return False


def _join_fragment(previous: str, fragment: str) -> str:
    left = previous.rstrip(" ,;")
    right = _clean_resume_line(fragment).lstrip(" ,;")
    if not right:
        return left
    if right[0].islower() or right.lower().startswith(("and ", "or ")):
        return f"{left}, {right}"
    return f"{left} {right}"


def _normalize_project_bullets(raw_bullets: list[Any]) -> list[str]:
    bullets: list[str] = []
    for raw in raw_bullets:
        text = _clean_resume_line(raw)
        if not text:
            continue
        if bullets and _is_fragment_bullet(text, bullets[-1]):
            bullets[-1] = _join_fragment(bullets[-1], text)
        else:
            bullets.append(text)
    return bullets


def _rewrite_summary(candidate_profile: dict[str, Any], job_fields: dict[str, Any], ats_keywords: list[str]) -> str:
    role_track = detect_role_track(job_fields)
    opening = {
        "software_engineer": "Software Engineer",
        "genai_engineer": "AI/ML Engineer",
        "data_scientist": "Data Scientist",
        "data_engineer": "Data Engineer",
        "data_analyst": "Data Analyst",
        "business_analyst": "Business Analyst",
        "market_analyst": "Market Analyst",
        "sap_consultant": "SAP Integration Consultant",
    }.get(role_track, _normalize_target_title(job_fields))
    domain_phrase = {
        "software_engineer": "backend services, cloud automation, production data workflows, API integrations, and ML infrastructure support",
        "genai_engineer": "production LLM applications, RAG pipelines, evaluation frameworks, agentic workflows, and secure AI services",
        "data_scientist": "predictive models, statistical analysis, NLP, forecasting, experimentation, and cloud analytics",
        "data_engineer": "scalable ETL pipelines, cloud data platforms, enterprise integrations, data quality, and analytics infrastructure",
        "data_analyst": "analytics workflows, KPI reporting, stakeholder dashboards, statistical analysis, and automation",
        "business_analyst": "requirements analysis, process improvement, stakeholder reporting, KPI analysis, and automation",
        "market_analyst": "market research, forecasting, segmentation, trend analysis, and executive reporting",
        "sap_consultant": "SAP CPI integrations, S/4HANA automation, enterprise data pipelines, validation, and operational reliability",
    }.get(role_track, "scalable data systems, predictive analytics, and automation solutions")
    # Keep job-posting keywords in Technical Skills, but make the summary read
    # like a professional statement rather than an ATS keyword dump.
    stack_by_role = {
        "software_engineer": ["Python", "Java", "REST APIs", "FastAPI", "AWS", "CloudFormation"],
        "genai_engineer": ["Python", "PyTorch", "LLMs", "RAG", "FastAPI", "AWS"],
        "data_scientist": ["Python", "SQL", "PyTorch", "PySpark", "NLP", "AWS"],
        "data_engineer": ["Python", "SQL", "Java", "MySQL", "Spark", "AWS"],
        "data_analyst": ["Python", "SQL", "Power BI", "Tableau", "statistics"],
        "business_analyst": ["SQL", "Power BI", "REST APIs", "data quality", "process automation"],
        "market_analyst": ["Python", "SQL", "forecasting", "segmentation", "Power BI"],
        "sap_consultant": ["Python", "SQL", "SAP CPI", "SAP BTP", "REST APIs", "AWS"],
    }
    stack_text = ", ".join(stack_by_role.get(role_track, ["Python", "SQL", "cloud technologies"]))
    education = candidate_profile.get("education", []) or []
    graduate = next((item for item in education if str(item.get("school", "")).startswith("Stevens")), {})
    gpa = str(graduate.get("gpa", "")).strip()
    academic_edge = f"M.S. in Data Science from Stevens Institute of Technology{f' (GPA {gpa})' if gpa else ''}"
    credential_phrase = " and an AWS Certified AI Practitioner certification" if role_track in {"genai_engineer", "data_scientist"} else ""
    company_scope = "Easley Dunn Productions, Accenture, and LTIMindtree" if role_track == "software_engineer" else "Accenture and LTIMindtree"
    return (
        f"{opening} with 4+ years of experience building {domain_phrase} across {company_scope}. "
        f"Combines enterprise delivery, an {academic_edge}, and applied AI/ML research{credential_phrase}. "
        f"Hands-on expertise in {stack_text}, with quantified results in data quality, pipeline performance, and production analytics."
    )


def _merge_lti_entries(
    candidate_profile: dict[str, Any],
    rewritten_bullets: dict[str, str],
    selected_bullet_ids: list[str],
    job_fields: dict[str, Any],
) -> list[dict[str, Any]]:
    merged_sources = []
    others = []
    for entry in candidate_profile.get("experience", []):
        company = str(entry.get("company", "")).lower()
        if "ltimindtree" in company or re.fullmatch(r".*\blti\b.*", company):
            merged_sources.append(entry)
        else:
            others.append(entry)

    rendered: list[dict[str, Any]] = []
    selected_set = set(selected_bullet_ids)
    target_title = _normalize_target_title(job_fields)

    def role_display_for(entry: dict[str, Any]) -> str:
        company = str(entry.get("company", "")).lower()
        if "accenture" in company:
            return target_title
        return str(entry.get("role", "")).strip() or "Data Analyst"

    def render_entry(entry: dict[str, Any]) -> dict[str, Any]:
        revised = []
        for bullet in entry.get("bullets", []):
            bid = bullet.get("id")
            revised.append({**bullet, "text": rewritten_bullets.get(bid, bullet.get("text", ""))})
        return {
            **entry,
            "start_date_fmt": _to_mmm_yyyy(str(entry.get("start_date", ""))),
            "end_date_fmt": _to_mmm_yyyy(str(entry.get("end_date", ""))),
            "role": role_display_for(entry),
            "bullets": revised,
        }

    for entry in others:
        rendered.append(render_entry(entry))

    if not merged_sources:
        return rendered

    merged_bullets: list[dict[str, Any]] = []
    for entry in merged_sources:
        for bullet in entry.get("bullets", []):
            if not isinstance(bullet, dict):
                continue
            bid = str(bullet.get("id", "")).strip()
            if not bid:
                continue
            merged_bullets.append(
                {
                    **bullet,
                    "text": rewritten_bullets.get(bid, bullet.get("text", "")),
                    "_selected": bid in selected_set,
                }
            )

    merged_bullets.sort(key=lambda b: (not b.get("_selected", False), str(b.get("id", ""))))
    merged_bullets = [{k: v for k, v in bullet.items() if not k.startswith("_")} for bullet in merged_bullets[:3]]

    start_dates = [str(entry.get("start_date", "")) for entry in merged_sources if str(entry.get("start_date", "")).strip()]
    end_dates = [str(entry.get("end_date", "")) for entry in merged_sources if str(entry.get("end_date", "")).strip()]
    merged_entry = {
        **merged_sources[0],
        "company": "LTI / LTIMindtree",
        "role": target_title,
        "start_date_fmt": _to_mmm_yyyy(min(start_dates)) if start_dates else "",
        "end_date_fmt": _to_mmm_yyyy(max(end_dates)) if end_dates else "",
        "bullets": merged_bullets,
    }

    insert_at = next((idx for idx, entry in enumerate(candidate_profile.get("experience", [])) if entry in merged_sources), len(rendered))
    rendered.insert(min(insert_at, len(rendered)), merged_entry)

    def date_key(entry: dict[str, Any]) -> str:
        raw = str(entry.get("start_date", "")).strip()
        if re.match(r"^\d{4}[-/]\d{2}$", raw):
            return raw
        m = re.match(r"^([A-Za-z]{3,9})\s+(\d{4})$", raw)
        if m:
            return f"{m.group(2)}-{MONTH_MAP.get(m.group(1)[:3].lower(), '01')}"
        return "0000-00"

    rendered.sort(key=date_key, reverse=True)
    return rendered


def _compact_certification_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s*\(\d{4}\)\s*$", "", text)
    text = re.sub(r"\s*-\s*Amazon Web Services\s*\|\s*.+$", "", text)
    text = re.sub(r"\s*-\s*IBM\s*/\s*Coursera\s*\|\s*.+$", "", text)
    text = re.sub(r"\s*-\s*Databricks\s*\|\s*.+$", "", text)
    text = text.replace("Certified", "Certified")
    text = text.replace("Developement", "Development")
    return text


def _should_include_certifications(
    summary: str,
    experience: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    technical_skills: list[dict[str, Any]],
) -> bool:
    experience_bullets = sum(len(exp.get("bullets", []) or []) for exp in experience)
    project_bullets = sum(len(project.get("bullets", []) or []) for project in projects)
    skill_items = sum(len(group.get("items", []) or []) for group in technical_skills)
    density_score = (
        experience_bullets * 3
        + project_bullets * 2
        + len(technical_skills) * 2
        + min(skill_items, 24) // 4
        + min(len(summary.split()), 40) // 8
    )
    return density_score <= 58


def _tailored_technical_skills(
    candidate_profile: dict[str, Any],
    ats_keywords: list[str],
    job_fields: dict[str, Any],
) -> list[dict[str, Any]]:
    role_track = detect_role_track(job_fields)
    category_priority = {
        "software_engineer": ["Programming Languages", "Data Engineering and Cloud Platforms", "Generative AI and LLMs", "Machine Learning", "Visualization and BI"],
        "genai_engineer": ["Generative AI and LLMs", "Machine Learning", "Programming Languages", "Data Engineering and Cloud Platforms", "Visualization and BI"],
        "data_engineer": ["Data Engineering and Cloud Platforms", "Programming Languages", "Visualization and BI", "Machine Learning", "Generative AI and LLMs"],
        "data_scientist": ["Machine Learning", "Programming Languages", "Generative AI and LLMs", "Data Engineering and Cloud Platforms", "Visualization and BI"],
        "data_analyst": ["Visualization and BI", "Programming Languages", "Data Engineering and Cloud Platforms", "Machine Learning", "Generative AI and LLMs"],
        "business_analyst": ["Visualization and BI", "Programming Languages", "Data Engineering and Cloud Platforms", "Machine Learning", "Generative AI and LLMs"],
        "market_analyst": ["Visualization and BI", "Machine Learning", "Programming Languages", "Data Engineering and Cloud Platforms", "Generative AI and LLMs"],
        "sap_consultant": ["Data Engineering and Cloud Platforms", "Programming Languages", "Visualization and BI", "Machine Learning", "Generative AI and LLMs"],
    }.get(role_track, [])
    keyword_text = " ".join(str(keyword).lower() for keyword in ats_keywords)
    keyword_tokens = {
        token
        for token in re.findall(r"[a-z0-9+#/]+", keyword_text)
        if len(token) > 2
    }

    def item_score(item: str) -> int:
        low = str(item).lower()
        if any(low == str(keyword).lower() for keyword in ats_keywords):
            return 2
        tokens = {token for token in re.findall(r"[a-z0-9+#/]+", low) if len(token) > 2}
        if tokens and tokens.intersection(keyword_tokens):
            return 1
        return 0

    source_items: dict[str, list[str]] = {}
    for idx, group in enumerate(candidate_profile.get("technical_skills", []) or []):
        if not isinstance(group, dict):
            continue
        items = [str(item).strip() for item in (group.get("items", []) or []) if str(item).strip()]
        ordered_items = sorted(enumerate(items), key=lambda pair: (-item_score(pair[1]), pair[0]))
        category = str(group.get("category", ""))
        source_items[category] = [item for _, item in ordered_items]

    if role_track == "software_engineer":
        flattened = {item.lower(): item for values in source_items.values() for item in values}

        def take(*names: str) -> list[str]:
            chosen: list[str] = []
            for name in names:
                value = flattened.get(name.lower(), name)
                if value and value not in chosen:
                    chosen.append(value)
            return chosen

        return [
            {"category": "Languages & Backend", "items": take("Python", "Java", "SQL", "Node.js", "TypeScript", "REST APIs", "FastAPI")[:7]},
            {
                "category": "Cloud & Infrastructure",
                "items": take(
                    "AWS",
                    "AWS Lambda",
                    "Amazon API Gateway",
                    "Amazon DynamoDB",
                    "Amazon Bedrock",
                    "AWS CDK",
                    "CloudFormation",
                    "Docker",
                    "CI/CD",
                )[:9],
            },
            {"category": "Databases", "items": take("PostgreSQL", "MySQL", "DynamoDB", "Snowflake")[:4]},
            {
                "category": "AI/ML Systems",
                "items": take(
                    "Machine Learning",
                    "Large Language Models (LLMs)",
                    "Retrieval-Augmented Generation (RAG)",
                    "LangChain",
                    "FAISS",
                    "PyTorch",
                    "Scikit-learn",
                )[:7],
            },
            {"category": "Enterprise Integration", "items": take("SAP CPI", "SAP BTP", "SAP PI/PO", "SAP S/4HANA", "OAuth 2.0", "SAML")[:6]},
        ]

    if role_track in {"genai_engineer", "data_scientist", "data_engineer"}:
        flattened = {item.lower(): item for values in source_items.values() for item in values}

        def take(*names: str) -> list[str]:
            chosen: list[str] = []
            for name in names:
                value = flattened.get(name.lower(), name)
                if value and value not in chosen:
                    chosen.append(value)
            return chosen

        return [
            {
                "category": "AI/ML & Agentic AI",
                "items": take(
                    "Multi-Agent Systems",
                    "Retrieval-Augmented Generation (RAG)",
                    "LangChain",
                    "FAISS",
                    "LLM Fine-Tuning",
                    "Prompt Engineering",
                    "PyTorch",
                    "TensorFlow",
                    "Scikit-learn",
                )[:9],
            },
            {"category": "Languages & Backend", "items": take("Python", "Java", "SQL", "Node.js", "REST APIs", "Bash")[:6]},
            {"category": "Databases", "items": take("MySQL", "PostgreSQL", "DynamoDB", "Snowflake")[:4]},
            {
                "category": "Cloud & DevOps",
                "items": take(
                    "AWS",
                    "Amazon Bedrock",
                    "AWS Lambda",
                    "Amazon SageMaker",
                    "S3",
                    "EC2",
                    "IAM",
                    "CloudFormation",
                    "Spark",
                    "Databricks",
                    "Docker",
                    "CI/CD",
                )[:12],
            },
            {"category": "GenAI APIs & Tools", "items": take("OpenAI API", "Anthropic Claude API", "AWS Bedrock", "FastAPI", "pytest")[:5]},
            {"category": "Enterprise Integration", "items": take("SAP CPI", "SAP BTP", "SAP PI/PO", "SAP S/4HANA", "OAuth 2.0", "SAML")[:6]},
        ]

    groups: list[tuple[int, dict[str, Any]]] = []
    for idx, group in enumerate(candidate_profile.get("technical_skills", []) or []):
        if not isinstance(group, dict):
            continue
        category = str(group.get("category", ""))
        max_items = {
            "Programming Languages": 7,
            "Machine Learning": 8,
            "Generative AI and LLMs": 6,
            "Data Engineering and Cloud Platforms": 10,
            "Visualization and BI": 6,
        }.get(category, 8)
        groups.append(
            (
                idx,
                {
                    **group,
                    "items": source_items.get(category, [])[:max_items],
                },
            )
        )

    def group_rank(pair: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        original_idx, group = pair
        category = str(group.get("category", ""))
        try:
            return (category_priority.index(category), original_idx)
        except ValueError:
            return (len(category_priority), original_idx)

    groups.sort(key=group_rank)
    return [group for _, group in groups]


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
    experience = _merge_lti_entries(candidate_profile, rewritten_bullets, selected_bullet_ids, job_fields)

    education = []
    for edu in candidate_profile.get("education", []):
        education.append(
            {
                **edu,
                "start_date_fmt": _to_mmm_yyyy(str(edu.get("start_date", ""))),
                "end_date_fmt": _to_mmm_yyyy(str(edu.get("end_date", "") or edu.get("graduation_date", ""))),
                "degree_display": {
                    "Master of Science": "M.S.",
                    "Bachelor of Engineering": "B.E.",
                    "Bachelor of Science": "B.S.",
                }.get(str(edu.get("degree", "")).strip(), str(edu.get("degree", "")).strip()),
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
    chosen_project_ids = chosen_project_ids[:2]
    for pid in chosen_project_ids:
        proj = project_map.get(pid, {})
        default_desc = _clean_resume_line(proj.get("description", ""))
        original_bullets = _normalize_project_bullets(list(proj.get("bullets", []) or []))
        rewritten = _clean_resume_line(rewritten_projects.get(pid, ""))
        if original_bullets:
            bullets = original_bullets[:2]
        elif rewritten:
            bullets = [rewritten]
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

    technical_skills = _tailored_technical_skills(candidate_profile, ats_keywords, job_fields)

    certifications = [str(c).strip() for c in candidate_profile.get("certifications", []) if str(c).strip()]
    if _is_sap_role(job_fields):
        sap_certs = [c for c in certifications if "sap" in c.lower()]
        non_sap_certs = [c for c in certifications if "sap" not in c.lower()]
        certifications = sap_certs + non_sap_certs
    else:
        certifications = [c for c in certifications if "sap" not in c.lower()]
    award_records = [c for c in certifications if any(term in c.lower() for term in ("award", "performer of the month"))]
    certifications = [c for c in certifications if c not in award_records]
    certifications_display = [_compact_certification_name(c) for c in certifications if _compact_certification_name(c)]
    awards_display = []
    for award in award_records:
        parts = [part.strip() for part in award.split("|") if part.strip()]
        if len(parts) > 1:
            label = parts[0].split(" - ")[0].strip()
            awards_display.append(f"{label}, {parts[-1]}")
        elif parts:
            awards_display.append(parts[0])
    summary_text = _rewrite_summary(candidate_profile, job_fields, ats_keywords)
    payload = {
        "candidate": {
            **candidate_profile,
            "summary": summary_text,
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
            "certifications_display": certifications_display[:5],
            "awards_display": awards_display,
        },
        "job": job_fields,
    }
    return template.render(**payload)
