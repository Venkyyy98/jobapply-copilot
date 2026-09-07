from __future__ import annotations

import re
from typing import Any

from .llm import EXTRACT_JOB_FIELDS_PROMPT, LLMClient

COMMON_SPLIT_HEADERS = ["requirements", "qualifications", "responsibilities", "what you'll do", "about the role"]
ROLE_WORDS = r"analyst|engineer|scientist|consultant|specialist|manager|intern|developer|co-?op|trainee|apprentice"
US_STATE_PATTERN = (
    r"AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|WY|"
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming"
)
TITLE_NOISE_PATTERNS = [
    r"^view more jobs$",
    r"^similar jobs$",
    r"^see more jobs$",
    r"^apply now$",
    r"^job info$",
    r"^more information$",
    r"^about us$",
    r"^legend$",
    r"^copy to clipboard$",
]
NON_JOB_NOISE = [
    "skip to main content",
    "we use cookies",
    "cookie preferences",
    "privacy choices",
    "accept all cookies",
    "lifeattiktokdiversity",
    "people also viewed",
    "view more jobs",
    "connect with",
    "followers",
]
JOB_SIGNALS = [
    "responsibilities",
    "qualifications",
    "requirements",
    "about the role",
    "what you'll do",
    "job description",
    "experience",
    "preferred qualifications",
    "minimum qualifications",
]


def validate_job_content(job_text: str, page_title: str = "", company_hint: str = "") -> str | None:
    text = str(job_text or "").strip()
    low = text.lower()
    if len(text) < 120:
        return "Could not extract enough job description text. Paste the job description and analyze again."
    signal_count = sum(1 for signal in JOB_SIGNALS if signal in low)
    noise_count = sum(1 for noise in NON_JOB_NOISE if noise in low)
    title_context = f"{page_title} {company_hint}".lower()
    linkedin_profile_like = "linkedin.com/in/" in low or re.search(r"\b\d+(st|nd|rd|th)\s+degree\b", low)
    job_search_like = "view more jobs" in low and signal_count == 0
    title_has_role = bool(re.search(rf"\b({ROLE_WORDS})\b", title_context))
    if linkedin_profile_like:
        return "This looks like a LinkedIn profile, not a job posting. Open the actual job post and analyze again."
    if job_search_like:
        return "This looks like a job search/listing page, not a single job description. Open one job detail page and analyze again."
    if noise_count >= 2 and signal_count == 0:
        return "The page text looks like navigation or cookie content, not a job description. Paste the full job description and retry."
    if not title_has_role and signal_count == 0 and not re.search(r"\b(apply|position|role|hiring|qualification|responsibilit)\b", low):
        return "Could not identify a job posting from this page. Enter the job title/company and paste the full job description."
    return None


def _find_lines(text: str) -> list[str]:
    return [line.strip(" -\t") for line in text.splitlines() if line.strip()]


def _looks_like_noise_title(value: str) -> bool:
    raw = str(value or "").strip()
    low = raw.lower()
    if not raw:
        return True
    return any(re.search(pattern, low) for pattern in TITLE_NOISE_PATTERNS)


def _clean_title(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" -|")
    cleaned = re.sub(r"^(?:job\s+)?application\s+for\s+", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+at\s+[A-Z][A-Za-z0-9&.,'()\- ]{1,80}$", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+-\s+(careers?|jobs?|job openings?|apply).*?$", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+job\s+in\s+.+$", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(
        rf"\s+(?:-|–|—)\s+[A-Z][A-Za-z .'-]+,\s*(?:{US_STATE_PATTERN})$",
        "",
        cleaned,
    ).strip()
    cleaned = re.sub(r"\s+in\s+[A-Z][A-Za-z .'-]+,\s*(?:\d{5}|[A-Z]{2})(?:\b.*)?$", "", cleaned).strip()
    cleaned = re.sub(r"\s+in\s+[A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+\(?\b(?:remote|hybrid|onsite|on-site)\b\)?$", "", cleaned, flags=re.I).strip()
    return cleaned[:120]


def _clean_company(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" -|")
    cleaned = re.sub(r"\s+(careers?|jobs?|job openings?|apply)$", "", cleaned, flags=re.I).strip()
    if cleaned.lower() in {"detected or edit manually", "unknown", "unknown company", "company"}:
        return ""
    return cleaned[:120]


def _clean_location(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" -|")
    cleaned = re.sub(r"\s*\((hybrid|remote|on-?site)\)\s*", "", cleaned, flags=re.I).strip(" ,")
    cleaned = re.sub(r"^(location|locations)\s*:?\s*", "", cleaned, flags=re.I).strip()
    return cleaned[:120]


def _looks_like_specific_location(value: str) -> bool:
    cleaned = _clean_location(value)
    if not cleaned:
        return False
    low = cleaned.lower()
    if low in {"united states", "usa", "us", "remote", "hybrid", "on-site", "onsite"}:
        return False
    return bool(
        re.search(rf"\b[A-Z][A-Za-z.' -]+,\s*(?:{US_STATE_PATTERN})\b", cleaned)
        or re.search(r"\b(mumbai|pune|bangalore|bengaluru|hyderabad|chennai|gurgaon|gurugram|noida|delhi),?\s+india\b", low)
    )


def _heuristic_location(lines: list[str]) -> str:
    location_patterns = [
        rf"\b([A-Z][A-Za-z.' -]+,\s*(?:{US_STATE_PATTERN}))\b",
        r"\b(Mumbai|Pune|Bangalore|Bengaluru|Hyderabad|Chennai|Gurgaon|Gurugram|Noida|Delhi),?\s+India\b",
    ]

    for i, line in enumerate(lines[:80]):
        raw_low = re.sub(r"\s+", " ", str(line or "").strip()).lower()
        cleaned = _clean_location(line)
        low = cleaned.lower()
        if raw_low in {"location", "locations"} and i + 1 < len(lines):
            next_line = _clean_location(lines[i + 1])
            if _looks_like_specific_location(next_line):
                return next_line
        if raw_low.startswith(("location:", "locations:")) and _looks_like_specific_location(cleaned):
            return cleaned
        for pattern in location_patterns:
            match = re.search(pattern, cleaned)
            if match:
                return _clean_location(match.group(1))
    return ""


def _title_from_page_title(page_title: str) -> str:
    raw = str(page_title or "").strip()
    if not raw:
        return ""
    for sep in ["|", " - ", " – ", " — "]:
        if sep in raw:
            first = _clean_title(raw.split(sep)[0])
            if first and not _looks_like_noise_title(first):
                return first
    cleaned = _clean_title(raw)
    return "" if _looks_like_noise_title(cleaned) else cleaned


def _heuristic_title(page_title: str, lines: list[str]) -> str:
    from_page_title = _title_from_page_title(page_title)
    if from_page_title and re.search(rf"\b({ROLE_WORDS})\b", from_page_title, flags=re.I):
        return from_page_title
    for line in lines[:20]:
        cleaned = _clean_title(line)
        if _looks_like_noise_title(cleaned):
            continue
        if re.search(rf"\b({ROLE_WORDS})\b", cleaned, flags=re.I):
            return cleaned
    if from_page_title:
        return from_page_title
    for line in lines[:10]:
        cleaned = _clean_title(line)
        if cleaned and not _looks_like_noise_title(cleaned):
            return cleaned
    return "Unknown Role"


def _heuristic_company(page_title: str, company_hint: str) -> str:
    hint = _clean_company(company_hint)
    if hint:
        return hint
    raw = str(page_title or "").strip()
    if raw:
        for sep in ["|", " - ", " – ", " — "]:
            if sep in raw:
                parts = [_clean_company(p) for p in raw.split(sep) if _clean_company(p)]
                if len(parts) > 1:
                    return parts[-1]
        match = re.search(r"\b([A-Z][A-Za-z0-9&.,' ]+)\s+Careers?\b", raw)
        if match:
            company = _clean_company(match.group(1))
            if company:
                return company
    return "Unknown Company"


def parse_job_fields(
    llm: LLMClient,
    job_text: str,
    page_title: str,
    company_hint: str,
    url: str,
    title_hint: str = "",
) -> dict[str, Any]:
    lines = _find_lines(job_text)
    explicit_title = _clean_title(title_hint)
    explicit_company = _clean_company(company_hint)
    heuristic = {
        "title": explicit_title or _heuristic_title(page_title, lines),
        "company": explicit_company or _heuristic_company(page_title, company_hint),
        "location": _heuristic_location(lines),
        "requirements": [],
        "responsibilities": [],
        "skills": [],
        "summary": " ".join(lines[:5])[:500],
        "job_text": job_text,
        "description": job_text,
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
        payload = (
            f"URL: {url}\nPAGE_TITLE: {page_title}\n"
            f"USER_CONFIRMED_TITLE: {explicit_title}\n"
            f"USER_CONFIRMED_COMPANY: {explicit_company}\nJOB:\n{job_text[:15000]}"
        )
        try:
            extracted = llm.json_completion(EXTRACT_JOB_FIELDS_PROMPT, payload)
            for key in ["title", "company", "location", "requirements", "responsibilities", "skills", "summary"]:
                if key not in extracted or not extracted[key]:
                    continue
                if key == "title" and _looks_like_noise_title(str(extracted[key])):
                    continue
                if key == "company" and not _clean_company(str(extracted[key])):
                    continue
                if key == "title" and explicit_title:
                    continue
                if key == "company" and explicit_company:
                    continue
                if key == "location" and not _looks_like_specific_location(str(extracted[key])):
                    continue
                if key == "title":
                    heuristic[key] = _clean_title(str(extracted[key]))
                elif key == "company":
                    heuristic[key] = _clean_company(str(extracted[key]))
                else:
                    heuristic[key] = extracted[key]
        except Exception:
            pass

    return heuristic
