from __future__ import annotations

import re
from typing import Any

from .llm import CANDIDATE_BULLET_REWRITE_PROMPT, LLMClient, PROJECT_REWRITE_PROMPT, TAILORING_PLAN_PROMPT


def _profile_skill_set(candidate_profile: dict[str, Any]) -> set[str]:
    skills = candidate_profile.get("skills", [])
    out = set()
    for item in skills:
        if isinstance(item, str):
            out.add(item.lower())
    return out


def _base_answers(candidate_profile: dict[str, Any], preferences: dict[str, Any]) -> dict[str, str]:
    preferred_locations = preferences.get("preferred_locations")
    preferred_location = "Please confirm manually."
    if isinstance(preferred_locations, list) and preferred_locations:
        preferred_location = str(preferred_locations[0]).strip() or preferred_location
    elif isinstance(preferred_locations, str) and preferred_locations.strip():
        preferred_location = preferred_locations.strip()

    return {
        "work_authorization": preferences.get("work_authorization") or "Please confirm manually.",
        "sponsorship_required": str(preferences.get("sponsorship_required", "unknown")),
        "preferred_location": preferred_location,
        "linkedin": candidate_profile.get("links", {}).get("linkedin", ""),
        "github": candidate_profile.get("links", {}).get("github", ""),
    }


ROLE_KEYWORDS: dict[str, list[str]] = {
    "software_engineer": [
        "software engineer",
        "software developer",
        "backend",
        "infrastructure",
        "distributed systems",
        "kubernetes",
        "containerization",
        "monitoring",
        "logging",
        "deployment",
        "python",
        "go",
        "api",
    ],
    "data_analyst": ["dashboard", "reporting", "bi", "power bi", "tableau", "sql", "analytics", "kpi"],
    "data_engineer": ["etl", "pipeline", "airflow", "spark", "databricks", "warehouse", "ingestion", "orchestration"],
    "data_scientist": ["machine learning", "model", "forecast", "classification", "regression", "nlp", "llm", "feature engineering"],
    "genai_engineer": ["generative ai", "genai", "llm", "rag", "retrieval", "embeddings", "vector search", "tool calling", "agentic ai", "mcp", "bedrock"],
    "hardware_engineer": ["soc", "silicon", "vlsi", "eda", "cmos", "micro-architecture", "floor planning", "clock distribution"],
    "sap_consultant": ["sap", "cpi", "s/4hana", "btp", "integration suite", "odata", "idoc", "erp"],
    "business_analyst": ["business analyst", "requirements", "process", "stakeholder", "documentation", "kpi", "analysis"],
    "market_analyst": ["market", "competitive", "forecast", "trends", "segmentation", "research", "insights"],
}

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "healthcare": ["hospital", "healthcare", "clinical", "patient", "medical", "pharma", "ehr", "pneumonia"],
    "finance": ["finance", "financial", "bank", "banking", "investment", "trading", "portfolio", "risk", "fintech"],
    "sap": ["sap", "cpi", "s/4hana", "integration suite", "btp", "erp", "idata", "odata"],
    "ai_product": [
        "assistant",
        "copilot",
        "chrome extension",
        "extension",
        "fastapi",
        "next.js",
        "web app",
        "user experience",
    ],
}

SECTOR_PROJECT_BOOST: dict[str, list[str]] = {
    "healthcare": ["proj_2"],
    "finance": ["proj_1", "proj_4"],
    "sap": ["proj_4"],
    "ai_product": ["proj_5", "proj_6", "proj_7", "proj_9"],
}

ATS_TERM_ALIASES: list[tuple[str, str]] = [
    ("retrieval-augmented generation", "Retrieval-Augmented Generation (RAG)"),
    ("tool calling", "Tool Calling"),
    ("function calling", "Tool Calling"),
    ("model context protocol", "Model Context Protocol (MCP)"),
    ("mcp", "Model Context Protocol (MCP)"),
    ("agentic ai", "Agentic AI"),
    ("autonomous agent", "Autonomous Agents"),
    ("autonomous agents", "Autonomous Agents"),
    ("recommendation systems", "Recommendation Systems"),
    ("recommendation system", "Recommendation Systems"),
    ("causal inference methods", "Causal Inference"),
    ("causal inference", "Causal Inference"),
    ("quasi-experimental methods", "Quasi-Experimental Methods"),
    ("quasi experimental methods", "Quasi-Experimental Methods"),
    ("a/b experiments", "A/B Testing"),
    ("a/b experiment", "A/B Testing"),
    ("a/b test design", "A/B Testing"),
    ("statistical analysis", "Statistical Analysis"),
    ("predictive modeling", "Predictive Modeling"),
    ("time-series forecasting", "Time-Series Forecasting"),
    ("time series forecasting", "Time-Series Forecasting"),
    ("feature engineering", "Feature Engineering"),
    ("data visualization", "Data Visualization"),
    ("data storytelling", "Data Storytelling"),
    ("requirements gathering", "Requirements Gathering"),
    ("stakeholder management", "Stakeholder Management"),
    ("machine learning", "Machine Learning"),
    ("deep learning", "Deep Learning"),
    ("artificial intelligence", "Artificial Intelligence"),
    ("data exploration", "Data Exploration"),
    ("data cleaning", "Data Cleaning"),
    ("data analysis", "Data Analysis"),
    ("data mining", "Data Mining"),
    ("generative ai", "Generative AI"),
    ("data quality", "Data Quality"),
    ("cloud data platforms", "Cloud Data Platforms"),
    ("cloud data platform", "Cloud Data Platforms"),
    ("data pipelines", "Data Pipelines"),
    ("data pipeline", "Data Pipelines"),
    ("etl pipelines", "ETL Pipelines"),
    ("etl pipeline", "ETL Pipelines"),
    ("sap s/4hana", "SAP S/4HANA"),
    ("sap cpi", "SAP CPI"),
    ("power bi", "Power BI"),
    ("rest apis", "REST APIs"),
    ("rest api", "REST APIs"),
    ("a/b testing", "A/B Testing"),
    ("hypothesis testing", "Hypothesis Testing"),
    ("regression", "Regression"),
    ("classification", "Classification"),
    ("clustering", "Clustering"),
    ("forecasting", "Forecasting"),
    ("experimentation", "Experimentation"),
    ("analytics", "Analytics"),
    ("reporting", "Reporting"),
    ("dashboards", "Dashboards"),
    ("dashboard", "Dashboards"),
    ("python", "Python"),
    ("pandas", "Pandas"),
    ("numpy", "NumPy"),
    ("pyspark", "PySpark"),
    ("spark", "Spark"),
    ("hadoop", "Hadoop"),
    ("sql", "SQL"),
    ("mysql", "MySQL"),
    ("java", "Java"),
    (" r ", "R"),
    ("databricks", "Databricks"),
    ("palantir foundry", "Palantir Foundry"),
    ("foundry", "Palantir Foundry"),
    ("airflow", "Airflow"),
    ("mlflow", "MLflow"),
    ("docker", "Docker"),
    ("kubernetes", "Kubernetes"),
    ("snowflake", "Snowflake"),
    ("tableau", "Tableau"),
    ("qlik", "Qlik"),
    ("gis", "GIS"),
    ("qgis", "QGIS"),
    ("arcgis", "ArcGIS"),
    ("excel", "Excel"),
    ("aws", "AWS"),
    ("aws cdk", "AWS CDK"),
    ("lambda", "AWS Lambda"),
    ("aws lambda", "AWS Lambda"),
    ("api gateway", "Amazon API Gateway"),
    ("dynamodb", "Amazon DynamoDB"),
    ("bedrock", "Amazon Bedrock"),
    ("amazon bedrock", "Amazon Bedrock"),
    ("gcp", "GCP"),
    ("google cloud", "GCP"),
    ("azure", "Azure"),
    ("azure ml", "Azure ML"),
    ("tensorflow", "TensorFlow"),
    ("pytorch", "PyTorch"),
    ("llm", "LLMs"),
    ("iot", "IoT"),
    ("text mining", "Text Mining"),
    ("rag", "Retrieval-Augmented Generation (RAG)"),
    ("soc", "SoC"),
    ("silicon", "Silicon Design"),
    ("vlsi", "VLSI"),
    ("eda tools", "EDA Tools"),
    ("eda", "EDA Tools"),
    ("cmos", "CMOS"),
    ("perl", "Perl"),
    ("tcl", "TCL"),
    ("micro-architecture", "Micro-architecture"),
    ("microarchitecture", "Micro-architecture"),
    ("floor planning", "Floor Planning"),
    ("clock distribution", "Clock Distribution"),
    ("power delivery", "Power Delivery"),
    ("memory systems", "Memory Systems"),
    ("btp", "SAP BTP"),
    ("s/4hana", "SAP S/4HANA"),
    ("cpi", "SAP CPI"),
]

ATS_NOISE_WORDS = {
    "a",
    "an",
    "are",
    "for",
    "individuals",
    "join",
    "looking",
    "our",
    "talented",
    "the",
    "to",
    "us",
    "we",
    "you",
    "your",
}

TOKEN_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "has",
    "have",
    "into",
    "our",
    "such",
    "that",
    "the",
    "their",
    "this",
    "through",
    "with",
    "work",
    "you",
    "your",
}

KEYWORD_PROFILE_ALIASES: dict[str, list[str]] = {
    "Artificial Intelligence": ["artificial intelligence", " ai ", "ai practitioner", "applied machine learning"],
    "Data Exploration": ["exploratory data analysis", "eda"],
    "Data Mining": ["exploratory data analysis", "data cleaning", "preprocessing"],
    "Cloud Data Platforms": ["cloud platforms", "aws", "gcp", "azure", "databricks", "snowflake"],
    "Dashboard creation": ["dashboard", "dashboards", "power bi", "tableau", "plotly dash", "streamlit"],
    "Dashboards": ["dashboard", "dashboards", "power bi", "tableau", "plotly dash", "streamlit"],
    "Reporting": ["reporting", "reports", "power bi", "tableau", "stakeholder-ready reporting"],
    "Experimentation": ["experimentation", "experiment", "experiments", "model evaluation", "benchmarking", "a/b testing"],
    "A/B Testing": ["a/b testing", "experiment", "experiments", "experimentation"],
    "Classification": ["classification", "classifier", "cnn", "mobilenet", "random forest", "logistic regression"],
    "Segmentation": ["segmentation", "clustering", "classification"],
    "Revenue optimization": ["portfolio analysis", "forecasting", "business impact", "optimization"],
    "Pricing": ["portfolio analysis", "forecasting", "business impact"],
    "Text Mining": ["natural language processing", "nlp", "finbert"],
    "Statistical Analysis": ["statistical analysis", "hypothesis testing", "anova", "regression", "forecasting", "model evaluation", "f1-score"],
}


def _job_corpus(job_fields: dict[str, Any]) -> str:
    parts: list[str] = [
        str(job_fields.get("title", "")),
        str(job_fields.get("company", "")),
        str(job_fields.get("summary", "")),
        str(job_fields.get("job_text", "")),
        str(job_fields.get("description", "")),
    ]
    parts.extend([str(x) for x in job_fields.get("requirements", [])])
    parts.extend([str(x) for x in job_fields.get("responsibilities", [])])
    parts.extend([str(x) for x in job_fields.get("skills", [])])
    return " ".join(parts).lower()


def _candidate_corpus(candidate_profile: dict[str, Any]) -> str:
    parts: list[str] = [str(candidate_profile.get("summary", ""))]
    parts.extend(str(skill) for skill in candidate_profile.get("skills", []))
    for exp in candidate_profile.get("experience", []):
        parts.extend([str(exp.get("role", "")), str(exp.get("company", ""))])
        parts.extend(str(b.get("text", "")) for b in exp.get("bullets", []) if isinstance(b, dict))
    for edu in candidate_profile.get("education", []):
        parts.extend([str(edu.get("degree", "")), str(edu.get("field", "")), str(edu.get("school", ""))])
    for project in candidate_profile.get("academic_projects", []):
        parts.extend([str(project.get("name", "")), str(project.get("description", ""))])
        parts.extend(str(bullet) for bullet in project.get("bullets", []) if isinstance(bullet, str))
    for group in candidate_profile.get("technical_skills", []):
        if isinstance(group, dict):
            parts.extend(str(item) for item in group.get("items", []))
    return " ".join(parts).lower()


def _has_any(corpus: str, terms: list[str]) -> bool:
    return any(term in corpus for term in terms)


def _filter_inaccurate_fit_reasons(reasons: list[str], job_fields: dict[str, Any]) -> list[str]:
    job_corpus = _job_corpus(job_fields)
    filtered: list[str] = []
    has_five_year_requirement = bool(re.search(r"(?<![\d.])5\s*\+?\s*years?\b|\bfive\s+years?\b", job_corpus))
    for reason in reasons:
        text = str(reason).strip()
        if not text:
            continue
        if not has_five_year_requirement and re.search(r"(?<![\d.])5\s*\+?\s*years?\b|\bfive\s+years?\b", text.lower()):
            continue
        filtered.append(text)
    return filtered


def detect_sector(job_fields: dict[str, Any]) -> str:
    corpus = _job_corpus(job_fields)
    title = str(job_fields.get("title", "")).lower()
    if re.search(r"\b(ai|artificial intelligence|genai|generative ai|llm)\b", title) and re.search(
        r"\b(engineer|developer|architect|consultant)\b", title
    ):
        return "ai_product"
    best = "generic"
    best_score = 0
    for sector, words in SECTOR_KEYWORDS.items():
        score = sum(1 for w in words if w in corpus)
        if score > best_score:
            best = sector
            best_score = score
    return best


def _deterministic_fit_score(
    job_fields: dict[str, Any],
    candidate_profile: dict[str, Any],
    role_track: str,
    ats_keywords: list[str],
) -> tuple[int, list[str]]:
    job_corpus = _job_corpus(job_fields)
    candidate_corpus = _candidate_corpus(candidate_profile)
    coverage = keyword_coverage(candidate_profile, ats_keywords)
    matched = set(coverage["matched_keywords"])
    missing = set(coverage["missing_keywords"])

    score = 20
    reasons: list[str] = []
    score += round((coverage["keyword_coverage_pct"] / 100) * 45)
    if matched:
        reasons.append(f"Matched profile keywords: {', '.join(list(matched)[:8])}.")

    if role_track == "software_engineer" and _has_any(
        candidate_corpus,
        ["software engineer", "python", "java", "node.js", "fastapi", "next.js", "api", "aws", "lambda", "cloudformation", "ci/cd"],
    ):
        score += 15
        reasons.append("Profile contains software engineering, backend, and cloud deployment evidence.")
    elif role_track == "data_scientist" and _has_any(
        candidate_corpus,
        ["machine learning", "data science", "model", "forecast", "classification", "regression", "nlp", "tensorflow", "pytorch"],
    ):
        score += 15
        reasons.append("Profile contains strong data science and machine learning evidence.")
        if _has_any(job_corpus, ["experiment", "pricing", "segmentation", "revenue", "dashboard", "reporting", "stakeholder"]) and _has_any(
            candidate_corpus,
            ["forecast", "model evaluation", "f1-score", "dashboard", "power bi", "stakeholder", "business", "analytics", "classification"],
        ):
            score += 8
            reasons.append("Profile has transferable product analytics evidence across modeling, reporting, and stakeholder-facing analysis.")
    elif role_track == "data_engineer" and _has_any(candidate_corpus, ["pipeline", "etl", "spark", "databricks", "data quality"]):
        score += 15
        reasons.append("Profile contains strong data engineering evidence.")
    elif role_track == "data_analyst" and _has_any(candidate_corpus, ["analytics", "dashboard", "reporting", "power bi", "tableau", "sql"]):
        score += 15
        reasons.append("Profile contains strong analytics and reporting evidence.")
    elif role_track == "hardware_engineer":
        if _has_any(candidate_corpus, ["electronics", "electrical", "computer engineering", "c++"]):
            score += 6
            reasons.append("Education has some engineering overlap, but core silicon/SoC evidence is limited.")
        if not _has_any(candidate_corpus, ["soc", "silicon", "vlsi", "eda", "cmos", "micro-architecture", "floor planning"]):
            score -= 18
            reasons.append("Role is hardware/SoC focused; profile does not show core silicon design, EDA, VLSI, or CMOS experience.")

    if _has_any(candidate_corpus, ["master of science", "data science", "computer science", "bachelor"]):
        score += 6
        reasons.append("Education aligns with the role requirements.")

    if _has_any(job_corpus, ["stakeholder", "communicate", "presentation", "client", "consultant"]) and _has_any(
        candidate_corpus,
        ["stakeholder", "communication", "business", "partnered", "presentation", "client"],
    ):
        score += 6
        reasons.append("Profile supports stakeholder communication and business-facing delivery.")

    if _has_any(job_corpus, ["5+ years", "5 years", "five years"]) and not _has_any(candidate_corpus, ["5+ years", "5 years", "five years"]):
        score -= 8
        reasons.append("Role asks for 5+ years; profile currently states 4+ years, so review seniority fit manually.")
    elif role_track in {"software_engineer", "data_scientist", "data_analyst", "data_engineer", "genai_engineer"}:
        if _has_any(job_corpus, ["4+ years", "4 years", "four years"]):
            score += 5
            reasons.append("Profile meets the stated 4+ year experience threshold.")
        elif _has_any(job_corpus, ["3+ years", "3 years", "three years"]):
            score += 6
            reasons.append("Profile exceeds the stated 3+ year experience threshold.")
        elif _has_any(job_corpus, ["2+ years", "2 years", "two years"]):
            score += 6
            reasons.append("Profile exceeds the stated 2+ year experience threshold.")
        elif _has_any(job_corpus, ["1+ years", "1 years", "one year"]):
            score += 5
            reasons.append("Profile exceeds the stated 1+ year experience threshold.")

    if missing:
        reasons.append(f"Potential gaps to address: {', '.join(list(missing)[:6])}.")

    if role_track == "data_scientist" and _has_any(job_corpus, ["causal inference", "quasi-experimental", "quasi experimental"]) and not _has_any(
        candidate_corpus,
        ["causal inference", "quasi-experimental", "quasi experimental", "a/b testing", "ab testing"],
    ):
        score = min(score, 72)

    return max(0, min(100, score)), reasons[:8]


def detect_role_track(job_fields: dict[str, Any]) -> str:
    corpus = _job_corpus(job_fields)
    title = str(job_fields.get("title", "")).lower()
    if "sap" in title:
        return "sap_consultant"
    if re.search(r"\b(software engineer|software developer|backend engineer|infrastructure engineer)\b", title):
        return "software_engineer"
    if re.search(r"\b(soc|silicon|vlsi|eda|cmos|asic|fpga|micro-?architecture)\b", title):
        return "hardware_engineer"
    if "business analyst" in title:
        return "business_analyst"
    if "market analyst" in title:
        return "market_analyst"
    if re.search(r"\b(ai|artificial intelligence|genai|generative ai|llm)\b", title) and re.search(
        r"\b(engineer|engineering|developer|architect|consultant)\b", title
    ):
        return "genai_engineer"
    if re.search(r"\b(ml|machine learning)\b", title) and re.search(r"\b(engineer|engineering|developer)\b", title):
        return "genai_engineer"
    if "data scientist" in title or re.search(r"\bml\b|\bmachine learning\b", title):
        return "data_scientist"
    if "data engineer" in title or "analytics engineer" in title:
        return "data_engineer"
    if "data analyst" in title or "business analyst" in title:
        return "data_analyst"
    best = "data_analyst"
    best_score = -1
    for role, words in ROLE_KEYWORDS.items():
        score = sum(1 for w in words if w in corpus)
        if role == "sap_consultant" and detect_sector(job_fields) == "sap":
            score += 2
        if score > best_score:
            best = role
            best_score = score
    return best


def _token_set(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9+#./-]{3,}", text.lower())
        if t not in TOKEN_STOPWORDS
    }


def _bullet_word_count(text: str) -> int:
    return len(re.findall(r"\b[\w%+/.-]+\b", str(text or "")))


def _bullet_quality_score(text: str) -> int:
    raw = str(text or "")
    low = raw.lower()
    score = 0
    if re.search(r"\b\d", raw):
        score += 2
    if any(token in low for token in ["reduced", "improved", "increased", "enabled", "automated", "designed", "built", "led", "developed", "refactored", "implemented", "engineered"]):
        score += 2
    if any(token in low for token in ["stakeholder", "cross-functional", "pipeline", "dashboard", "integration", "forecast", "model", "analytics", "data quality", "migration", "validation"]):
        score += 2
    if _bullet_word_count(raw) >= 18:
        score += 2
    return score


def _accept_rewritten_bullet(original_text: str, rewritten_text: str) -> bool:
    original = str(original_text or "").strip()
    rewritten = str(rewritten_text or "").strip()
    if not rewritten:
        return False
    if rewritten == original:
        return True
    original_words = _bullet_word_count(original)
    rewritten_words = _bullet_word_count(rewritten)
    if rewritten_words < max(14, int(original_words * 0.72)):
        return False
    if _bullet_quality_score(rewritten) < _bullet_quality_score(original):
        return False
    if re.search(r"\b(helped|worked on|responsible for|involved in)\b", rewritten.lower()) and not re.search(
        r"\b(helped|worked on|responsible for|involved in)\b", original.lower()
    ):
        return False
    if re.search(r"\b\d", original) and not re.search(r"\b\d", rewritten):
        return False
    return True


def rank_project_ids(
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    ats_keywords: list[str],
    sector: str,
    role_track: str = "",
) -> list[str]:
    projects = candidate_profile.get("academic_projects", [])
    if not isinstance(projects, list):
        return []
    jd_tokens = _token_set(_job_corpus(job_fields))
    keyword_tokens = _token_set(" ".join([str(x) for x in ats_keywords]))
    ranked: list[tuple[str, float]] = []
    boost_ids = set(SECTOR_PROJECT_BOOST.get(sector, []))
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        pid = str(proj.get("id", "")).strip()
        if not pid:
            continue
        blob = f"{proj.get('name', '')} {proj.get('description', '')} {' '.join(str(x) for x in proj.get('bullets', []) or [])}".lower()
        ptoks = _token_set(blob)
        overlap = len(ptoks.intersection(jd_tokens)) + len(ptoks.intersection(keyword_tokens))
        score = float(overlap)
        if pid in boost_ids:
            score += 25.0
        if sector == "sap" and "sap" in blob:
            score += 10.0
        if sector == "finance" and any(k in blob for k in ["finbert", "financial", "portfolio", "backtesting"]):
            score += 8.0
        if sector == "finance" and pid == "proj_4" and any(k in _job_corpus(job_fields) for k in ["enterprise", "integration", "workflow", "incident"]):
            score += 30.0
        if sector == "healthcare" and any(k in blob for k in ["health", "medical", "pneumonia", "rag"]):
            score += 8.0
        if sector == "ai_product" and any(
            k in blob for k in ["agentops", "autonomous-agent", "jobapply copilot", "chrome extension", "fastapi", "next.js", "workflow", "copilot", "developer tooling"]
        ):
            score += 8.0
        if pid == "proj_6" and any(
            k in _job_corpus(job_fields)
            for k in [
                "rag",
                "retrieval-augmented generation",
                "faiss",
                "vector search",
                "prompt injection",
                "llm evaluation",
                "llm-as-a-judge",
                "faithfulness",
                "hallucination",
                "ai safety",
                "ai security",
            ]
        ):
            score += 30.0
        if role_track == "data_scientist":
            if any(k in blob for k in ["classification", "regression", "clustering", "deep learning", "cnn", "mobilenet", "finbert", "pyspark", "arima", "sarima"]):
                score += 14.0
            if any(k in blob for k in ["machine learning", "model", "forecast", "predictive", "statistical", "time-series", "tensorflow", "pytorch"]):
                score += 10.0
            if any(k in blob for k in ["rag", "mcp", "agentic"]) and sector not in {"healthcare", "sap"} and "rag" not in _job_corpus(job_fields):
                score -= 10.0
            if "sap" in blob and sector != "sap":
                score -= 8.0
        if role_track == "data_engineer":
            if any(k in blob for k in ["pipeline", "etl", "observability", "spark", "databricks", "lambda", "dynamodb", "api gateway"]):
                score += 8.0
            if pid in {"proj_4", "proj_7"} and any(k in _job_corpus(job_fields) for k in ["aws", "cloud", "lambda", "api gateway", "dynamodb", "etl", "data pipeline", "integration"]):
                score += 18.0
        if role_track == "genai_engineer":
            if any(k in blob for k in ["llm", "rag", "retrieval", "vector", "agentic", "copilot", "prompt", "bedrock", "mcp", "tool calling"]):
                score += 16.0
            if pid in {"proj_4", "proj_5", "proj_6", "proj_7"}:
                score += 20.0
            if sector == "finance" and pid == "proj_1":
                score += 30.0
            if pid == "proj_5" and any(k in _job_corpus(job_fields) for k in ["developer tool", "observability", "agent infrastructure", "startup"]):
                score += 24.0
            if pid == "proj_7" and any(k in _job_corpus(job_fields) for k in ["aws", "lambda", "bedrock", "full-stack", "backend"]):
                score += 24.0
            if pid == "proj_4" and detect_sector(job_fields) == "finance" and any(k in _job_corpus(job_fields) for k in ["enterprise", "integration", "workflow", "incident"]):
                score += 18.0
            if "sap" in blob and detect_sector(job_fields) != "sap" and not any(k in _job_corpus(job_fields) for k in ["enterprise", "integration", "workflow"]):
                score -= 20.0
        if role_track == "software_engineer":
            if any(k in blob for k in ["fastapi", "next.js", "typescript", "lambda", "api gateway", "dynamodb", "aws cdk", "cloud-native", "backend"]):
                score += 16.0
            if pid in {"proj_5", "proj_7", "proj_9"}:
                score += 18.0
            if any(k in _job_corpus(job_fields) for k in ["ml inference", "model serving", "inference platform", "developer tooling"]):
                if any(k in blob for k in ["bedrock", "agent", "llm", "developer tooling", "observability", "cloud-native"]):
                    score += 12.0
        ranked.append((pid, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in ranked[:3]]


def rank_bullet_ids(
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    ats_keywords: list[str],
    role_track: str,
    sector: str,
) -> list[str]:
    jd_tokens = _token_set(_job_corpus(job_fields))
    role_tokens = _token_set(" ".join(ROLE_KEYWORDS.get(role_track, [])))
    sector_tokens = _token_set(" ".join(SECTOR_KEYWORDS.get(sector, [])))
    kw_tokens = _token_set(" ".join([str(k) for k in ats_keywords]))
    scored: list[tuple[str, float]] = []
    for exp in candidate_profile.get("experience", []):
        for bullet in exp.get("bullets", []):
            if not isinstance(bullet, dict):
                continue
            bid = str(bullet.get("id", "")).strip()
            if not bid:
                continue
            text = str(bullet.get("text", "")).lower()
            btoks = _token_set(text)
            score = 0.0
            score += 1.6 * len(btoks.intersection(jd_tokens))
            score += 1.2 * len(btoks.intersection(kw_tokens))
            score += 1.1 * len(btoks.intersection(role_tokens))
            score += 0.8 * len(btoks.intersection(sector_tokens))
            if role_track == "sap_consultant" and "sap" in text:
                score += 4.0
            if role_track == "data_engineer" and any(x in text for x in ["pipeline", "etl", "integration"]):
                score += 2.0
            if role_track == "data_analyst" and any(x in text for x in ["dashboard", "analytics", "insight"]):
                score += 2.0
            if role_track == "data_scientist" and any(x in text for x in ["model", "machine learning", "forecast"]):
                score += 2.0
            if role_track == "genai_engineer" and any(
                x in text for x in ["llm", "rag", "retrieval", "embedding", "vector", "agent", "prompt", "fastapi"]
            ):
                score += 4.0
            if role_track == "software_engineer" and any(
                x in text for x in ["software", "codebase", "api", "python", "deployment", "cloud", "aws", "lambda", "monitor", "automation"]
            ):
                score += 4.0
            scored.append((bid, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    ranked_ids = [bid for bid, _ in scored]
    seen = set()
    deduped = []
    for bid in ranked_ids:
        if bid not in seen:
            seen.add(bid)
            deduped.append(bid)
    return deduped[:8]


def build_tailoring_plan(
    llm: LLMClient,
    job_fields: dict[str, Any],
    candidate_profile: dict[str, Any],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    experience = candidate_profile.get("experience", [])
    bullet_ids: list[str] = []
    for exp in experience:
        for bullet in exp.get("bullets", []):
            if isinstance(bullet, dict) and bullet.get("id"):
                bullet_ids.append(bullet["id"])

    role_track = detect_role_track(job_fields)
    sector_track = detect_sector(job_fields)
    answers = _base_answers(candidate_profile, preferences)

    ats_keywords = extract_ats_keywords(job_fields)
    fit_score, reasons = _deterministic_fit_score(job_fields, candidate_profile, role_track, ats_keywords)
    gaps: list[str] = []
    if fit_score < 60:
        gaps.append("Fit is moderate; verify role expectations and highlight transferable projects.")
    plan = [
        "Re-order summary and skills to mirror top job requirements.",
        "Prioritize bullets that demonstrate direct tooling overlap.",
        "Keep claims factual and tied to existing profile entries.",
    ] + gaps
    suggested_bullets = rank_bullet_ids(candidate_profile, job_fields, ats_keywords, role_track, sector_track)[:6]
    suggested_project_ids = rank_project_ids(candidate_profile, job_fields, ats_keywords, sector_track, role_track)

    if llm.enabled:
        try:
            payload = (
                "JOB_FIELDS:\n"
                f"{job_fields}\n\n"
                "CANDIDATE_PROFILE:\n"
                f"{candidate_profile}\n\n"
                "PREFERENCES:\n"
                f"{preferences}"
            )
            generated = llm.json_completion(TAILORING_PLAN_PROMPT, payload)
            llm_fit_score = int(generated.get("fit_score", fit_score))
            fit_score = max(fit_score, min(100, round((fit_score * 0.75) + (llm_fit_score * 0.25))))
            llm_reasons = [str(item) for item in generated.get("fit_reasons", []) if str(item).strip()]
            reasons = _filter_inaccurate_fit_reasons(reasons + llm_reasons, job_fields)[:8]
            plan = list(generated.get("tailoring_plan", plan))
            llm_bullets = [bid for bid in generated.get("suggested_bullet_ids", suggested_bullets) if bid in bullet_ids]
            ranked = rank_bullet_ids(candidate_profile, job_fields, ats_keywords, role_track, sector_track)
            chosen = [bid for bid in llm_bullets if bid in ranked]
            for bid in ranked:
                if bid not in chosen:
                    chosen.append(bid)
            suggested_bullets = chosen[:8]
            answers.update({k: str(v) for k, v in generated.get("common_answers", {}).items()})
            ats_keywords = sanitize_ats_keywords(list(generated.get("ats_keywords", [])) + ats_keywords, job_fields)
            fit_score, deterministic_reasons = _deterministic_fit_score(job_fields, candidate_profile, role_track, ats_keywords)
            reasons = _filter_inaccurate_fit_reasons(deterministic_reasons + llm_reasons, job_fields)[:8]
        except Exception:
            pass

    if not suggested_bullets:
        suggested_bullets = rank_bullet_ids(candidate_profile, job_fields, ats_keywords, role_track, sector_track)
    suggested_project_ids = rank_project_ids(candidate_profile, job_fields, ats_keywords, sector_track, role_track)

    if not reasons:
        reasons = ["Insufficient explicit overlap detected; review manually before applying."]

    coverage = keyword_coverage(candidate_profile, ats_keywords)

    return {
        "fit_score": fit_score,
        "fit_reasons": reasons[:8],
        "tailoring_plan": (plan + [f"Target role track: {role_track}", f"Detected sector: {sector_track}"])[:8],
        "suggested_bullets": suggested_bullets,
        "suggested_project_ids": suggested_project_ids[:3],
        "role_track": role_track,
        "sector_track": sector_track,
        "common_answers": answers,
        "ats_keywords": ats_keywords[:20],
        "matched_keywords": coverage["matched_keywords"],
        "missing_keywords": coverage["missing_keywords"],
        "keyword_coverage_pct": coverage["keyword_coverage_pct"],
    }


def extract_ats_keywords(job_fields: dict[str, Any]) -> list[str]:
    corpus_parts = [str(item) for item in job_fields.get("skills", []) if str(item).strip()]
    corpus_parts.extend(str(item) for item in job_fields.get("requirements", []) if str(item).strip())
    corpus_parts.extend(str(item) for item in job_fields.get("responsibilities", []) if str(item).strip())
    corpus_parts.extend(
        str(job_fields.get(key, ""))
        for key in ("title", "summary", "job_text", "description")
        if str(job_fields.get(key, "")).strip()
    )
    corpus = " ".join(corpus_parts).lower()
    normalized: list[str] = []
    for skill in job_fields.get("skills", []):
        value = str(skill).strip()
        if not value or len(value.split()) > 4 or len(value) > 40:
            continue
        mapped = next((label for phrase, label in ATS_TERM_ALIASES if value.lower() == phrase or value.lower() == label.lower()), value)
        if mapped not in normalized:
            normalized.append(mapped)
    for phrase, label in ATS_TERM_ALIASES:
        boundary = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
        if re.search(boundary, corpus) and label not in normalized:
            normalized.append(label)
    return normalized[:35]


def sanitize_ats_keywords(keywords: list[str], job_fields: dict[str, Any]) -> list[str]:
    explicit = {
        str(item).strip().lower()
        for item in job_fields.get("skills", [])
        if str(item).strip()
    }
    normalized: list[str] = []
    for raw in keywords:
        value = str(raw).strip()
        low = value.lower()
        words = set(re.findall(r"[a-z]+", low))
        if words.intersection(ATS_NOISE_WORDS):
            continue
        match = next((label for phrase, label in ATS_TERM_ALIASES if low == phrase or low == label.lower()), None)
        if match and match not in normalized:
            normalized.append(match)
            continue
        # Preserve a concise explicit skill supplied by the parser, but never prose fragments.
        if low in explicit and len(value.split()) <= 4 and len(value) <= 40 and value not in normalized:
            normalized.append(value)
    return normalized[:35]


def rewrite_selected_bullets(
    llm: LLMClient,
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    selected_bullet_ids: list[str],
    role_track: str | None = None,
    priority_keywords: list[str] | None = None,
) -> dict[str, str]:
    original = {
        b.get("id"): b.get("text", "").strip()
        for exp in candidate_profile.get("experience", [])
        for b in exp.get("bullets", [])
        if isinstance(b, dict) and b.get("id")
    }
    selected = [bid for bid in selected_bullet_ids if bid in original]
    rewritten = {bid: original[bid] for bid in selected}
    if not selected or not llm.enabled:
        return rewritten

    payload = (
        "JOB_FIELDS:\n"
        f"{job_fields}\n\n"
        "ROLE_TRACK:\n"
        f"{role_track or detect_role_track(job_fields)}\n\n"
        "PRIORITY_KEYWORDS:\n"
        f"{priority_keywords or []}\n\n"
        "SELECTED_BULLET_IDS:\n"
        f"{selected}\n\n"
        "CANDIDATE_PROFILE:\n"
        f"{candidate_profile}"
    )
    try:
        response = llm.json_completion(CANDIDATE_BULLET_REWRITE_PROMPT, payload)
        for item in response.get("rewritten_bullets", []):
            bid = item.get("id")
            text = str(item.get("text", "")).strip()
            if bid in rewritten and _accept_rewritten_bullet(original.get(bid, ""), text):
                rewritten[bid] = text
    except Exception:
        return rewritten

    return rewritten


def rewrite_project_descriptions(
    llm: LLMClient,
    candidate_profile: dict[str, Any],
    job_fields: dict[str, Any],
    priority_keywords: list[str] | None = None,
    selected_project_ids: list[str] | None = None,
) -> dict[str, str]:
    projects = candidate_profile.get("academic_projects", [])
    original = {
        p.get("id"): str(p.get("description", "")).strip()
        for p in projects
        if isinstance(p, dict) and p.get("id")
    }
    project_ids = [pid for pid in original.keys() if pid]
    if selected_project_ids:
        selected = [pid for pid in selected_project_ids if pid in original]
        if selected:
            project_ids = selected
    rewritten = dict(original)
    if not project_ids or not llm.enabled:
        return rewritten

    payload = (
        "JOB_FIELDS:\n"
        f"{job_fields}\n\n"
        "PRIORITY_KEYWORDS:\n"
        f"{priority_keywords or []}\n\n"
        "PROJECT_IDS:\n"
        f"{project_ids}\n\n"
        "CANDIDATE_PROFILE:\n"
        f"{candidate_profile}"
    )
    try:
        response = llm.json_completion(PROJECT_REWRITE_PROMPT, payload)
        for item in response.get("rewritten_projects", []):
            pid = item.get("id")
            desc = str(item.get("description", "")).strip()
            if pid in rewritten and desc:
                rewritten[pid] = desc
    except Exception:
        return rewritten
    return rewritten


def _contains_keyword(corpus: str, keyword: str) -> bool:
    low = str(keyword or "").strip().lower()
    if not low:
        return False
    candidates = [low] + [alias.lower() for alias in KEYWORD_PROFILE_ALIASES.get(str(keyword).strip(), [])]
    for candidate in candidates:
        phrase = f" {candidate.strip()} "
        if len(candidate.strip()) <= 4:
            if re.search(rf"(?<![a-z0-9]){re.escape(candidate.strip())}(?![a-z0-9])", corpus):
                return True
        elif phrase in corpus or candidate.strip() in corpus:
            return True
    return False


def keyword_coverage(candidate_profile: dict[str, Any], ats_keywords: list[str]) -> dict[str, Any]:
    corpus_parts: list[str] = []
    corpus_parts.extend([str(s) for s in candidate_profile.get("skills", [])])
    for exp in candidate_profile.get("experience", []):
        corpus_parts.extend([str(b.get("text", "")) for b in exp.get("bullets", []) if isinstance(b, dict)])
    for proj in candidate_profile.get("academic_projects", []):
        corpus_parts.append(str(proj.get("name", "")))
        corpus_parts.append(str(proj.get("description", "")))
    for group in candidate_profile.get("technical_skills", []):
        if isinstance(group, dict):
            corpus_parts.extend([str(x) for x in group.get("items", [])])

    corpus = f" {' '.join(corpus_parts).lower()} "
    matched: list[str] = []
    missing: list[str] = []
    for kw in ats_keywords:
        k = str(kw).strip()
        if not k:
            continue
        if _contains_keyword(corpus, k):
            matched.append(k)
        else:
            missing.append(k)
    total = len(matched) + len(missing)
    pct = int(round((len(matched) / total) * 100)) if total else 0
    return {
        "matched_keywords": matched[:15],
        "missing_keywords": missing[:15],
        "keyword_coverage_pct": pct,
    }


def keyword_coverage_for_text(ats_keywords: list[str], text: str) -> dict[str, Any]:
    corpus = f" {str(text or '').lower()} "
    matched: list[str] = []
    missing: list[str] = []
    for kw in ats_keywords:
        k = str(kw).strip()
        if not k:
            continue
        if _contains_keyword(corpus, k):
            matched.append(k)
        else:
            missing.append(k)
    total = len(matched) + len(missing)
    pct = int(round((len(matched) / total) * 100)) if total else 0
    return {
        "matched_keywords": matched[:20],
        "missing_keywords": missing[:20],
        "keyword_coverage_pct": pct,
    }


def build_diff_summary(base_bullet_ids: list[str], selected_bullet_ids: list[str]) -> list[str]:
    selected_set = set(selected_bullet_ids)
    unchanged = [bid for bid in base_bullet_ids if bid in selected_set]
    omitted = [bid for bid in base_bullet_ids if bid not in selected_set]
    summary = [
        f"Selected {len(selected_bullet_ids)} bullets for targeted relevance.",
        f"Kept {len(unchanged)} base bullets unchanged.",
    ]
    if omitted:
        summary.append(f"De-prioritized bullet IDs: {', '.join(omitted[:8])}")
    return summary
