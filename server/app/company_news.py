from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import json
import xml.etree.ElementTree as ET

from .llm import COMPANY_ISSUE_PROMPT, LLMClient


def fetch_company_news(company: str, days: int = 30, limit: int = 8) -> list[dict[str, str]]:
    company = (company or "").strip()
    if not company:
        return []
    query = quote_plus(f'"{company}" when:{max(1, days)}d')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    req = Request(url, headers={"User-Agent": "JobApplyCopilot/1.0"})
    with urlopen(req, timeout=8) as resp:
        xml_bytes = resp.read()
    root = ET.fromstring(xml_bytes)
    items = root.findall(".//item")
    out: list[dict[str, str]] = []
    for item in items[: max(1, limit)]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()
        published_iso = ""
        if pub_date:
            try:
                published_iso = parsedate_to_datetime(pub_date).isoformat()
            except Exception:
                published_iso = pub_date
        if title and link:
            out.append(
                {
                    "title": title,
                    "url": link,
                    "published_at": published_iso,
                    "source": source,
                }
            )
    return out


def _fallback_issue(company: str, job_title: str, articles: list[dict[str, str]]) -> dict[str, Any]:
    if not articles:
        return {}
    top = articles[0]
    issue_title = top.get("title", "")[:140]
    summary = (
        f"Recent public coverage around {company} suggests a near-term priority area. "
        f"Based on the top headline, this role can support data-driven execution and reporting on that priority."
    )
    linkedin_note = (
        f"I noticed recent coverage about {company}'s current priorities, especially: '{issue_title}'. "
        "I work on analytics automation and dashboarding, and I’d love to share how I’d support faster reporting and decision-making."
    )
    return {
        "issue_title": issue_title,
        "issue_summary": summary,
        "why_it_matters": "The issue likely affects execution speed, visibility, or stakeholder alignment.",
        "how_candidate_can_help": (
            f"As a {job_title or 'candidate'}, I can help by improving data quality, building reliable reporting workflows, "
            "and translating metrics into actionable decisions."
        ),
        "linkedin_outreach_note": linkedin_note,
        "sources": articles[:4],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def build_company_issue_brief(
    llm: LLMClient,
    company: str,
    job_title: str,
    job_text: str,
) -> dict[str, Any]:
    try:
        articles = fetch_company_news(company=company, days=30, limit=10)
    except Exception:
        articles = []
    if not articles:
        return {}

    if llm.enabled:
        payload = json.dumps(
            {
                "company": company,
                "job_title": job_title,
                "job_text_excerpt": (job_text or "")[:6000],
                "articles": articles,
            },
            ensure_ascii=False,
        )
        try:
            result = llm.json_completion(COMPANY_ISSUE_PROMPT, payload)
            sources = result.get("sources") or []
            clean_sources: list[dict[str, str]] = []
            for s in sources:
                if not isinstance(s, dict):
                    continue
                title = str(s.get("title", "")).strip()
                url = str(s.get("url", "")).strip()
                published_at = str(s.get("published_at", "")).strip()
                if title and url:
                    clean_sources.append({"title": title, "url": url, "published_at": published_at})
            if clean_sources:
                return {
                    "issue_title": str(result.get("issue_title", "")).strip(),
                    "issue_summary": str(result.get("issue_summary", "")).strip(),
                    "why_it_matters": str(result.get("why_it_matters", "")).strip(),
                    "how_candidate_can_help": str(result.get("how_candidate_can_help", "")).strip(),
                    "linkedin_outreach_note": str(result.get("linkedin_outreach_note", "")).strip(),
                    "sources": clean_sources[:5],
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                }
        except Exception:
            pass

    return _fallback_issue(company=company, job_title=job_title, articles=articles)
