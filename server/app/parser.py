from __future__ import annotations

import re
from typing import Any

from .llm import EXTRACT_JOB_FIELDS_PROMPT, LLMClient

COMMON_SPLIT_HEADERS = ["requirements", "qualifications", "responsibilities", "what you'll do", "about the role"]


def _find_lines(text: str) -> list[str]:
    return [line.strip(" -\t") for line in text.splitlines() if line.strip()]


def _heuristic_title(page_title: str, lines: list[str]) -> str:
    if page_title and "|" in page_title:
        return page_title.split("|")[0].strip()
    if lines:
        return lines[0][:120]
    return "Unknown Role"


def _heuristic_company(page_title: str, company_hint: str) -> str:
    if company_hint.strip():
        return company_hint.strip()
    if page_title and "|" in page_title:
        parts = [p.strip() for p in page_title.split("|") if p.strip()]
        if len(parts) > 1:
            return parts[1]
    return "Unknown Company"


def parse_job_fields(
    llm: LLMClient,
    job_text: str,
    page_title: str,
    company_hint: str,
    url: str,
) -> dict[str, Any]:
    lines = _find_lines(job_text)
    heuristic = {
        "title": _heuristic_title(page_title, lines),
        "company": _heuristic_company(page_title, company_hint),
        "location": "",
        "requirements": [],
        "responsibilities": [],
        "skills": [],
        "summary": " ".join(lines[:5])[:500],
    }

    for line in lines:
        low = line.lower()
        if any(head in low for head in COMMON_SPLIT_HEADERS):
            continue
        if re.search(r"\b(years?|experience|bachelor|master|phd|python|sql|aws|react|java)\b", low):
            heuristic["requirements"].append(line)
        if re.search(r"\bbuild|design|collaborate|lead|develop|implement|maintain\b", low):
            heuristic["responsibilities"].append(line)

    skills = set()
    for candidate in heuristic["requirements"] + heuristic["responsibilities"]:
        for token in ["python", "sql", "aws", "gcp", "azure", "react", "node", "java", "docker", "kubernetes"]:
            if token in candidate.lower():
                skills.add(token.upper() if len(token) <= 3 else token.title())
    heuristic["skills"] = sorted(skills)

    if llm.enabled:
        payload = f"URL: {url}\nTITLE: {page_title}\nCOMPANY_HINT: {company_hint}\nJOB:\n{job_text[:15000]}"
        try:
            extracted = llm.json_completion(EXTRACT_JOB_FIELDS_PROMPT, payload)
            for key in ["title", "company", "location", "requirements", "responsibilities", "skills", "summary"]:
                if key in extracted and extracted[key]:
                    heuristic[key] = extracted[key]
        except Exception:
            pass

    return heuristic
