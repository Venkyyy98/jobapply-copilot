from app.llm import LLMClient
from app.parser import parse_job_fields


def test_parse_job_fields_heuristics():
    text = """
Senior Data Engineer
Responsibilities:
- Build ETL pipelines in Python and SQL.
- Collaborate with analytics team.
Requirements:
- 5+ years experience with Python, AWS, and Docker.
"""
    llm = LLMClient(api_key="")
    result = parse_job_fields(
        llm=llm,
        job_text=text,
        page_title="Senior Data Engineer | Example Corp",
        company_hint="",
        url="https://example.com/job",
    )

    assert result["title"] == "Senior Data Engineer"
    assert result["company"] == "Example Corp"
    assert any("python" in r.lower() for r in result["requirements"])
    assert "Aws" in result["skills"] or "AWS" in result["skills"]
