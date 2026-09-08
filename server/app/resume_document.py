"""Canonical, renderer-independent resume blocks and validated inline emphasis.

The plain-text adapter preserves the existing API/storage contract. Both exporters
consume these same blocks, so layout never depends on model-generated HTML.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re
from urllib.parse import urlsplit
from typing import Literal


@dataclass(frozen=True)
class Segment:
    text: str
    bold: bool = False
    url: str = ""

    def __post_init__(self):
        if self.url and urlsplit(self.url).scheme not in {"https", "http", "mailto"}:
            raise ValueError("Unsupported resume hyperlink scheme")


@dataclass(frozen=True)
class Block:
    kind: Literal["name", "contact", "heading", "entry", "education", "education_detail", "bullet", "body"]
    segments: tuple[Segment, ...]
    right: str = ""


@dataclass(frozen=True)
class ResumeDocument:
    blocks: tuple[Block, ...]


HEADINGS = {
    "SUMMARY", "PROFESSIONAL SUMMARY", "TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE",
    "PROJECTS", "ACADEMIC PROJECTS", "AI/ML PROJECTS", "EDUCATION",
    "CERTIFICATIONS", "CERTIFICATIONS & AWARDS",
}
DATE = re.compile(r"\b(?:19|20)\d{2}\b|\bPresent\b", re.I)
TECH = re.compile(
    r"\b(?:multi-agent [\w-]+ workflows|ETL pipelines|data pipelines|semantic search|"
    r"anomaly detection|machine learning|feature engineering|LLM evaluation|"
    r"RAG|LangGraph|LangChain|Python|SQL|Java|MySQL|Spark|Kafka|FastAPI|"
    r"TensorFlow|PyTorch|FAISS|AWS|SAP CPI|CI/CD|REST APIs|FinBERT|PySpark|CNN-MobileNet)\b", re.I
)
METRIC = re.compile(r"(?<!\w)(?:~)?\d+(?:\.\d+)?(?:%|\+)(?:\s+(?:integration workflows|adversarial test cases))?|\b(?:F1-score|accuracy) of \d+\.\d+", re.I)


def bullet_segments(raw: str) -> tuple[Segment, ...]:
    # Accept paired legacy Markdown, then validate emphasis against the clean text.
    clean = re.sub(r"^(?:[-*•]\s*)+", "", raw.strip()).replace("**", "")
    candidates: list[tuple[int, int]] = []
    for match in re.finditer(r"\*\*(.+?)\*\*", raw):
        phrase = match.group(1)
        start = clean.find(phrase)
        if start >= 0 and len(phrase.split()) <= 6 and len(phrase) < len(clean) * .65:
            candidates.append((start, start + len(phrase)))
    for pattern in (METRIC, TECH):
        candidates.extend((m.start(), m.end()) for m in pattern.finditer(clean))
    if not candidates:
        words = list(re.finditer(r"\S+", clean))
        if len(words) >= 5:
            candidates.append((words[0].start(), words[min(2, len(words) - 1)].end()))
    spans: list[tuple[int, int]] = []
    for start, end in candidates:
        if len(spans) == 2:
            break
        if end - start > len(clean) * .65 or any(start < b and end > a for a, b in spans):
            continue
        spans.append((start, end))
    result: list[Segment] = []
    cursor = 0
    for start, end in sorted(spans):
        if cursor < start:
            result.append(Segment(clean[cursor:start]))
        result.append(Segment(clean[start:end], True))
        cursor = end
    if cursor < len(clean):
        result.append(Segment(clean[cursor:]))
    return tuple(result)


def html_segments(segments: tuple[Segment, ...]) -> str:
    output = []
    for segment in segments:
        value = escape(segment.text, quote=True)
        if segment.bold:
            value = f"<b>{value}</b>"
        if segment.url:
            value = f'<link href="{escape(segment.url, quote=True)}" color="#000000"><u>{value}</u></link>'
        output.append(value)
    return "".join(output)


def parse_resume(text: str) -> ResumeDocument:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blocks: list[Block] = []
    section = ""
    for index, raw in enumerate(lines):
        line = raw.replace("**", "")
        if index == 0:
            blocks.append(Block("name", (Segment(line, True),)))
        elif index == 1:
            segments = []
            for part in (p.strip() for p in line.split("|")):
                if not part:
                    continue
                if segments:
                    segments.append(Segment(" | "))
                match = re.match(r"(?:LinkedIn|GitHub|Portfolio):\s*(https?://\S+)$", part, re.I)
                if match:
                    url = match.group(1)
                    segments.append(Segment(re.sub(r"^https?://(?:www\.)?", "", url).rstrip("/"), url=url))
                else:
                    part = re.sub(r"(?<!\d)(\d{3})(\d{3})(\d{4})(?!\d)", r"(\1) \2-\3", part)
                    segments.append(Segment(part))
            blocks.append(Block("contact", tuple(segments)))
        elif line.upper() in HEADINGS:
            section = line.upper()
            blocks.append(Block("heading", (Segment(section, True),)))
        elif raw.startswith(("- ", "* ", "• ")):
            content = re.sub(r"^(?:[-*•]\s*)+", "", raw.strip())
            segments = bullet_segments(content)
            if section.startswith("CERTIFICATIONS"):
                label, sep, rest = content.partition(" | ")
                segments = (Segment(label, True), Segment(sep + rest))
            blocks.append(Block("bullet", segments))
        elif section == "TECHNICAL SKILLS":
            label, sep, rest = line.partition(":")
            blocks.append(Block("body", (Segment(label + sep, True), Segment(rest))))
        elif section == "PROFESSIONAL EXPERIENCE":
            parts = [p.strip() for p in line.split("|")]
            right = parts.pop() if len(parts) > 1 and DATE.search(parts[-1]) else ""
            segments = []
            for i, part in enumerate(parts):
                if not part:
                    continue
                if segments:
                    segments.append(Segment(" | "))
                segments.append(Segment(part, i < 2))
            blocks.append(Block("entry", tuple(segments), right))
        elif "PROJECTS" in section:
            match = re.search(r"\s*(?:\|\s*|\()(?:GitHub|Git):\s*(https?://[^\s)]+)\)?$", line, re.I)
            segments = (Segment(line[:match.start()].strip() if match else line, True),)
            if match:
                segments += (Segment(" | "), Segment("GitHub", True, match.group(1)))
            blocks.append(Block("entry", segments))
        elif section == "EDUCATION":
            parts = [p.strip() for p in line.split("|")]
            right = ""
            if len(parts) > 1 and DATE.search(parts[-1]) and not parts[-1].startswith("GPA"):
                right = parts.pop()
            elif len(parts) > 1 and blocks and blocks[-1].kind == "education" and not parts[-1].startswith("GPA"):
                right = parts.pop()
            title = parts.pop(0)
            segments = (Segment(title, not (blocks and blocks[-1].kind == "education")),)
            details = [p for p in parts if p]
            if details:
                segments += (Segment(" | " + " | ".join(details)),)
            kind = "education_detail" if blocks and blocks[-1].kind == "education" else "education"
            blocks.append(Block(kind, segments, right))
        elif section.startswith("CERTIFICATIONS"):
            if line.lower().startswith("awards:"):
                label, _, rest = line.partition(":")
                blocks.append(Block("body", (Segment(label + ":", True), Segment(rest))))
                continue
            segments = []
            for part in (p.strip() for p in line.split("|")):
                if not part:
                    continue
                if segments:
                    segments.append(Segment(" | "))
                segments.append(Segment(part, False))
            blocks.append(Block("body", tuple(segments)))
        else:
            blocks.append(Block("body", (Segment(line),)))
    return ResumeDocument(tuple(blocks))
