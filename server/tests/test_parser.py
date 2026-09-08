from app.llm import LLMClient
from app.parser import parse_job_fields
from app.parser import trim_to_job_description
from app.parser import validate_job_content


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


def test_trim_to_job_description_removes_application_form_tail():
    text = """
Data Scientist
You Have:
3+ years of experience as a data scientist.
Proficiency in SQL and Python.
Apply for this job
Voluntary Self-Identification of Disability
People can become disabled, so we need to ask this question at least every five years.
"""

    trimmed = trim_to_job_description(text)

    assert "3+ years of experience" in trimmed
    assert "every five years" not in trimmed
    assert "Voluntary Self-Identification" not in trimmed


def test_parse_job_fields_skips_view_more_jobs_heading():
    text = """
View More Jobs
Data Science Co-op
United States (Hybrid)
Number of Position(s): 2
Duration: 4 Months
Location: Hybrid in Murry Hill
Your responsibilities
Work on the development of big data analysis and visualization use cases within Splunk.
Develop web-based database applications using PhP, Javascript, VueJS, Python and MySQL.
Your skills and experience
Interest in software development, ideally having worked with PHP, Javascript, Python, MySQL, VueJS, Selenium, VMware, AWS.
"""
    llm = LLMClient(api_key="")
    result = parse_job_fields(
        llm=llm,
        job_text=text,
        page_title="Data Science Co-op - Nokia Careers",
        company_hint="Detected or edit manually",
        url="https://careers.nokia.com/job/35743",
    )

    assert result["title"] == "Data Science Co-op"
    assert result["company"] == "Nokia"


def test_parse_job_fields_extracts_location_from_locations_label():
    text = """
IT Intern — AI Service Desk Assistant
Apply
locations
San Jose, CA
time type
Full time
What You'll Do
Build an AI-powered IT Service Desk Assistant using LLM APIs and RAG.
Required Skills & Qualifications
Proficiency in Python, working knowledge of LLM APIs, RAG concepts, and Git.
"""
    llm = LLMClient(api_key="")
    result = parse_job_fields(
        llm=llm,
        job_text=text,
        page_title="IT Intern — AI Service Desk Assistant | Lyten Careers",
        company_hint="Lyten",
        url="https://example.com/lyten-it-intern",
    )

    assert result["title"] == "IT Intern — AI Service Desk Assistant"
    assert result["company"] == "Lyten"
    assert result["location"] == "San Jose, CA"


def test_parse_job_fields_cleans_job_location_suffix_from_title():
    llm = LLMClient(api_key="")
    result = parse_job_fields(
        llm=llm,
        job_text="Job Purpose: Data Scientist will build machine learning models. Requirements include Python and SQL experience.",
        page_title="Data Scientist job in Atlanta, Georgia, 30328",
        company_hint="Veritiv",
        url="https://example.com/veritiv-data-scientist",
    )

    assert result["title"] == "Data Scientist"
    assert result["company"] == "Veritiv"

    result = parse_job_fields(
        llm=llm,
        job_text="Data Scientist I role using Python, SQL, machine learning, and predictive modeling.",
        page_title="Data Scientist I in Chantilly, Virginia",
        company_hint="Noblis",
        url="https://example.com/noblis-data-scientist",
    )

    assert result["title"] == "Data Scientist I"


def test_parse_job_fields_cleans_application_prefix_and_heading_location():
    llm = LLMClient(api_key="")
    result = parse_job_fields(
        llm=llm,
        job_text="""
Machine Learning Engineer - Mountain View, CA
Who we are
Atoms builds Physical AI systems for real-world industries.
What you'll do
Build machine learning intelligence and applications for production systems.
Requirements
Experience with Python and machine learning.
""",
        page_title="Job Application for Machine Learning Engineer",
        company_hint="Atoms",
        url="https://example.com/atoms-machine-learning-engineer",
    )

    assert result["title"] == "Machine Learning Engineer"
    assert result["company"] == "Atoms"


def test_parse_job_fields_preserves_user_confirmed_title_and_company():
    class MisleadingLLM:
        enabled = True

        def json_completion(self, _prompt, _payload):
            return {
                "title": "Machine Learning Engineer at Checkr",
                "company": "Banyan Infrastructure Corporation",
                "location": "San Francisco, CA",
            }

    result = parse_job_fields(
        llm=MisleadingLLM(),
        job_text="""
About Checkr
We're hiring an ML Engineer to build AI systems.
Requirements
Experience with Python and machine learning.
""",
        page_title="Machine Learning Engineer | Checkr",
        title_hint="Machine Learning Engineer",
        company_hint="Checkr",
        url="https://example.com/checkr-machine-learning-engineer",
    )

    assert result["title"] == "Machine Learning Engineer"
    assert result["company"] == "Checkr"


def test_parse_job_fields_removes_company_suffix_from_title():
    result = parse_job_fields(
        llm=LLMClient(api_key=""),
        job_text="""
About Checkr
We're hiring an ML Engineer to build AI systems.
Requirements
Experience with Python and machine learning.
""",
        page_title="Machine Learning Engineer at Checkr",
        company_hint="Checkr",
        url="https://example.com/checkr-machine-learning-engineer",
    )

    assert result["title"] == "Machine Learning Engineer"


def test_validate_job_content_rejects_linkedin_profile_text():
    reason = validate_job_content(
        """
        Hayri Izgi 3rd degree connection Data Science Business Intelligence Machine Learning Python
        Austin, Texas, United States 500 followers People also viewed Connect with this person
        Experience Education Licenses Certifications Skills Recommendations Activity Posts
        """,
        page_title="Hayri Izgi | LinkedIn",
    )

    assert reason
    assert "LinkedIn profile" in reason


def test_validate_job_content_rejects_job_search_list_page():
    reason = validate_job_content(
        """
        View More Jobs View More Jobs View More Jobs Search results for data engineer roles.
        Save this search and browse recommended jobs. Filters location date posted company.
        """,
        page_title="Data engineer jobs",
    )

    assert reason
    assert "job search/listing page" in reason
