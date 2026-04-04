from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re

from docx import Document
from docx.enum.text import WD_LINE_SPACING, WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


def _safe(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_contact_line_with_links(line: str) -> str:
    segments = [seg.strip() for seg in line.split("|")]
    rendered: list[str] = []
    for seg in segments:
        if seg.lower().startswith("linkedin:"):
            url = seg.split(":", 1)[1].strip()
            rendered.append(f'<link href="{_safe(url)}" color="blue">LinkedIn</link>')
            continue
        if seg.lower().startswith("github:"):
            url = seg.split(":", 1)[1].strip()
            rendered.append(f'<link href="{_safe(url)}" color="blue">Github</link>')
            continue
        if seg.lower().startswith("portfolio:"):
            url = seg.split(":", 1)[1].strip()
            rendered.append(f'<link href="{_safe(url)}" color="blue">Portfolio</link>')
            continue
        rendered.append(_safe(seg))
    return " | ".join(rendered)


def _format_project_line_with_link(line: str) -> str:
    # Example expected format:
    # "Project Name (GitHub:https://github.com/org/repo)"
    m = re.search(r"\((git(?:hub)?):\s*(https?://[^)]+)\)$", line, flags=re.IGNORECASE)
    if not m:
        return _safe(line)
    label = m.group(1)
    url = m.group(2).strip()
    head = line[: m.start()].rstrip()
    return f'{_safe(head)} (<link href="{_safe(url)}" color="blue">{_safe(label.title())}</link>)'


def _format_cover_contact_line(line: str) -> str:
    segments = [seg.strip() for seg in line.split("|")]
    rendered: list[str] = []
    for seg in segments:
        if "linkedin.com/" in seg.lower():
            url = seg if seg.lower().startswith("http") else f"https://{seg}"
            rendered.append(f'<link href="{_safe(url)}" color="blue">{_safe(seg)}</link>')
        else:
            rendered.append(_safe(seg))
    return " | ".join(rendered)


def _format_skill_line(line: str) -> str:
    if ":" not in line:
        return _safe(line)
    label, rest = line.split(":", 1)
    return f"<b>{_safe(label.strip())}:</b>{_safe(rest)}"


def _split_cover_letter(text: str) -> dict[str, object]:
    lines = [line.rstrip() for line in text.splitlines()]
    nonempty = [line.strip() for line in lines if line.strip()]
    if len(nonempty) < 8:
        return {
            "name": "",
            "contact": "",
            "date": "",
            "recipient": [],
            "salutation": "",
            "body": [p.strip() for p in text.split("\n\n") if p.strip()],
            "closing": [],
        }

    name = nonempty[0]
    contact = nonempty[1] if len(nonempty) > 1 else ""
    date_line = nonempty[2] if len(nonempty) > 2 else ""
    salutation_index = next((idx for idx, line in enumerate(nonempty) if line.lower().startswith("dear ")), 6)
    recipient = nonempty[3:salutation_index]
    salutation = nonempty[salutation_index] if salutation_index < len(nonempty) else "Dear Hiring Manager,"
    closing_markers = {"sincerely,", "best regards,", "regards,"}
    closing_index = next(
        (idx for idx, line in enumerate(nonempty) if line.lower() in closing_markers),
        len(nonempty),
    )
    body = nonempty[salutation_index + 1 : closing_index]
    closing = nonempty[closing_index:] if closing_index < len(nonempty) else []
    return {
        "name": name,
        "contact": contact,
        "date": date_line,
        "recipient": recipient,
        "salutation": salutation,
        "body": body,
        "closing": closing,
    }


SECTION_HEADERS = {
    "PROFESSIONAL SUMMARY",
    "PROFESSIONAL EXPERIENCE",
    "EDUCATION",
    "ACADEMIC PROJECTS",
    "TECHNICAL SKILLS",
}


DEFAULT_RESUME_LAYOUT = {
    "left_margin": 0.5,
    "right_margin": 0.5,
    "top_margin": 0.4,
    "bottom_margin": 0.4,
    "name_font": 16.0,
    "name_leading": 18.0,
    "name_space_after": 3.0,
    "contact_font": 9.3,
    "contact_leading": 10.6,
    "contact_space_after": 7.0,
    "heading_font": 10.2,
    "heading_leading": 11.5,
    "heading_space_before": 6.0,
    "heading_space_after": 3.0,
    "heading_rule_before": 1.0,
    "heading_rule_after": 3.0,
    "company_font": 9.4,
    "company_leading": 10.6,
    "company_space_before": 1.0,
    "company_space_after": 1.0,
    "role_font": 9.1,
    "role_leading": 10.3,
    "role_space_after": 1.0,
    "body_font": 9.0,
    "body_leading": 10.2,
    "body_space_after": 1.0,
    "bullet_left_indent": 9.0,
    "bullet_first_line_indent": -7.0,
    "bullet_space_after": 1.0,
    "docx_paragraph_space_after": 3.0,
    "docx_bullet_space_after": 2.0,
    "docx_heading_space_after": 3.0,
    "docx_project_space_after": 3.0,
    "docx_contact_space_after": 7.0,
    "docx_skill_space_after": 3.0,
}

TIGHT_RESUME_LAYOUT = {
    **DEFAULT_RESUME_LAYOUT,
    "left_margin": 0.48,
    "right_margin": 0.48,
    "top_margin": 0.36,
    "bottom_margin": 0.36,
    "contact_leading": 10.4,
    "contact_space_after": 6.0,
    "heading_leading": 11.2,
    "heading_space_before": 5.0,
    "heading_space_after": 2.0,
    "heading_rule_before": 0.5,
    "heading_rule_after": 2.0,
    "company_leading": 10.4,
    "company_space_before": 0.5,
    "company_space_after": 0.5,
    "role_leading": 10.1,
    "role_space_after": 0.5,
    "body_leading": 10.0,
    "body_space_after": 0.5,
    "bullet_space_after": 0.5,
    "docx_paragraph_space_after": 2.0,
    "docx_bullet_space_after": 1.0,
    "docx_heading_space_after": 2.0,
    "docx_project_space_after": 2.0,
    "docx_contact_space_after": 6.0,
    "docx_skill_space_after": 2.0,
}


class _CountingCanvas(Canvas):
    last_page_count = 0

    def save(self) -> None:
        type(self).last_page_count = self._pageNumber
        super().save()


def _resume_lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    return [line for line in lines if line.strip()]


def _resume_pdf_story(lines: list[str], layout: dict[str, float]) -> list[object]:
    base = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "ResumeName",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=layout["name_font"],
        leading=layout["name_leading"],
        alignment=1,
        spaceAfter=layout["name_space_after"],
    )
    contact_style = ParagraphStyle(
        "ResumeContact",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=layout["contact_font"],
        leading=layout["contact_leading"],
        alignment=1,
        spaceAfter=layout["contact_space_after"],
    )
    heading_style = ParagraphStyle(
        "ResumeHeading",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=layout["heading_font"],
        leading=layout["heading_leading"],
        spaceBefore=layout["heading_space_before"],
        spaceAfter=layout["heading_space_after"],
    )
    company_style = ParagraphStyle(
        "ResumeCompany",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=layout["company_font"],
        leading=layout["company_leading"],
        spaceBefore=layout["company_space_before"],
        spaceAfter=layout["company_space_after"],
    )
    role_style = ParagraphStyle(
        "ResumeRole",
        parent=base["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=layout["role_font"],
        leading=layout["role_leading"],
        spaceAfter=layout["role_space_after"],
    )
    body_style = ParagraphStyle(
        "ResumeBody",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=layout["body_font"],
        leading=layout["body_leading"],
        spaceAfter=layout["body_space_after"],
    )
    bullet_style = ParagraphStyle(
        "ResumeBullet",
        parent=body_style,
        leftIndent=layout["bullet_left_indent"],
        firstLineIndent=layout["bullet_first_line_indent"],
        spaceAfter=layout["bullet_space_after"],
    )

    story: list[object] = []
    story.append(Paragraph(_safe(lines[0]), name_style))
    if len(lines) > 1:
        story.append(Paragraph(_format_contact_line_with_links(lines[1]), contact_style))

    in_experience = False
    current_section = ""
    for line in lines[2:]:
        stripped = line.strip()
        if stripped in SECTION_HEADERS:
            current_section = stripped
            in_experience = stripped == "PROFESSIONAL EXPERIENCE"
            story.append(Paragraph(_safe(stripped), heading_style))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.75,
                    color=colors.black,
                    spaceBefore=layout["heading_rule_before"],
                    spaceAfter=layout["heading_rule_after"],
                )
            )
            continue

        if stripped.startswith("- "):
            story.append(Paragraph(_safe(f"• {stripped[2:]}"), bullet_style))
            continue

        if in_experience and " | " in stripped and "-" in stripped:
            story.append(Paragraph(_safe(stripped), company_style))
            continue

        if in_experience and "(" in stripped and ")" in stripped:
            story.append(Paragraph(_safe(stripped), role_style))
            continue

        if current_section == "ACADEMIC PROJECTS" and not stripped.startswith("- "):
            story.append(Paragraph(_format_project_line_with_link(stripped), company_style))
            continue

        if current_section == "TECHNICAL SKILLS" and ":" in stripped:
            story.append(Paragraph(_format_skill_line(stripped), body_style))
            continue

        story.append(Paragraph(_safe(stripped), body_style))

    return story


def _render_resume_pdf_bytes(text: str, layout: dict[str, float]) -> tuple[bytes, int]:
    lines = _resume_lines(text)
    if not lines:
        return b"", 0

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=layout["left_margin"] * inch,
        rightMargin=layout["right_margin"] * inch,
        topMargin=layout["top_margin"] * inch,
        bottomMargin=layout["bottom_margin"] * inch,
    )
    story = _resume_pdf_story(lines, layout)

    class CountingCanvas(_CountingCanvas):
        pass

    doc.build(story, canvasmaker=CountingCanvas)
    return buffer.getvalue(), CountingCanvas.last_page_count


@lru_cache(maxsize=32)
def _should_use_tight_resume_layout(text: str) -> bool:
    _, default_pages = _render_resume_pdf_bytes(text, DEFAULT_RESUME_LAYOUT)
    if default_pages <= 1:
        return False
    _, tight_pages = _render_resume_pdf_bytes(text, TIGHT_RESUME_LAYOUT)
    return tight_pages <= 1


@lru_cache(maxsize=32)
def resume_layout_status(text: str) -> str:
    _, default_pages = _render_resume_pdf_bytes(text, DEFAULT_RESUME_LAYOUT)
    if default_pages <= 1:
        return "default"
    _, tight_pages = _render_resume_pdf_bytes(text, TIGHT_RESUME_LAYOUT)
    if tight_pages <= 1:
        return "tight"
    return "overflow"


def resume_text_to_pdf(text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = _resume_lines(text)
    if not lines:
        return text_to_pdf(text, output_path)

    default_bytes, default_pages = _render_resume_pdf_bytes(text, DEFAULT_RESUME_LAYOUT)
    if default_pages <= 1:
        output_path.write_bytes(default_bytes)
        return

    tight_bytes, tight_pages = _render_resume_pdf_bytes(text, TIGHT_RESUME_LAYOUT)
    output_path.write_bytes(tight_bytes if tight_pages <= 1 else default_bytes)


def cover_letter_text_to_pdf(text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
    )
    styles = getSampleStyleSheet()
    parsed = _split_cover_letter(text)
    name_style = ParagraphStyle(
        "CoverName",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=18,
        alignment=1,
        spaceAfter=4,
    )
    contact_style = ParagraphStyle(
        "CoverContact",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=11,
        alignment=1,
        spaceAfter=12,
    )
    meta_style = ParagraphStyle(
        "CoverMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        spaceAfter=1,
    )
    salutation_style = ParagraphStyle(
        "CoverSalutation",
        parent=meta_style,
        spaceBefore=10,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "CoverBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        spaceAfter=8,
    )
    closing_style = ParagraphStyle(
        "CoverClosing",
        parent=meta_style,
        spaceBefore=8,
        spaceAfter=3,
    )
    story = []
    if parsed["name"]:
        story.append(Paragraph(_safe(str(parsed["name"])), name_style))
    if parsed["contact"]:
        story.append(Paragraph(_format_cover_contact_line(str(parsed["contact"])), contact_style))
    if parsed["date"]:
        story.append(Paragraph(_safe(str(parsed["date"])), meta_style))
    for line in parsed["recipient"]:
        story.append(Paragraph(_safe(str(line)), meta_style))
    if parsed["salutation"]:
        story.append(Paragraph(_safe(str(parsed["salutation"])), salutation_style))
    for paragraph in parsed["body"]:
        story.append(Paragraph(_safe(str(paragraph)).replace("\n", "<br/>"), body))
    for line in parsed["closing"]:
        story.append(Paragraph(_safe(str(line)), closing_style))
    doc.build(story)


def text_to_pdf(text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=LETTER)
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontName = "Helvetica"
    body.fontSize = 10
    body.leading = 14

    story = []
    for paragraph in [p.strip() for p in text.split("\n\n") if p.strip()]:
        safe = paragraph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(safe.replace("\n", "<br/>"), body))
        story.append(Spacer(1, 8))

    doc.build(story)


def text_to_docx(text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    lines = [line.rstrip() for line in text.splitlines()]
    paragraph = None
    for line in lines:
        if not line.strip():
            paragraph = None
            continue
        if paragraph is None:
            paragraph = doc.add_paragraph(line.strip())
        else:
            paragraph.add_run("\n" + line.strip())
    doc.save(str(output_path))


def _set_page_margins(doc: Document, left: float, right: float, top: float, bottom: float) -> None:
    section = doc.sections[0]
    section.left_margin = Inches(left)
    section.right_margin = Inches(right)
    section.top_margin = Inches(top)
    section.bottom_margin = Inches(bottom)


def _set_run_font(run, font_name: str, size: float | None = None) -> None:
    run.font.name = font_name
    if size is not None:
        run.font.size = Pt(size)
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        r_fonts.set(qn(f"w:{attr}"), font_name)


def _set_docx_default_font(doc: Document, font_name: str = "Helvetica") -> None:
    for style_name in ("Normal", "List Bullet"):
        try:
            style = doc.styles[style_name]
        except KeyError:
            continue
        style.font.name = font_name
        r_pr = style.element.get_or_add_rPr()
        r_fonts = r_pr.rFonts
        if r_fonts is None:
            r_fonts = OxmlElement("w:rFonts")
            r_pr.append(r_fonts)
        for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
            r_fonts.set(qn(f"w:{attr}"), font_name)
        try:
            style.paragraph_format.space_before = Pt(0)
            style.paragraph_format.space_after = Pt(0)
            style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        except Exception:
            pass


def _add_hyperlink(paragraph, text: str, url: str) -> None:
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    r_fonts = OxmlElement("w:rFonts")
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        r_fonts.set(qn(f"w:{attr}"), "Helvetica")
    r_pr.append(r_fonts)
    r_pr.append(color)
    r_pr.append(u)
    new_run.append(r_pr)
    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def _add_bottom_border(paragraph) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = p_bdr.find(qn("w:bottom"))
    if bottom is None:
        bottom = OxmlElement("w:bottom")
        p_bdr.append(bottom)
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "8")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")


def _docx_paragraph(
    doc: Document,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    size: float = 10.0,
    leading: float | None = None,
    align: WD_PARAGRAPH_ALIGNMENT | None = None,
    bullet: bool = False,
    layout: dict[str, float] = DEFAULT_RESUME_LAYOUT,
) -> None:
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(
        layout["docx_bullet_space_after"] if bullet else layout["docx_paragraph_space_after"]
    )
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(leading or (size * 1.13))
    if bullet:
        p.paragraph_format.left_indent = Pt(layout["bullet_left_indent"])
        p.paragraph_format.first_line_indent = Pt(layout["bullet_first_line_indent"])
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    _set_run_font(run, "Helvetica", size)


def _docx_contact_line(doc: Document, line: str, layout: dict[str, float] = DEFAULT_RESUME_LAYOUT) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(layout["docx_contact_space_after"])
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(layout["contact_leading"])
    segments = [seg.strip() for seg in line.split("|")]
    first = True
    for seg in segments:
        if not first:
            sep = p.add_run(" | ")
            _set_run_font(sep, "Helvetica", 9.3)
        low = seg.lower()
        if low.startswith("linkedin:"):
            url = seg.split(":", 1)[1].strip()
            _add_hyperlink(p, "LinkedIn", url)
        elif low.startswith("github:"):
            url = seg.split(":", 1)[1].strip()
            _add_hyperlink(p, "Github", url)
        elif low.startswith("portfolio:"):
            url = seg.split(":", 1)[1].strip()
            _add_hyperlink(p, "Portfolio", url)
        else:
            run = p.add_run(seg)
            _set_run_font(run, "Helvetica", 9.3)
        first = False


def _docx_skill_line(doc: Document, line: str, layout: dict[str, float]) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(layout["docx_skill_space_after"])
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(layout["body_leading"])
    if ":" not in line:
        run = p.add_run(line)
        _set_run_font(run, "Helvetica", 9.0)
        return
    label, rest = line.split(":", 1)
    head = p.add_run(f"{label.strip()}:")
    head.bold = True
    _set_run_font(head, "Helvetica", 9.0)
    tail = p.add_run(rest)
    _set_run_font(tail, "Helvetica", 9.0)


def _docx_project_line(doc: Document, line: str, layout: dict[str, float]) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(layout["docx_project_space_after"])
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(layout["company_leading"])
    m = re.search(r"\((git(?:hub)?):\s*(https?://[^)]+)\)$", line, flags=re.IGNORECASE)
    if not m:
        run = p.add_run(line)
        run.bold = True
        _set_run_font(run, "Helvetica", 9.4)
        return
    head = line[: m.start()].rstrip()
    label = m.group(1).title()
    url = m.group(2).strip()
    run = p.add_run(f"{head} (")
    run.bold = True
    _set_run_font(run, "Helvetica", 9.4)
    _add_hyperlink(p, label, url)
    run2 = p.add_run(")")
    run2.bold = True
    _set_run_font(run2, "Helvetica", 9.4)


def resume_text_to_docx(text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    layout = TIGHT_RESUME_LAYOUT if _should_use_tight_resume_layout(text) else DEFAULT_RESUME_LAYOUT
    doc = Document()
    _set_docx_default_font(doc, "Helvetica")
    _set_page_margins(
        doc,
        left=layout["left_margin"],
        right=layout["right_margin"],
        top=layout["top_margin"],
        bottom=layout["bottom_margin"],
    )

    lines = _resume_lines(text)
    if not lines:
        return text_to_docx(text, output_path)

    _docx_paragraph(
        doc,
        lines[0].strip(),
        bold=True,
        size=16,
        leading=layout["name_leading"],
        align=WD_PARAGRAPH_ALIGNMENT.CENTER,
        layout=layout,
    )
    if len(lines) > 1:
        _docx_contact_line(doc, lines[1].strip(), layout)

    in_experience = False
    current_section = ""
    for line in lines[2:]:
        stripped = line.strip()
        if stripped in SECTION_HEADERS:
            current_section = stripped
            in_experience = stripped == "PROFESSIONAL EXPERIENCE"
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(layout["docx_heading_space_after"])
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            p.paragraph_format.line_spacing = Pt(layout["heading_leading"])
            run = p.add_run(stripped)
            run.bold = True
            _set_run_font(run, "Helvetica", 10.2)
            _add_bottom_border(p)
            continue

        if stripped.startswith("- "):
            _docx_paragraph(
                doc,
                f"• {stripped[2:].strip()}",
                size=9.0,
                leading=layout["body_leading"],
                bullet=True,
                layout=layout,
            )
            continue

        if in_experience and " | " in stripped and "-" in stripped:
            _docx_paragraph(doc, stripped, bold=True, size=9.4, leading=layout["company_leading"], layout=layout)
            continue

        if in_experience and "(" in stripped and ")" in stripped:
            _docx_paragraph(doc, stripped, italic=True, size=9.1, leading=layout["role_leading"], layout=layout)
            continue

        if current_section == "ACADEMIC PROJECTS" and not stripped.startswith("- "):
            _docx_project_line(doc, stripped, layout)
            continue

        if current_section == "TECHNICAL SKILLS" and ":" in stripped:
            _docx_skill_line(doc, stripped, layout)
            continue

        _docx_paragraph(doc, stripped, size=9.0, leading=layout["body_leading"], layout=layout)

    doc.save(str(output_path))


def cover_letter_text_to_docx(text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    _set_docx_default_font(doc, "Helvetica")
    _set_page_margins(doc, left=0.8, right=0.8, top=0.8, bottom=0.8)
    parsed = _split_cover_letter(text)

    if parsed["name"]:
        _docx_paragraph(
            doc,
            str(parsed["name"]),
            bold=True,
            size=16,
            align=WD_PARAGRAPH_ALIGNMENT.CENTER,
        )

    if parsed["contact"]:
        p = doc.add_paragraph()
        p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        p.paragraph_format.space_after = Pt(10)
        segments = [seg.strip() for seg in str(parsed["contact"]).split("|")]
        first = True
        for seg in segments:
            if not first:
                sep = p.add_run("  |  ")
                _set_run_font(sep, "Helvetica", 9.5)
            if "linkedin.com/" in seg.lower():
                url = seg if seg.lower().startswith("http") else f"https://{seg}"
                _add_hyperlink(p, seg, url)
            else:
                run = p.add_run(seg)
                _set_run_font(run, "Helvetica", 9.5)
            first = False

    if parsed["date"]:
        _docx_paragraph(doc, str(parsed["date"]), size=11, align=WD_PARAGRAPH_ALIGNMENT.LEFT)
    for line in parsed["recipient"]:
        _docx_paragraph(doc, str(line), size=11, align=WD_PARAGRAPH_ALIGNMENT.LEFT)
    if parsed["salutation"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(str(parsed["salutation"]))
        _set_run_font(run, "Helvetica", 11)
    for para in parsed["body"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(str(para))
        _set_run_font(run, "Helvetica", 11)
    for idx, line in enumerate(parsed["closing"]):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6 if idx == 0 else 0)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(str(line))
        _set_run_font(run, "Helvetica", 11)

    doc.save(str(output_path))
