from __future__ import annotations

import re
from typing import Any


def profile_claim_index(candidate_profile: dict[str, Any]) -> dict[str, set[str]]:
    companies = {str(e.get("company", "")).strip().lower() for e in candidate_profile.get("experience", []) if e.get("company")}
    roles = {str(e.get("role", "")).strip().lower() for e in candidate_profile.get("experience", []) if e.get("role")}
    degrees = {str(e.get("degree", "")).strip().lower() for e in candidate_profile.get("education", []) if e.get("degree")}
    certs = {str(c).strip().lower() for c in candidate_profile.get("certifications", []) if c}
    return {
        "companies": companies,
        "roles": roles,
        "degrees": degrees,
        "certs": certs,
    }


def _find_capitalized_phrases(text: str) -> set[str]:
    phrases = set(re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2}\b", text))
    return {p.strip().lower() for p in phrases if len(p) > 2}


def check_for_unsupported_claims(candidate_profile: dict[str, Any], generated_texts: list[str]) -> list[str]:
    issues: list[str] = []
    idx = profile_claim_index(candidate_profile)
    known = idx["companies"] | idx["roles"] | idx["degrees"] | idx["certs"]

    for text in generated_texts:
        mentions = _find_capitalized_phrases(text)
        for mention in mentions:
            if mention in {"dear hiring manager", "sincerely", "linkedin", "github"}:
                continue
            if any(mention in group for group in [idx["companies"], idx["roles"], idx["degrees"], idx["certs"]]):
                continue
            if mention in known:
                continue
            if re.search(r"\b\d{1,3}%\b", mention):
                issues.append("Detected percentage claim not traceable to profile facts.")

    return sorted(set(issues))


def check_profile_completeness(candidate_profile: dict[str, Any]) -> list[str]:
    missing = []
    required_paths = [
        ("identity.full_name", candidate_profile.get("identity", {}).get("full_name")),
        ("identity.email", candidate_profile.get("identity", {}).get("email")),
        ("experience", candidate_profile.get("experience", [])),
        ("education", candidate_profile.get("education", [])),
    ]
    for key, value in required_paths:
        if not value:
            missing.append(f"Missing required profile field: {key}")
    return missing
