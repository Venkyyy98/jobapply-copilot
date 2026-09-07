from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
HUNTER_ENDPOINT = "https://api.hunter.io/v2"


@dataclass
class Target:
    name: str = ""
    title: str = ""
    linkedin_url: str = ""
    email: str = ""
    source: str = ""
    score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    relationship_type: str = "beyond_network"
    shared_context: str = ""


def _http_get_json(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "JobApplyCopilot/1.0"})
    with urlopen(req, timeout=timeout) as res:  # nosec - user-provided urls not used
        raw = res.read().decode("utf-8", errors="ignore")
    data = json.loads(raw or "{}")
    return data if isinstance(data, dict) else {}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _tokenize(text: str) -> list[str]:
    return [x for x in re.sub(r"[^a-z0-9\s]", " ", text.lower()).split() if len(x) > 2]


def _name_from_title(raw_title: str) -> tuple[str, str]:
    title = _normalize(raw_title)
    if " - " in title:
        left, right = title.split(" - ", 1)
        return left.strip(), right.strip()
    if " | " in title:
        left, right = title.split(" | ", 1)
        return left.strip(), right.strip()
    parts = title.split(",")
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    return title[:80], ""


def _score_contact(candidate: Target, role: str) -> float:
    score = 0.0
    title = (candidate.title or "").lower()
    name = (candidate.name or "").lower()
    text = f"{candidate.title} {' '.join(candidate.evidence)}".lower()
    role_tokens = set(_tokenize(role))

    if any(k in title for k in ["recruit", "talent", "sourcer", "people partner", "hr"]):
        score += 45
    if any(k in title for k in ["hiring manager", "manager", "director", "head", "lead", "principal"]):
        score += 30
    if any(k in title for k in ["data", "analytics", "bi", "sap", "engineer", "scientist"]):
        score += 18
    if name and len(name.split()) >= 2:
        score += 3

    role_overlap = 0
    if role_tokens:
        candidate_tokens = set(_tokenize(f"{candidate.title} {' '.join(candidate.evidence)}"))
        role_overlap = len(role_tokens.intersection(candidate_tokens))
        score += min(20, role_overlap * 3)

    if candidate.relationship_type == "previous_company":
        score += 20
    elif candidate.relationship_type == "school":
        score += 18

    return round(score, 2)


def _organization_aliases(name: str) -> list[str]:
    display = _normalize(name)
    lower = display.lower()
    aliases = {lower}
    if "ltimindtree" in lower or "larsen" in lower or re.search(r"\blti\b", lower):
        aliases.update(
            {
                "ltimindtree",
                "lti mindtree",
                "larsen & toubro infotech",
                "larsen and toubro infotech",
                "l&t infotech",
                "lti",
            }
        )
    if "stevens institute" in lower:
        aliases.add("stevens institute")
    return sorted((alias for alias in aliases if len(alias) >= 3), key=len, reverse=True)


def _background_organizations(candidate_profile: dict[str, Any] | None) -> tuple[list[tuple[str, list[str]]], list[tuple[str, list[str]]]]:
    profile = candidate_profile or {}
    companies: list[tuple[str, list[str]]] = []
    schools: list[tuple[str, list[str]]] = []
    seen_companies: set[str] = set()
    seen_schools: set[str] = set()

    for item in profile.get("experience", []) or []:
        company = _normalize(str(item.get("company", ""))) if isinstance(item, dict) else ""
        key = re.sub(r"[^a-z0-9]", "", company.lower())
        if company and key not in seen_companies:
            seen_companies.add(key)
            companies.append((company, _organization_aliases(company)))

    for item in profile.get("education", []) or []:
        school = _normalize(str(item.get("school", ""))) if isinstance(item, dict) else ""
        key = re.sub(r"[^a-z0-9]", "", school.lower())
        if school and key not in seen_schools:
            seen_schools.add(key)
            schools.append((school, _organization_aliases(school)))

    # A university can also appear as an employer for an RA role. Treat that
    # overlap as an alumni connection, which is the more useful outreach label.
    companies = [
        (display, aliases)
        for display, aliases in companies
        if re.sub(r"[^a-z0-9]", "", display.lower()) not in seen_schools
    ]
    return companies, schools


def _contains_alias(text: str, alias: str) -> bool:
    if alias == "lti":
        return bool(re.search(r"\blti\b", text))
    return alias in text


def classify_shared_background(target: Target, candidate_profile: dict[str, Any] | None) -> Target:
    text = _normalize(f"{target.title} {' '.join(target.evidence)}").lower()
    companies, schools = _background_organizations(candidate_profile)
    for display, aliases in companies:
        if any(_contains_alias(text, alias) for alias in aliases):
            target.relationship_type = "previous_company"
            target.shared_context = display
            return target
    for display, aliases in schools:
        if any(_contains_alias(text, alias) for alias in aliases):
            target.relationship_type = "school"
            target.shared_context = display
            return target
    target.relationship_type = "beyond_network"
    target.shared_context = ""
    return target


def _quoted_background_query(items: list[tuple[str, list[str]]], limit: int = 5) -> str:
    terms: list[str] = []
    for display, aliases in items:
        preferred = next((alias for alias in aliases if alias != "lti"), display)
        if preferred and preferred not in terms:
            terms.append(preferred)
        if len(terms) >= limit:
            break
    return " OR ".join(f'"{term}"' for term in terms)


def _serp_search(api_key: str, q: str, num: int = 10) -> list[dict[str, Any]]:
    params = {
        "q": q,
        "engine": "google",
        "num": str(num),
        "api_key": api_key,
    }
    url = f"{SERPAPI_ENDPOINT}?{urlencode(params)}"
    data = _http_get_json(url)
    organic = data.get("organic_results", [])
    return organic if isinstance(organic, list) else []


def _extract_domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _discover_company_domain(serpapi_key: str, company: str) -> str:
    results = _serp_search(serpapi_key, f"{company} official website", num=5)
    for item in results:
        link = str(item.get("link", "")).strip()
        if not link:
            continue
        host = _extract_domain_from_url(link)
        if not host:
            continue
        if "linkedin.com" in host or "wikipedia.org" in host:
            continue
        return host
    return ""


def _email_from_hunter(hunter_api_key: str, domain: str, full_name: str) -> str:
    if not hunter_api_key or not domain or not full_name:
        return ""
    name_parts = [p for p in re.split(r"\s+", full_name.strip()) if p]
    if len(name_parts) < 2:
        return ""
    params = {
        "domain": domain,
        "first_name": name_parts[0],
        "last_name": name_parts[-1],
        "api_key": hunter_api_key,
    }
    url = f"{HUNTER_ENDPOINT}/email-finder?{urlencode(params)}"
    try:
        data = _http_get_json(url)
    except Exception:
        return ""
    payload = data.get("data", {})
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("email", "")).strip()


def find_target_contacts(
    *,
    serpapi_key: str,
    hunter_api_key: str,
    company: str,
    role: str,
    job_url: str,
    candidate_profile: dict[str, Any] | None = None,
    limit: int = 10,
) -> tuple[list[Target], list[str]]:
    warnings: list[str] = []
    if not serpapi_key:
        return [], ["SERPAPI_KEY is missing on server. Add it in .env and restart server."]

    companies, schools = _background_organizations(candidate_profile)
    queries = [
        f'site:linkedin.com/in "{company}" recruiter',
        f'site:linkedin.com/in "{company}" "hiring manager" "{role}"',
        f'site:linkedin.com/in "{company}" ("data lead" OR "data manager" OR "team lead")',
    ]
    company_terms = _quoted_background_query(companies)
    school_terms = _quoted_background_query(schools)
    if company_terms:
        queries.append(f'site:linkedin.com/in "{company}" ({company_terms})')
    if school_terms:
        queries.append(f'site:linkedin.com/in "{company}" ({school_terms})')

    by_url: dict[str, Target] = {}
    for q in queries:
        items = _serp_search(serpapi_key, q, num=10)
        for item in items:
            link = str(item.get("link", "")).strip()
            if "/in/" not in link or "linkedin.com" not in link:
                continue
            title_raw = str(item.get("title", "")).strip()
            snippet = _normalize(str(item.get("snippet", "")))
            name, parsed_title = _name_from_title(title_raw)
            key = link.split("?")[0].lower()
            existing = by_url.get(key)
            if existing is None:
                by_url[key] = Target(
                    name=name,
                    title=parsed_title,
                    linkedin_url=link,
                    source="serpapi",
                    evidence=[snippet] if snippet else [],
                )
            else:
                if snippet:
                    existing.evidence.append(snippet)
                if (not existing.title) and parsed_title:
                    existing.title = parsed_title

    contacts = list(by_url.values())
    if not contacts:
        return [], ["No LinkedIn targets found from public search. Try company name/job title variations."]

    for c in contacts:
        classify_shared_background(c, candidate_profile)
        c.score = _score_contact(c, role)

    contacts.sort(key=lambda x: x.score, reverse=True)
    contacts = contacts[: max(1, limit)]

    domain = _extract_domain_from_url(job_url)
    if "workday" in domain or "greenhouse" in domain or "lever" in domain or not domain:
        discovered = _discover_company_domain(serpapi_key, company)
        if discovered:
            domain = discovered
    if not domain:
        warnings.append("Could not confidently determine company domain for email enrichment.")

    if hunter_api_key and domain:
        for c in contacts:
            c.email = _email_from_hunter(hunter_api_key, domain, c.name)
    elif not hunter_api_key:
        warnings.append("HUNTER_API_KEY missing. Returning contacts without email enrichment.")

    return contacts, warnings
