from pathlib import Path

import pytest
import yaml

from app.resume_render import render_resume_text
from app.main import _generated_resume_fit_score, clean_role_for_filename
from app.cover_letter_render import render_cover_letter_text
from app.exporters import DEFAULT_RESUME_LAYOUT, _resume_pdf_story
from app.llm import LLMClient
from app.tailoring import _base_answers, build_tailoring_plan, detect_role_track, detect_sector, extract_ats_keywords, sanitize_ats_keywords


def test_resume_pdf_inline_labels_use_bold_font() -> None:
    story = _resume_pdf_story(
        [
            "Venkatesh Mudaliar",
            "Contact",
            "TECHNICAL SKILLS",
            "Machine Learning: Python, SQL",
            "PROFESSIONAL EXPERIENCE",
            "AI Engineer | Accenture | Mumbai, India | Feb 2023 - Sep 2024",
            "- Built production systems.",
            "EDUCATION",
            "M.S. Data Science | May 2026 | Hoboken, NJ",
            "Stevens Institute of Technology | GPA 3.82",
        ],
        DEFAULT_RESUME_LAYOUT,
    )

    fragments: list[tuple[str, str]] = []

    def collect(flowable: object) -> None:
        for fragment in getattr(flowable, "frags", []):
            fragments.append((str(getattr(fragment, "text", "")), str(getattr(fragment, "fontName", ""))))
        for row in getattr(flowable, "_cellvalues", []):
            for cell in row:
                for item in cell if isinstance(cell, (list, tuple)) else [cell]:
                    collect(item)

    for flowable in story:
        collect(flowable)

    assert any(text == "Machine Learning:" and font.endswith("Bold") for text, font in fragments)
    assert any(text == "AI Engineer" and font.endswith("Bold") for text, font in fragments)
    assert any(text == "Accenture" and font.endswith("Bold") for text, font in fragments)


def test_extract_ats_keywords_excludes_job_posting_prose() -> None:
    job_fields = {
        "requirements": [
            "We are looking for talented individuals to join us as a Data Engineer with Python, SQL, Spark, and Databricks."
        ],
        "responsibilities": ["Build ETL pipelines and improve data quality."],
        "skills": ["Python", "SQL", "Databricks"],
    }

    keywords = extract_ats_keywords(job_fields)

    assert "Python" in keywords
    assert "SQL" in keywords
    assert "Databricks" in keywords
    assert "ETL Pipelines" in keywords
    assert "We" not in keywords
    assert "looking" not in keywords
    assert "talented" not in keywords


def test_extract_ats_keywords_includes_required_java_and_mysql() -> None:
    keywords = extract_ats_keywords(
        {
            "requirements": [
                "Experience in Java with 3+ years in an enterprise environment.",
                "Proficiency in database technologies including MySQL or equivalent.",
            ],
            "responsibilities": [],
            "skills": [],
        }
    )

    assert "Java" in keywords
    assert "MySQL" in keywords


def test_sanitize_llm_ats_keywords_rejects_prose_tokens() -> None:
    job_fields = {"skills": ["We", "looking", "Python", "SQL", "Spark"]}
    keywords = sanitize_ats_keywords(["We", "are", "looking", "Python", "Spark"], job_fields)

    assert keywords == ["Python", "Spark"]


def test_base_answers_handles_empty_preferred_locations() -> None:
    answers = _base_answers(
        {"links": {"linkedin": "https://linkedin.example", "github": "https://github.example"}},
        {"preferred_locations": [], "work_authorization": ""},
    )

    assert answers["preferred_location"] == "Please confirm manually."
    assert answers["work_authorization"] == "Please confirm manually."
    assert answers["linkedin"] == "https://linkedin.example"


def test_data_scientist_fit_score_reflects_strong_profile_overlap() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    job_fields = {
        "title": "Data Scientist",
        "company": "Deloitte",
        "summary": "Experienced Data Scientist role in AI and Data practice.",
        "requirements": [
            "Bachelor's degree, preferably in Computer Science, Information Technology, Computer Engineering, or related IT discipline.",
            "5+ Years of Experience in a Data Science or Machine Learning role.",
            "5+ Years of Experience Proficiency in programming languages such as Python or R.",
            "Strong knowledge of machine learning techniques and algorithms.",
            "Experience with data manipulation and analysis libraries like pandas and NumPy.",
            "Experience with big data technologies like Spark or Hadoop.",
            "Experience with deep learning frameworks like TensorFlow or PyTorch.",
            "Familiarity with cloud platforms such as AWS, Azure, or GCP.",
            "Experience with data visualization tools like Tableau or Power BI.",
        ],
        "responsibilities": [
            "Collect, clean, and explore large datasets to uncover trends and patterns.",
            "Develop and train machine learning models for prediction, classification, and clustering.",
            "Communicate findings through data visualization and presentations.",
        ],
        "skills": ["Python", "R", "pandas", "NumPy", "Spark", "TensorFlow", "PyTorch", "AWS", "Azure", "GCP", "Tableau", "Power BI"],
    }

    plan = build_tailoring_plan(LLMClient(api_key=""), job_fields, candidate, {})

    assert plan["fit_score"] >= 75
    assert plan["role_track"] == "data_scientist"
    assert plan["sector_track"] == "generic"
    assert plan["keyword_coverage_pct"] >= 80
    assert "Python" in plan["matched_keywords"]
    assert "Machine Learning" in plan["matched_keywords"]
    assert set(plan["suggested_project_ids"]) == {"proj_1", "proj_2", "proj_8"}
    assert "proj_5" not in plan["suggested_project_ids"]


def test_product_data_scientist_role_gets_credit_for_transferable_analytics() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    job_fields = {
        "title": "Data Scientist",
        "company": "Twitch",
        "location": "San Francisco, CA",
        "job_text": (
            "Join the Monetization team. Partner with product, engineering, finance, and data teams "
            "to measure new features, design and analyze experiments, and apply causal inference methods. "
            "Develop models and analyses that inform pricing, segmentation, and revenue optimization. "
            "Build dashboards, reporting, and analytical tooling."
        ),
        "requirements": [
            "3+ years of experience as a data scientist, applied scientist, economist, or related field.",
            "Proficiency in SQL.",
            "Proficiency with Python or R.",
            "Strong foundation in experimentation and causal inference.",
            "Strong communication skills across technical and non-technical stakeholders.",
            "Comfort building dashboards and recurring reporting.",
        ],
        "responsibilities": [],
        "skills": [],
    }

    plan = build_tailoring_plan(LLMClient(api_key=""), job_fields, candidate, {})

    assert plan["role_track"] == "data_scientist"
    assert 60 <= plan["fit_score"] <= 72
    assert "Role asks for 5+ years" not in " ".join(plan["fit_reasons"])
    assert "Profile exceeds the stated 3+ year experience threshold." in plan["fit_reasons"]
    assert "Causal Inference" in plan["missing_keywords"]


def test_pasted_data_scientist_text_scores_higher_than_hardware_role() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    booz_job = {
        "title": "Data Scientist",
        "company": "Booz Allen Hamilton",
        "job_text": (
            "Data Scientist with 1+ years of experience with data exploration, data cleaning, data analysis, "
            "data visualization, or data mining. Knowledge of Machine Learning, Artificial Intelligence, or "
            "Natural Language Processing. Ability to develop predictive data models and deploy text mining or "
            "machine learning techniques. Nice to have ETL pipelines leveraging Python, Databricks or Palantir "
            "Foundry, Tableau or Qlik, GIS software including QGIS or ArcGIS. Master's degree."
        ),
        "requirements": [],
        "responsibilities": [],
        "skills": [],
        "summary": "",
    }
    amd_job = {
        "title": "SOC Silicon Design Engineer in Austin, Texas",
        "company": "Advanced Micro Devices, Inc",
        "job_text": (
            "Develop and design custom silicon. Solid understanding of SoC construction including fabric "
            "connectivity, memory systems, power delivery, clock distribution, floor planning, and packaging. "
            "Experience with EDA tools, VLSI design flow and CMOS technology. Proficiency in Perl, TCL, Python."
        ),
        "requirements": [],
        "responsibilities": [],
        "skills": [],
        "summary": "",
    }

    booz_plan = build_tailoring_plan(LLMClient(api_key=""), booz_job, candidate, {})
    amd_plan = build_tailoring_plan(LLMClient(api_key=""), amd_job, candidate, {})

    assert booz_plan["role_track"] == "data_scientist"
    assert booz_plan["fit_score"] >= 75
    assert booz_plan["keyword_coverage_pct"] > 0
    assert "Machine Learning" in booz_plan["matched_keywords"]
    assert amd_plan["role_track"] == "hardware_engineer"
    assert amd_plan["fit_score"] <= 50
    assert booz_plan["fit_score"] - amd_plan["fit_score"] >= 25


def test_clean_role_for_filename_removes_location_noise() -> None:
    assert clean_role_for_filename("Data Scientist job in Atlanta, Georgia, 30328") == "Data Scientist"
    assert clean_role_for_filename("Data Scientist I in Chantilly, Virginia") == "Data Scientist I"


def test_infrastructure_software_engineer_role_uses_software_track() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    job_fields = {
        "title": "Software Engineer - Infrastructure",
        "company": "Baseten",
        "job_text": (
            "Develop infrastructure components for our ML inference platform using Python and Go. "
            "Implement Kubernetes deployments for model serving, build monitoring systems, "
            "support infrastructure automation, and contribute to inference orchestration."
        ),
        "requirements": [
            "Proficient coding abilities in one or more popular programming or scripting languages.",
            "Working knowledge of Kubernetes and containerization.",
            "Basic understanding of machine learning concepts and model serving.",
            "Familiarity with distributed systems concepts.",
        ],
        "responsibilities": [
            "Develop infrastructure components for ML inference.",
            "Build and enhance monitoring systems.",
            "Support infrastructure automation.",
        ],
    }

    plan = build_tailoring_plan(LLMClient(api_key=""), job_fields, candidate, {})

    assert plan["role_track"] == "software_engineer"
    assert "proj_7" in plan["suggested_project_ids"] or "proj_9" in plan["suggested_project_ids"]


def test_infrastructure_software_engineer_resume_summary_targets_software() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    job_fields = {
        "title": "Software Engineer - Infrastructure",
        "company": "Baseten",
        "job_text": "Build ML inference infrastructure using Python, Kubernetes, monitoring, APIs, and cloud automation.",
    }

    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        job_fields,
        [],
        ["exp_0_b1", "exp_0_b2", "exp_2_b2"],
        {},
        {},
        ["Python", "AWS", "CloudFormation", "REST APIs"],
    )

    assert "SUMMARY\nSoftware Engineer with 4+ years of experience" in text
    assert "Hands-on expertise in Python, Java, REST APIs, FastAPI, AWS, CloudFormation" in text
    assert "Data Engineer with 4+ years" not in text


def test_generated_resume_fit_score_penalizes_unsolved_required_gaps() -> None:
    job_fields = {
        "title": "Software Engineer - Infrastructure",
        "requirements": [
            "Develop infrastructure using Python and Go.",
            "Working knowledge of Kubernetes and containerization.",
            "Experience with monitoring and distributed systems.",
        ],
    }
    resume_text = (
        "SUMMARY\nSoftware Engineer with Python, Java, REST APIs, AWS, CloudFormation, "
        "Machine Learning, and monitoring experience.\n"
    )

    score = _generated_resume_fit_score(
        job_fields,
        resume_text,
        ["Python", "Go", "Kubernetes", "Monitoring", "Distributed Systems"],
    )

    assert score < 80
    assert score > 30


def test_ai_engineer_with_successfactors_reference_is_not_classified_as_sap() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    job_fields = {
        "title": "AI Engineer Consultant",
        "company": "Deloitte US",
        "job_text": (
            "Build production GenAI services using Claude, GPT, Codex, and Gemini. Implement LLM applications, "
            "tool calling, RAG, document ingestion, embeddings, vector and hybrid search, retrieval evaluation, "
            "real-time inference APIs, Docker, Kubernetes, observability, IAM, encryption, and audit logging. "
            "Partner across product, data science, data engineering, platform, and security. Human Capital "
            "platform experience such as Workday, SAP SuccessFactors, or Oracle HCM is preferred."
        ),
        "requirements": [],
        "responsibilities": [],
        "skills": [],
        "suggested_bullets": [],
        "suggested_project_ids": ["proj_5", "proj_6"],
    }

    assert detect_role_track(job_fields) == "genai_engineer"
    assert detect_sector(job_fields) == "ai_product"

    cover_letter = render_cover_letter_text(
        server_dir / "data/templates",
        LLMClient(api_key=""),
        candidate,
        job_fields,
        {},
    )

    assert "LLM applications" in cover_letter
    assert "RAG pipelines" in cover_letter
    assert "My standout project" in cover_letter
    assert "AgentOps Copilot" in cover_letter
    assert "RAGProbe" in cover_letter
    assert "Financial Portfolio Prediction" not in cover_letter
    assert "Pneumonia Detection" not in cover_letter
    assert "In my professional work" in cover_letter
    assert "AWS Certified AI Practitioner" in cover_letter
    assert candidate["identity"]["phone"] in cover_letter
    assert candidate["identity"]["email"] in cover_letter
    assert "SAP " not in cover_letter
    assert "SAP BTP" not in cover_letter
    assert "SAP CPI environments" not in cover_letter


def test_sap_cover_letter_uses_approved_template_facts_and_target_company() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    job_fields = {
        "title": "SAP BTP Integration Consultant",
        "company": "Example Systems",
        "job_text": "Lead SAP CPI and PI/PO migrations, S/4HANA integrations, monitoring, and OAuth delivery.",
    }

    cover_letter = render_cover_letter_text(
        server_dir / "data/templates",
        LLMClient(api_key=""),
        candidate,
        job_fields,
        {},
    )

    assert "Example Systems's SAP BTP Integration Consultant role is compelling" in cover_letter
    assert "Puma account" in cover_letter
    assert "reduce processing time by 30%" in cover_letter
    assert "BHP account" in cover_letter
    assert "50+ ERP interfaces" in cover_letter
    assert "Principal Propagation and OAuth 2.0" in cover_letter
    assert "SAP Certified Development Associate - Integration Suite" in cover_letter
    assert "SAP Blackbelt Integration Suite" in cover_letter
    assert "[Company Name]" not in cover_letter
    assert "FinBERT" not in cover_letter
    assert "Pneumonia" not in cover_letter
    assert "Sign Language" not in cover_letter
    assert candidate["identity"]["phone"] in cover_letter
    assert candidate["identity"]["email"] in cover_letter


def test_sap_cover_letter_without_specialized_facts_never_selects_data_science_projects() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    candidate.pop("cover_letter_facts", None)

    cover_letter = render_cover_letter_text(
        server_dir / "data/templates",
        LLMClient(api_key=""),
        candidate,
        {
            "title": "SAP CPI Consultant",
            "company": "Example Systems",
            "job_text": "SAP CPI, PI/PO, BTP Integration Suite, S/4HANA, and production monitoring.",
        },
        {},
    )

    assert "SAP IntelliOps" in cover_letter
    assert "FinBERT" not in cover_letter
    assert "Pneumonia" not in cover_letter
    assert "Sign Language" not in cover_letter


def test_cover_letter_uses_bay_area_location_without_stale_nj_claims() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())

    cover_letter = render_cover_letter_text(
        server_dir / "data/templates",
        LLMClient(api_key=""),
        candidate,
        {
            "title": "AI Engineer",
            "company": "Bay AI Labs",
            "location": "San Francisco, CA",
            "job_text": "Build production LLM agents, RAG workflows, and retrieval evaluation services.",
        },
        {},
    )

    contact_line = cover_letter.splitlines()[1]
    assert "San Francisco Bay Area" in contact_line
    assert "Already based in the San Francisco Bay Area" in cover_letter
    assert "Jersey City" not in cover_letter
    assert "currently live in New Jersey" not in cover_letter
    assert "currently based in New York" not in cover_letter


def test_remote_cover_letter_uses_antioch_and_does_not_invent_relocation() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())

    cover_letter = render_cover_letter_text(
        server_dir / "data/templates",
        LLMClient(api_key=""),
        candidate,
        {
            "title": "Data Engineer",
            "company": "Remote Data Co",
            "location": "Remote",
            "job_text": "Build cloud data pipelines, APIs, ETL workflows, and reliable analytics systems.",
        },
        {},
    )

    assert "Antioch, CA" in cover_letter.splitlines()[1]
    assert "comfortable collaborating with distributed teams" in cover_letter
    assert "relocat" not in cover_letter.lower()
    assert "New Jersey" not in cover_letter
    assert "New York" not in cover_letter


def test_cover_letter_mentions_at_most_two_profile_projects() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    cover_letter = render_cover_letter_text(
        server_dir / "data/templates",
        LLMClient(api_key=""),
        candidate,
        {
            "title": "Applied AI Engineer",
            "company": "Example AI",
            "job_text": "Build AI agents, developer tooling, RAG, LLM evaluation, AWS Bedrock, and production APIs.",
        },
        {},
    )
    project_names = [
        str(project.get("name", ""))
        for project in candidate["academic_projects"]
        if str(project.get("name", "")) and str(project.get("name", "")) in cover_letter
    ]

    assert len(project_names) <= 2
    assert {"SAP IntelliOps", "AgentOps Copilot", "RAGProbe", "AWS Autonomous Agent"}.intersection(project_names)


def test_cover_letter_selects_fintech_project_from_actual_requirements() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())

    cover_letter = render_cover_letter_text(
        server_dir / "data/templates",
        LLMClient(api_key=""),
        candidate,
        {
            "title": "Machine Learning Engineer",
            "company": "Fintech Example",
            "job_text": "Build NLP, forecasting, financial portfolio analytics, enterprise workflow integration, and model evaluation for fintech products.",
        },
        {},
    )

    assert "Financial Portfolio Prediction" in cover_letter
    assert "F1-score of 0.82" in cover_letter
    assert "SAP IntelliOps" in cover_letter
    assert "Pneumonia Detection" not in cover_letter


def test_resume_technical_skills_do_not_inject_unknown_keywords() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        {
            "title": "Data Engineer",
            "company": "Example",
            "job_text": "Python SQL Spark Databricks",
        },
        [],
        [],
        {},
        {},
        ["Python", "SQL", "Spark", "Databricks", "We", "are", "looking", "talented"],
    )

    technical_skills = text.split("TECHNICAL SKILLS", 1)[1].split("PROFESSIONAL EXPERIENCE", 1)[0]
    assert "We, are, looking" not in technical_skills
    assert "talented" not in technical_skills
    assert "Cloud & DevOps:" in technical_skills
    assert "Spark" in technical_skills
    assert "Databricks" in technical_skills


def test_resume_promotes_profile_supported_required_java_and_mysql() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        {
            "title": "Data Engineer",
            "company": "Ancestry",
            "job_text": "Required experience in Java, MySQL, Spark, AWS, and REST APIs.",
        },
        [],
        [],
        {},
        {},
        ["Java", "MySQL", "Spark", "AWS", "REST APIs"],
    )

    technical_skills = text.split("TECHNICAL SKILLS", 1)[1].split("PROFESSIONAL EXPERIENCE", 1)[0]
    assert "Languages & Backend:" in technical_skills
    assert "Java" in technical_skills
    assert "MySQL" in technical_skills
    assert "Spark" in technical_skills
    assert "AWS" in technical_skills
    assert "REST APIs" in technical_skills


def test_resume_projects_prefer_curated_bullets_over_rewrites() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        {
            "title": "Machine Learning Engineer",
            "company": "Example",
            "job_text": "LLM workflows resume intelligence ATS optimization",
        },
        [],
        ["proj_9"],
        {},
        {"proj_9": "Built AI Resume Intelligence Platform, a Chrome extension workflow that analyzes job postings and tailors resumes."},
        ["LLM workflows", "ATS optimization"],
    )

    projects = text.split("PROJECTS", 1)[1].split("CERTIFICATIONS", 1)[0]
    assert "Built AI Resume Intelligence Platform, a Chrome extension workflow" not in projects
    assert "Built an agentic AI platform using FastAPI, Next.js, SQLite" in projects
    assert "Developed semantic-search and ATS optimization workflows" in projects


def test_resume_repairs_project_bullet_fragments_from_profile_form() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    candidate["academic_projects"][0]["bullets"] = [
        "Built a FinBERT + PySpark pipeline to process noisy",
        "large-scale financial news and convert sentiment into structured Buy/Hold/Sell signals for downstream analysis.",
        "Improved signal quality and consistency by tuning classification logic and feature flow",
        "achieving a best model F1-score of 0.82.",
    ]

    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        {"title": "Data Scientist", "company": "Deloitte"},
        [],
        ["proj_1"],
        {},
        {},
        ["Python", "Machine Learning"],
    )

    projects = text.split("PROJECTS", 1)[1].split("CERTIFICATIONS", 1)[0]
    assert "- large-scale financial news" not in projects
    assert "- achieving a best model F1-score" not in projects
    assert (
        "Built a FinBERT + PySpark pipeline to process noisy, large-scale financial news and convert sentiment into structured Buy/Hold/Sell signals"
        in projects
    )


def test_resume_education_matches_reference_format_with_graduation_date() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())

    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        {"title": "Data Scientist", "company": "Example"},
        [],
        [],
        {},
        {},
        ["Python", "Machine Learning"],
    )

    education = text.split("EDUCATION", 1)[1]
    assert "M.S. Data Science | Sep 2024 - May 2026" in education
    assert "Stevens Institute of Technology | GPA 3.82 | Hoboken, NJ" in education
    assert "B.E. Electronics & Telecommunications | May 2016 - May 2020" in education
    assert "University of Mumbai | Mumbai, India" in education


def test_resume_experience_location_is_right_aligned_text_line_and_role_is_clean() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())

    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        {"title": "Data Scientist", "company": "Example"},
        [],
        [],
        {},
        {},
        ["Python", "Machine Learning"],
    )

    experience = text.split("PROFESSIONAL EXPERIENCE", 1)[1].split("PROJECTS", 1)[0]
    assert "Research Assistant | Stevens Institute of Technology | Hoboken, NJ, USA | May 2025 - Sep 2025" in experience
    assert "Data Scientist | Accenture | Mumbai, India | Feb 2023 - Sep 2024" in experience
    assert "Data Scientist | LTI / LTIMindtree | Mumbai, India | Sep 2020 - Feb 2023" in experience


@pytest.mark.parametrize(
    ("job_title", "expected_target_title"),
    [
        ("AI and Automation Engineer (Business Analysis, Senior Analyst)", "AI Engineer"),
        ("Intern, AI Engineering", "AI Engineer"),
        ("AI/ML Engineer", "Machine Learning Engineer"),
        ("Data Scientist", "Data Scientist"),
        ("Business Analyst", "Business Analyst"),
        ("Data Engineer", "Data Engineer"),
        ("Data Analyst", "Data Analyst"),
        ("Software Engineer", "Software Engineer"),
        ("Quantitative Finance Analyst", "Quantitative Analyst"),
    ],
)
def test_resume_changes_only_accenture_and_lti_titles_to_clean_target_role(
    job_title: str,
    expected_target_title: str,
) -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())

    text = render_resume_text(
        server_dir / "data/templates",
        candidate,
        {"title": job_title, "company": "Example", "job_text": job_title},
        [],
        [],
        {},
        {},
        ["Python", "SQL"],
    )

    experience = text.split("PROFESSIONAL EXPERIENCE", 1)[1].split("PROJECTS", 1)[0]
    assert f"{expected_target_title} | Accenture | Mumbai, India | Feb 2023 - Sep 2024" in experience
    assert f"{expected_target_title} | LTI / LTIMindtree | Mumbai, India | Sep 2020 - Feb 2023" in experience
    assert "Research Assistant | Stevens Institute of Technology | Hoboken, NJ, USA | May 2025 - Sep 2025" in experience
    assert "Research Assistant -" not in experience


def test_ragprobe_is_selected_for_rag_evaluation_and_security_roles() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    candidate = yaml.safe_load((server_dir / "data/candidate_profile.yaml").read_text())
    job = {
        "title": "RAG Evaluation Engineer",
        "company": "Example",
        "job_text": (
            "Build FAISS vector search and retrieval-augmented generation evaluation pipelines. "
            "Benchmark hallucination, faithfulness, context recall, prompt injection, and AI security "
            "using LLM-as-a-Judge methodologies."
        ),
    }

    plan = build_tailoring_plan(LLMClient(api_key=""), job, candidate, {})

    assert "proj_6" in plan["suggested_project_ids"]
