"""Offline role/layout regression samples. No API key or network requests.

Run from the repository root: .venv/bin/python scripts/preview_resumes.py
"""
import argparse
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.exporters import resume_text_to_docx, resume_text_to_pdf, resume_layout_status
from app.resume_render import render_resume_text
from app.tailoring import build_tailoring_plan
from app.llm import LLMClient

ROLES = {
    "ai_ml_engineer": ("Machine Learning Engineer", ["Python", "RAG", "LLM evaluation", "FastAPI"]),
    "data_engineer": ("Data Engineer", ["Python", "SQL", "Java", "MySQL", "Spark"]),
    "data_scientist": ("Data Scientist", ["Python", "machine learning", "statistics", "PyTorch"]),
    "business_analyst": ("Business Analyst", ["SQL", "Power BI", "requirements analysis"]),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "server/data/candidate_profile.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "output/resume-previews")
    args = parser.parse_args()
    candidate = yaml.safe_load(args.profile.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    for name, (title, skills) in ROLES.items():
        job = {"title": title, "company": "Preview Company", "location": "San Francisco, CA", "skills": skills}
        plan = build_tailoring_plan(LLMClient(api_key=""), job, candidate, {})
        text = render_resume_text(
            ROOT / "server/data/templates", candidate,
            job, plan["suggested_bullets"], plan.get("suggested_project_ids", []), {}, {}, skills,
        )
        (args.output / f"{name}.txt").write_text(text)
        resume_text_to_pdf(text, args.output / f"{name}.pdf")
        resume_text_to_docx(text, args.output / f"{name}.docx")
        print(f"{name}: {resume_layout_status(text)} -> {args.output / name}")


if __name__ == "__main__":
    main()
