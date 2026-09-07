from zipfile import ZipFile

from lxml import etree
import pytest

from app.resume_document import Segment, bullet_segments, html_segments, parse_resume
from app.resume_export import FONT, export_docx, export_pdf, pdf_bytes, pdf_story, typography


SAMPLE = """Alex Candidate
San Francisco, CA | 2012756554 | alex@example.com | LinkedIn:https://linkedin.com/in/alex

SUMMARY
Engineer building factual, measurable data systems.
TECHNICAL SKILLS
Languages & Backend: Python, Java, SQL
PROFESSIONAL EXPERIENCE
Senior AI Engineer - Enterprise Automation | Example Research & Development Corporation | San Francisco Bay Area, California | Jan 2023 - Present
- Built **RAG pipelines** using Python & SQL, reducing investigation time by **40%**.
- Refactored 30+ integration workflows into modular pipelines, increasing throughput by 30%.
- Preserved <special> characters & quotes, with malformed **markup and no invented results.
PROJECTS
Search & Retrieval | GitHub:https://github.com/example/search?x=1&y=2
- Built FAISS semantic search across 500+ adversarial test cases.
EDUCATION
M.S. Data Science | May 2026 | Hoboken, NJ
Example University | GPA 3.82
CERTIFICATIONS & AWARDS
AWS Certified AI Practitioner | Sep 2025 - Sep 2028
"""


def test_canonical_emphasis_preserves_text_and_limits_bold():
    for raw in ["Built **RAG pipelines** using SQL, improving recall by **18%**.",
                "Built **malformed markup with Python & <XML>.",
                "**Built an entire system with Python and SQL across many services.**"]:
        segments = bullet_segments(raw)
        assert "".join(s.text for s in segments) == raw.replace("**", "")
        assert 1 <= sum(s.bold for s in segments) <= 2
        assert not all(s.bold for s in segments)
        assert "**" not in html_segments(segments)


def test_safe_text_and_url_validation():
    assert html_segments((Segment('<XML> & "quotes"', True),)) == '<b>&lt;XML&gt; &amp; &quot;quotes&quot;</b>'
    with pytest.raises(ValueError):
        Segment("click", url="javascript:alert(1)")


def test_required_hierarchy_and_empty_fields():
    model = parse_resume(SAMPLE.replace("San Francisco Bay Area, California", ""))
    entry = next(b for b in model.blocks if b.kind == "entry")
    assert [s.bold for s in entry.segments if s.text != " | "] == [True, True]
    assert " |  | " not in "".join(s.text for s in entry.segments)
    assert entry.right == "Jan 2023 - Present"
    assert all(b.segments[0].bold for b in model.blocks if b.kind in {"name", "heading", "entry", "education"})
    assert not any(not "".join(s.text for s in b.segments).strip() for b in model.blocks)
    assert "(201) 275-6554" in "".join(s.text for s in model.blocks[1].segments)


def test_both_exports_keep_fonts_bold_links_and_dates(tmp_path):
    pdf, docx = tmp_path / "sample.pdf", tmp_path / "sample.docx"
    export_pdf(SAMPLE, pdf)
    export_docx(SAMPLE, docx)
    assert pdf_bytes(parse_resume(SAMPLE))[1] == 1
    data = pdf.read_bytes()
    assert b"/FontFile2" in data
    assert b"/URI (https://github.com/example/search?x=1&y=2)" in data
    assert b"/URI (https://linkedin.com/in/alex)" in data
    with ZipFile(docx) as archive:
        xml = etree.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = xml.xpath("//w:t/text()", namespaces=ns)
        assert "**" not in "".join(texts)
        assert "<special>" in "".join(texts)
        for run in xml.xpath("//w:r[w:t]", namespaces=ns):
            assert run.xpath("w:rPr/w:rFonts/@w:ascii", namespaces=ns) == [FONT]
            assert run.xpath("w:rPr/w:sz/@w:val", namespaces=ns)
        bold = xml.xpath("//w:r[w:rPr/w:b[not(@w:val='0')]]/w:t/text()", namespaces=ns)
        for label in ["Alex Candidate", "Languages & Backend:", "RAG pipelines", "40%", "M.S. Data Science"]:
            assert label in bold
        date_paragraphs = xml.xpath("//w:p[w:r/w:t='Jan 2023 - Present']", namespaces=ns)
        assert date_paragraphs[0].xpath("w:pPr/w:jc/@w:val", namespaces=ns) == ["right"]
        assert not xml.xpath("//w:tab", namespaces=ns)
        assert len(xml.xpath("//w:hyperlink", namespaces=ns)) == 2
        assert len([n for n in archive.namelist() if n.endswith(".odttf")]) == 2
        assert "embedBold" in archive.read("word/fontTable.xml").decode()


def test_pdf_fragments_match_canonical_emphasis():
    fragments = []
    def collect(item):
        fragments.extend(getattr(item, "frags", []))
        for row in getattr(item, "_cellvalues", []):
            for cell in row:
                collect(cell)
    for item in pdf_story(parse_resume(SAMPLE)):
        collect(item)
    assert any(getattr(f, "text", "") == "40%" and f.fontName.endswith("Bold") for f in fragments)
    assert all(f.fontName.startswith("ResumeSerif") for f in fragments if hasattr(f, "fontName"))
    assert typography("bullet", True)[0] >= 9.5


def test_long_content_wraps_without_loss_or_tiny_fonts(tmp_path):
    text = SAMPLE.replace("Senior AI Engineer - Enterprise Automation", "Senior Engineer for Machine Learning and Enterprise Automation " * 3)
    text += "\nPROJECTS\nExtended Evaluation\n" + "- Built Python data pipelines with validated results.\n" * 90
    model = parse_resume(text)
    assert pdf_bytes(model)[1] > 1
    export_docx(text, tmp_path / "long.docx")
    assert len(model.blocks) > 90


@pytest.mark.parametrize("fail_export", [False, True])
def test_generation_endpoint_contract_and_no_plain_resume_fallback(tmp_path, monkeypatch, fail_export):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from app import main
    from app.llm import LLMClient
    from app.storage import Storage

    storage = Storage(tmp_path / "jobs.db")
    monkeypatch.setattr(main, "storage", storage)
    monkeypatch.setattr(main, "settings", replace(main.settings, output_dir=tmp_path / "outputs"))
    monkeypatch.setattr(main, "validate_job_content", lambda *a: "")
    monkeypatch.setattr(main, "require_complete_candidate_context", lambda *a: ({}, {}))
    monkeypatch.setattr(main, "parse_job_fields", lambda **kw: {"title": "Engineer", "company": "Example"})
    monkeypatch.setattr(main, "build_tailoring_plan", lambda *a: {})
    monkeypatch.setattr(main, "rewrite_selected_bullets", lambda *a, **kw: {})
    monkeypatch.setattr(main, "rewrite_project_descriptions", lambda *a, **kw: {})
    monkeypatch.setattr(main, "render_resume_text", lambda **kw: SAMPLE)
    monkeypatch.setattr(main, "render_cover_letter_text", lambda **kw: "Dear Hiring Manager,\n\nI am interested in this position.")
    monkeypatch.setattr(main, "check_for_unsupported_claims", lambda *a: [])
    if fail_export:
        def fail(*a):
            raise ValueError("Render failure")
        monkeypatch.setattr(main, "resume_text_to_docx", fail)
    job_id = storage.create_job({"title": "Engineer", "company": "Example", "job_text": "Engineer position"})
    main.app.dependency_overrides[main.require_api_user] = lambda: None
    main.app.dependency_overrides[main.request_llm] = lambda: LLMClient(api_key="")
    try:
        response = TestClient(main.app).post("/generate_docs", json={"job_id": job_id, "approve": True})
        if fail_export:
            assert response.status_code == 500
            assert "Resume formatting failed" in response.json()["detail"]
            assert not (tmp_path / "outputs" / str(job_id) / "resume.docx").exists()
        else:
            assert response.status_code == 200
            payload = response.json()
            assert payload["compliance_passed"]
            assert payload["ai_assisted"] is False
            assert payload["files"]["resume_docx"] == f"/download/{job_id}/resume_docx"
            assert (tmp_path / "outputs" / str(job_id) / "resume.pdf").exists()
    finally:
        main.app.dependency_overrides.pop(main.require_api_user, None)
        main.app.dependency_overrides.pop(main.request_llm, None)
