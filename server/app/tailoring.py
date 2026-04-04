from __future__ import annotations

import re
from typing import Any

from .llm import CANDIDATE_BULLET_REWRITE_PROMPT, LLMClient, PROJECT_REWRITE_PROMPT, TAILORING_PLAN_PROMPT


def _profile_skill_set(candidate_profile: dict[str, Any]) -> set[str]:
    skills = candidate_profile.get("skills", [])
    out = set()
    for item in skills:
        if isinstance(item, str):
            out.add(item.lower())
    return out


def _base_answers(candidate_profile: dict[str, Any], preferences: dict[str, Any]) -> dict[str, str]:
    return {
        "work_authorization": preferences.get("work_authorization", "Please confirm manually."),
        "sponsorship_required": str(preferences.get("sponsorship_required", "unknown")),
        "preferred_location": preferences.get("preferred_locations", ["Please confirm manually"])[0],
        "linkedin": candidate_profile.get("links", {}).get("linkedin", ""),
        "github": candidate_profile.get("links", {}).get("github", ""),
    }


ROLE_KEYWORDS: dict[str, list[str]] = {
    "data_analyst": ["dashboard", "reporting", "bi", "power bi", "tableau", "sql", "analytics", "kpi"],
    "data_engineer": ["etl", "pipeline", "airflow", "spark", "databricks", "warehouse", "ingestion", "orchestration"],
    "data_scientist": ["machine learning", "model", "forecast", "classification", "regression", "nlp", "llm", "feature engineering"],
    "sap_consultant": ["sap", "cpi", "s/4hana", "btp", "integration", "odata", "idoc", "erp"],
}

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "healthcare": ["hospital", "healthcare", "clinical", "patient", "medical", "pharma", "ehr", "pneumonia"],
    "finance": ["finance", "financial", "bank", "banking", "investment", "trading", "portfolio", "risk", "fintech"],
    "sap": ["sap", "cpi", "s/4hana", "integration suite", "btp", "erp", "idata", "odata"],
}

SECTOR_PROJECT_BOOST: dict[str, list[str]] = {
    "healthcare": ["proj_5", "proj_2"],
    "finance": ["proj_1"],
    "sap": ["proj_4"],
}


def _job_corpus(job_fields: dict[str, Any]) -> str:
    parts: list[str] = [
        str(job_fields.get("title", "")),
        str(job_fields.get("company", "")),
        str(job_fields.get("summary", "")),
    ]
    parts.extend([str(x) for x in job_fields.get("requirements", [])])
    parts.extend([str(x) for x in job_fields.get("responsibilities", [])])
    parts.extend([str(x) for x in job_fields.get("skills", [])])
    return " ".join(parts).lower()


def detect_sector(job_fields: dict[str, Any]) -> str:
    corpus = _job_corpus(job_fields)
    best = "generic"
    best_score = 0
    for sector, words in SECTOR_KEYWORDS.items():
        score = sum(1 for w in words if w in corpus)
        if score > best_score:
            best = sector
            best_score = score
    return best


def detect_role_track(job_fields: dict[str, Any]) -> str:
    corpus = _job_corpus(job_fields)
    title = str(job_fields.get("title", "")).lower()
    if "sap" in title:
        return "sap_consultant"
    if "data scientist" in title or re.search(r"\bml\b|\bmachine learning\b", title):
        return "data_scientist"
    if "data engineer" in title or "analytics engineer" in title:
        return "data_engineer"
    if "data analyst" in title or "business analyst" in title:
        return "data_analyst"
    best = "data_analyst"
    best_score = -1
    for role, words in ROLE_KEYWORDS.items():
        score = sum(1 for w in words if w in corpus)
        if role == "sap_consultant" and detect_sector(job_fields) == "sap":
            score += 2
        if score > best_score:
            best = role
            best_score = score
    return best


def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#./-]{3,}", text.lower())}


def _bullet_word_count(text: str) -> int:
    return len(re.findall(r"\b[\w%+/.-]+\b", str(text or "")))


def _bullet_quality_score(text: str) -> int:
    raw = str(text or "")
    low = raw.lower()
    score = 0
    if re.search(r"\b\d", raw):
        score += 2
    if any(token in low for token in ["reduced", "improved", "increased", "enabled", "automated", "designed", "built", "led", "developed", "refactored", "implemented", "engineered"]):
        score += 2
    if any(token in low for token in ["stakeholder", "cross-functional", "pipeline", "dashboard", "integration", "forecast", "model", "analytics", "data quality", "migration", "validation"]):
        score += 2
    if _bullet_word_count(raw) >= 18:
        score += 2
    return score


def _accept_rewritten_bullet(original_text: str, rewritten_text: str) -> bool:
    original = str(original_text or "").strip()
    rewritten = str(rewritten_text or "").strip()
    if not rewritten:
        return False
    if rewritten == original:
        return True
    original_words = _bullet_word_count(original)
    rewritten_words = _bullet_word_count(rewritten)
    if rewritten_words < max(14, int(original_words * 0.72)):
        return False
    if _bullet_quality_score(rewritten) < _bullet_quality_score(original):
        return False
    if re.search(r"\b(helped|worked on|responsible for|involved in)\b", rewritten.lower()) and not re.search(
        r"\b(helped|worked on|responsible for|involved in)\b", original.lower()
    ):
        return False
    if re.search(r"\b\d", original) and not re.search(r"\b\d", rewritten):
        return False
    return True


def rank_project_ids(
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    ats_keywords: list[str],
    sector: str,
) -> list[str]:
    projects = candidate_profile.get("academic_projects", [])
    if not isinstance(projects, list):
        return []
    jd_tokens = _token_set(_job_corpus(job_fields))
    keyword_tokens = _token_set(" ".join([str(x) for x in ats_keywords]))
    ranked: list[tuple[str, float]] = []
    boost_ids = set(SECTOR_PROJECT_BOOST.get(sector, []))
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        pid = str(proj.get("id", "")).strip()
        if not pid:
            continue
        blob = f"{proj.get('name', '')} {proj.get('description', '')}".lower()
        ptoks = _token_set(blob)
        overlap = len(ptoks.intersection(jd_tokens)) + len(ptoks.intersection(keyword_tokens))
        score = float(overlap)
        if pid in boost_ids:
            score += 25.0
        if sector == "sap" and "sap" in blob:
            score += 10.0
        if sector == "finance" and any(k in blob for k in ["finbert", "financial", "portfolio"]):
            score += 8.0
        if sector == "healthcare" and any(k in blob for k in ["health", "medical", "pneumonia", "rag"]):
            score += 8.0
        ranked.append((pid, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in ranked[:3]]


def rank_bullet_ids(
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    ats_keywords: list[str],
    role_track: str,
    sector: str,
) -> list[str]:
    jd_tokens = _token_set(_job_corpus(job_fields))
    role_tokens = _token_set(" ".join(ROLE_KEYWORDS.get(role_track, [])))
    sector_tokens = _token_set(" ".join(SECTOR_KEYWORDS.get(sector, [])))
    kw_tokens = _token_set(" ".join([str(k) for k in ats_keywords]))
    scored: list[tuple[str, float]] = []
    for exp in candidate_profile.get("experience", []):
        for bullet in exp.get("bullets", []):
            if not isinstance(bullet, dict):
                continue
            bid = str(bullet.get("id", "")).strip()
            if not bid:
                continue
            text = str(bullet.get("text", "")).lower()
            btoks = _token_set(text)
            score = 0.0
            score += 1.6 * len(btoks.intersection(jd_tokens))
            score += 1.2 * len(btoks.intersection(kw_tokens))
            score += 1.1 * len(btoks.intersection(role_tokens))
            score += 0.8 * len(btoks.intersection(sector_tokens))
            if role_track == "sap_consultant" and "sap" in text:
                score += 4.0
            if role_track == "data_engineer" and any(x in text for x in ["pipeline", "etl", "integration"]):
                score += 2.0
            if role_track == "data_analyst" and any(x in text for x in ["dashboard", "analytics", "insight"]):
                score += 2.0
            if role_track == "data_scientist" and any(x in text for x in ["model", "machine learning", "forecast"]):
                score += 2.0
            scored.append((bid, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    ranked_ids = [bid for bid, _ in scored]
    seen = set()
    deduped = []
    for bid in ranked_ids:
        if bid not in seen:
            seen.add(bid)
            deduped.append(bid)
    return deduped[:8]


def build_tailoring_plan(
    llm: LLMClient,
    job_fields: dict[str, Any],
    candidate_profile: dict[str, Any],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    required = [r.lower() for r in job_fields.get("requirements", [])]
    profile_skills = _profile_skill_set(candidate_profile)

    matched = 0
    total = max(1, len(required))
    reasons: list[str] = []
    for req in required[:12]:
        if any(skill in req for skill in profile_skills):
            matched += 1
            reasons.append(f"Matched requirement: {req[:100]}")

    fit_score = min(100, int((matched / total) * 100) + 25)
    gaps: list[str] = []
    if fit_score < 60:
        gaps.append("Fit is moderate; verify role expectations and highlight transferable projects.")

    experience = candidate_profile.get("experience", [])
    bullet_ids: list[str] = []
    for exp in experience:
        for bullet in exp.get("bullets", []):
            if isinstance(bullet, dict) and bullet.get("id"):
                bullet_ids.append(bullet["id"])

    plan = [
        "Re-order summary and skills to mirror top job requirements.",
        "Prioritize bullets that demonstrate direct tooling overlap.",
        "Keep claims factual and tied to existing profile entries.",
    ] + gaps

    role_track = detect_role_track(job_fields)
    sector_track = detect_sector(job_fields)
    suggested_bullets = rank_bullet_ids(candidate_profile, job_fields, [], role_track, sector_track)[:6]
    answers = _base_answers(candidate_profile, preferences)

    ats_keywords = extract_ats_keywords(job_fields)
    suggested_project_ids = rank_project_ids(candidate_profile, job_fields, ats_keywords, sector_track)

    if llm.enabled:
        try:
            payload = (
                "JOB_FIELDS:\n"
                f"{job_fields}\n\n"
                "CANDIDATE_PROFILE:\n"
                f"{candidate_profile}\n\n"
                "PREFERENCES:\n"
                f"{preferences}"
            )
            generated = llm.json_completion(TAILORING_PLAN_PROMPT, payload)
            fit_score = int(generated.get("fit_score", fit_score))
            reasons = list(generated.get("fit_reasons", reasons))
            plan = list(generated.get("tailoring_plan", plan))
            llm_bullets = [bid for bid in generated.get("suggested_bullet_ids", suggested_bullets) if bid in bullet_ids]
            ranked = rank_bullet_ids(candidate_profile, job_fields, ats_keywords, role_track, sector_track)
            chosen = [bid for bid in llm_bullets if bid in ranked]
            for bid in ranked:
                if bid not in chosen:
                    chosen.append(bid)
            suggested_bullets = chosen[:8]
            answers.update({k: str(v) for k, v in generated.get("common_answers", {}).items()})
            ats_keywords = list(generated.get("ats_keywords", ats_keywords))
        except Exception:
            pass

    if not suggested_bullets:
        suggested_bullets = rank_bullet_ids(candidate_profile, job_fields, ats_keywords, role_track, sector_track)
    if not suggested_project_ids:
        suggested_project_ids = rank_project_ids(candidate_profile, job_fields, ats_keywords, sector_track)

    if not reasons:
        reasons = ["Insufficient explicit overlap detected; review manually before applying."]

    coverage = keyword_coverage(candidate_profile, ats_keywords)

    return {
        "fit_score": fit_score,
        "fit_reasons": reasons[:8],
        "tailoring_plan": (plan + [f"Target role track: {role_track}", f"Detected sector: {sector_track}"])[:8],
        "suggested_bullets": suggested_bullets,
        "suggested_project_ids": suggested_project_ids[:3],
        "role_track": role_track,
        "sector_track": sector_track,
        "common_answers": answers,
        "ats_keywords": ats_keywords[:20],
        "matched_keywords": coverage["matched_keywords"],
        "missing_keywords": coverage["missing_keywords"],
        "keyword_coverage_pct": coverage["keyword_coverage_pct"],
    }


def extract_ats_keywords(job_fields: dict[str, Any]) -> list[str]:
    skills = [str(item).strip() for item in job_fields.get("skills", []) if str(item).strip()]
    requirement_text = " ".join(str(item) for item in job_fields.get("requirements", []))
    candidates = re.findall(r"\b[A-Za-z][A-Za-z0-9+\-/.#]{1,24}\b", requirement_text)
    normalized = []
    for token in skills + candidates:
        low = token.lower()
        if low in {"years", "year", "experience", "required", "preferred", "must", "have"}:
            continue
        if token not in normalized:
            normalized.append(token)
    return normalized[:35]


def rewrite_selected_bullets(
    llm: LLMClient,
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    selected_bullet_ids: list[str],
    role_track: str | None = None,
    priority_keywords: list[str] | None = None,
) -> dict[str, str]:
    original = {
        b.get("id"): b.get("text", "").strip()
        for exp in candidate_profile.get("experience", [])
        for b in exp.get("bullets", [])
        if isinstance(b, dict) and b.get("id")
    }
    selected = [bid for bid in selected_bullet_ids if bid in original]
    rewritten = {bid: original[bid] for bid in selected}
    if not selected or not llm.enabled:
        return rewritten

    payload = (
        "JOB_FIELDS:\n"
        f"{job_fields}\n\n"
        "ROLE_TRACK:\n"
        f"{role_track or detect_role_track(job_fields)}\n\n"
        "PRIORITY_KEYWORDS:\n"
        f"{priority_keywords or []}\n\n"
        "SELECTED_BULLET_IDS:\n"
        f"{selected}\n\n"
        "CANDIDATE_PROFILE:\n"
        f"{candidate_profile}"
    )
    try:
        response = llm.json_completion(CANDIDATE_BULLET_REWRITE_PROMPT, payload)
        for item in response.get("rewritten_bullets", []):
            bid = item.get("id")
            text = str(item.get("text", "")).strip()
            if bid in rewritten and _accept_rewritten_bullet(original.get(bid, ""), text):
                rewritten[bid] = text
    except Exception:
        return rewritten

    return rewritten


def rewrite_project_descriptions(
    llm: LLMClient,
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    priority_keywords: list[str] | None = None,
    selected_project_ids: list[str] | None = None,
) -> dict[str, str]:
    projects = candidate_profile.get("academic_projects", [])
    original = {
        p.get("id"): str(p.get("description", "")).strip()
        for p in projects
        if isinstance(p, dict) and p.get("id")
    }
    project_ids = [pid for pid in original.keys() if pid]
    if selected_project_ids:
        selected = [pid for pid in selected_project_ids if pid in original]
        if selected:
            project_ids = selected
    rewritten = dict(original)
    if not project_ids or not llm.enabled:
        return rewritten

    payload = (
        "JOB_FIELDS:\n"
        f"{job_fields}\n\n"
        "PRIORITY_KEYWORDS:\n"
        f"{priority_keywords or []}\n\n"
        "PROJECT_IDS:\n"
        f"{project_ids}\n\n"
        "CANDIDATE_PROFILE:\n"
        f"{candidate_profile}"
    )
    try:
        response = llm.json_completion(PROJECT_REWRITE_PROMPT, payload)
        for item in response.get("rewritten_projects", []):
            pid = item.get("id")
            desc = str(item.get("description", "")).strip()
            if pid in rewritten and desc:
                rewritten[pid] = desc
    except Exception:
        return rewritten
    return rewritten


def keyword_coverage(candidate_profile: dict[str, Any], ats_keywords: list[str]) -> dict[str, Any]:
    corpus_parts: list[str] = []
    corpus_parts.extend([str(s) for s in candidate_profile.get("skills", [])])
    for exp in candidate_profile.get("experience", []):
        corpus_parts.extend([str(b.get("text", "")) for b in exp.get("bullets", []) if isinstance(b, dict)])
    for proj in candidate_profile.get("academic_projects", []):
        corpus_parts.append(str(proj.get("name", "")))
        corpus_parts.append(str(proj.get("description", "")))
    for group in candidate_profile.get("technical_skills", []):
        if isinstance(group, dict):
            corpus_parts.extend([str(x) for x in group.get("items", [])])

    corpus = " ".join(corpus_parts).lower()
    matched: list[str] = []
    missing: list[str] = []
    for kw in ats_keywords:
        k = str(kw).strip()
        if not k:
            continue
        if k.lower() in corpus:
            matched.append(k)
        else:
            missing.append(k)
    total = len(matched) + len(missing)
    pct = int(round((len(matched) / total) * 100)) if total else 0
    return {
        "matched_keywords": matched[:15],
        "missing_keywords": missing[:15],
        "keyword_coverage_pct": pct,
    }


def keyword_coverage_for_text(ats_keywords: list[str], text: str) -> dict[str, Any]:
    corpus = str(text or "").lower()
    matched: list[str] = []
    missing: list[str] = []
    for kw in ats_keywords:
        k = str(kw).strip()
        if not k:
            continue
        if k.lower() in corpus:
            matched.append(k)
        else:
            missing.append(k)
    total = len(matched) + len(missing)
    pct = int(round((len(matched) / total) * 100)) if total else 0
    return {
        "matched_keywords": matched[:20],
        "missing_keywords": missing[:20],
        "keyword_coverage_pct": pct,
    }


def build_diff_summary(base_bullet_ids: list[str], selected_bullet_ids: list[str]) -> list[str]:
    selected_set = set(selected_bullet_ids)
    unchanged = [bid for bid in base_bullet_ids if bid in selected_set]
    omitted = [bid for bid in base_bullet_ids if bid not in selected_set]
    summary = [
        f"Selected {len(selected_bullet_ids)} bullets for targeted relevance.",
        f"Kept {len(unchanged)} base bullets unchanged.",
    ]
    if omitted:
        summary.append(f"De-prioritized bullet IDs: {', '.join(omitted[:8])}")
    return summary
