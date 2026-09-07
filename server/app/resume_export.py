"""PDF and DOCX adapters for the canonical resume document."""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from lxml import etree

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.part import Part
from docx.opc.packuri import PackURI
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from .resume_document import Block, ResumeDocument, Segment, html_segments, parse_resume

FONT = "Liberation Serif"
FONT_DIR = Path(__file__).resolve().parent / "fonts"
NAVY = "000000"
WIDTH = 538.0
MARGIN = 37.0


@lru_cache(maxsize=1)
def register_fonts():
    pdfmetrics.registerFont(TTFont("ResumeSerif", str(FONT_DIR / "LiberationSerif-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("ResumeSerif-Bold", str(FONT_DIR / "LiberationSerif-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("ResumeSerif-Italic", str(FONT_DIR / "LiberationSerif-Italic.ttf")))
    pdfmetrics.registerFontFamily("ResumeSerif", normal="ResumeSerif", bold="ResumeSerif-Bold",
                                italic="ResumeSerif-Italic", boldItalic="ResumeSerif-Bold")


def typography(kind: str, compact: bool = False):
    size = {"name": 18, "contact": 8.5, "heading": 11}.get(kind, 9.5 if compact else 10.2)
    leading = size * (1.10 if compact else 1.16)
    before = {"heading": 4 if compact else 7, "entry": 1 if compact else 2}.get(kind, 0)
    after = {"name": 2, "contact": 4, "heading": 2 if compact else 3, "bullet": 0 if compact else 1}.get(kind, 0 if compact else 1)
    return size, leading, before, after


class HeadingParagraph(Paragraph):
    def draw(self):
        super().draw()
        self.canv.setStrokeColor("#" + NAVY)
        self.canv.setLineWidth(.5)
        self.canv.line(0, -1, self.width, -1)


def pdf_story(model: ResumeDocument, compact: bool = False):
    register_fonts()
    story = []
    for block in model.blocks:
        size, leading, before, after = typography(block.kind, compact)
        style = ParagraphStyle(
            block.kind, fontName="ResumeSerif", fontSize=size, leading=leading,
            spaceBefore=before, spaceAfter=after, alignment=1 if block.kind in {"name", "contact"} else 0,
            textColor="#" + NAVY if block.kind in {"name", "heading"} else "#111111",
            keepWithNext=block.kind in {"heading", "entry", "education"} or (block.kind == "education_detail" and bool(block.right)), allowWidows=0, allowOrphans=0,
            leftIndent=10 if block.kind == "bullet" else 0,
            firstLineIndent=-6 if block.kind == "bullet" else 0,
        )
        value = html_segments(block.segments)
        if block.kind == "bullet":
            value = "&#8226; " + value
        paragraph = (HeadingParagraph if block.kind == "heading" else Paragraph)(value, style)
        if block.right:
            right_style = ParagraphStyle("date", parent=style, alignment=2, keepWithNext=False,
                                         fontName="ResumeSerif-Italic" if block.kind in {"education", "education_detail"} else "ResumeSerif")
            right = Paragraph(html_segments((Segment(block.right),)), right_style)
            table = Table([[paragraph, right]], colWidths=[WIDTH - 125, 125])
            table.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 8),
                ("RIGHTPADDING", (1, 0), (1, 0), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            table.spaceBefore, table.spaceAfter = before, after
            table.keepWithNext = block.kind in {"entry", "education", "education_detail"}
            story.append(table)
        else:
            story.append(paragraph)
    return story


def pdf_bytes(model: ResumeDocument, compact: bool = False):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(612, 792), leftMargin=MARGIN - 6, rightMargin=MARGIN - 6,
                            topMargin=25, bottomMargin=25)
    doc.build(pdf_story(model, compact))
    value = buffer.getvalue()
    return value, doc.page


@lru_cache(maxsize=32)
def layout_status(text: str):
    model = parse_resume(text)
    if pdf_bytes(model)[1] <= 1:
        return "default"
    if pdf_bytes(model, True)[1] <= 1:
        return "balanced"
    return "overflow"


def export_pdf(text: str, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    model = parse_resume(text)
    output.write_bytes(pdf_bytes(model, layout_status(text) == "balanced")[0])


def set_font(run, size: float, bold: bool = False):
    run.font.name, run.font.size, run.bold, run.italic = FONT, Pt(size), bold, False
    fonts = run._element.get_or_add_rPr().rFonts
    for name in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + name), FONT)


def embed_fonts(doc):
    font_table = doc.part.part_related_by("http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable")
    font = OxmlElement("w:font")
    font.set(qn("w:name"), FONT)
    for weight, tag in (("Regular", "embedRegular"), ("Bold", "embedBold")):
        key = uuid4()
        data = bytearray((FONT_DIR / f"LiberationSerif-{weight}.ttf").read_bytes())
        mask = key.bytes[::-1]
        for index in range(32):
            data[index] ^= mask[index % 16]
        part = Part(PackURI(f"/word/fonts/resume-{weight}.odttf"),
                    "application/vnd.openxmlformats-officedocument.obfuscatedFont", bytes(data), doc.part.package)
        rid = font_table.relate_to(part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font")
        element = OxmlElement("w:" + tag)
        element.set(qn("r:id"), rid)
        element.set(qn("w:fontKey"), "{" + str(key).upper() + "}")
        font.append(element)
    root = etree.fromstring(font_table.blob)
    root.append(font)
    font_table._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    doc.settings.element.append(OxmlElement("w:embedTrueTypeFonts"))


def add_segments(paragraph, segments, size):
    from docx.text.run import Run
    for segment in segments:
        if segment.url:
            hyperlink = OxmlElement("w:hyperlink")
            rid = paragraph.part.relate_to(segment.url,
                  "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
            hyperlink.set(qn("r:id"), rid)
            element = OxmlElement("w:r")
            hyperlink.append(element)
            paragraph._p.append(hyperlink)
            run = Run(element, paragraph)
            run.text = segment.text
            run.font.color.rgb = RGBColor.from_string("000000")
            run.underline = True
        else:
            run = paragraph.add_run(segment.text)
        set_font(run, size, segment.bold)


def format_paragraph(p, block, compact):
    size, leading, before, after = typography(block.kind, compact)
    fmt = p.paragraph_format
    fmt.space_before, fmt.space_after = Pt(before), Pt(after)
    fmt.line_spacing_rule, fmt.line_spacing = WD_LINE_SPACING.EXACTLY, Pt(leading)
    fmt.keep_together = True
    fmt.keep_with_next = block.kind in {"heading", "entry", "education"} or (block.kind == "education_detail" and bool(block.right))
    fmt.widow_control = True
    if block.kind in {"name", "contact"}:
        p.alignment = 1
    if block.kind == "bullet":
        fmt.left_indent, fmt.first_line_indent = Pt(10), Pt(-6)
        set_font(p.add_run("\u2022 "), size)
    add_segments(p, block.segments, size)
    if block.kind in {"name", "heading"}:
        for run in p.runs:
            run.font.color.rgb = RGBColor.from_string(NAVY)
    if block.kind == "heading":
        borders = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for key, value in {"val": "single", "sz": "4", "space": "0", "color": NAVY}.items():
            bottom.set(qn("w:" + key), value)
        borders.append(bottom)
        p._p.get_or_add_pPr().append(borders)


def export_docx(text: str, output: Path):
    from .resume_document import Segment
    model = parse_resume(text)
    compact = layout_status(text) == "balanced"
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Pt(MARGIN)
    section.top_margin = section.bottom_margin = Pt(31)
    doc.styles["Normal"].font.name = FONT
    doc.styles["Normal"].font.size = Pt(10)
    for block in model.blocks:
        if block.right:
            table = doc.add_table(rows=1, cols=2)
            table.autofit = False
            table.columns[0].width, table.columns[1].width = Pt(WIDTH - 125), Pt(125)
            table.cell(0, 0).width, table.cell(0, 1).width = Pt(WIDTH - 125), Pt(125)
            margins = OxmlElement("w:tblCellMar")
            for side in ("top", "left", "bottom", "right"):
                node = OxmlElement("w:" + side)
                node.set(qn("w:w"), "0")
                node.set(qn("w:type"), "dxa")
                margins.append(node)
            table._tbl.tblPr.append(margins)
            left, right = table.cell(0, 0).paragraphs[0], table.cell(0, 1).paragraphs[0]
            format_paragraph(left, block, compact)
            left.paragraph_format.right_indent = Pt(8)
            format_paragraph(right, Block("body", (Segment(block.right),)), compact)
            right.alignment = 2
            right.paragraph_format.keep_with_next = block.kind in {"entry", "education", "education_detail"}
            if block.kind in {"education", "education_detail"}:
                for run in right.runs:
                    run.italic = True
        else:
            format_paragraph(doc.add_paragraph(), block, compact)
    embed_fonts(doc)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
