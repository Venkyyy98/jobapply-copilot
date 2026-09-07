from app.resume_render import _resolve_header_location


def test_resume_header_uses_california_address_for_california_jobs():
    candidate = {"identity": {"location": "Antioch, California, United States"}}
    job = {
        "title": "IT Intern — AI Service Desk Assistant",
        "location": "San Jose, CA",
        "job_text": "Build an AI service desk assistant using LLM APIs and RAG.",
    }

    assert _resolve_header_location(candidate, job) == "San Francisco Bay Area, CA"


def test_resume_header_does_not_claim_local_nj_address_for_nj_jobs():
    candidate = {"identity": {"location": "Antioch, California, United States"}}
    job = {
        "title": "Data Science Co-op",
        "location": "Murray Hill, NJ",
        "job_text": "Similar Jobs Senior Data Engineer India Hybrid",
    }

    assert _resolve_header_location(candidate, job) == "Antioch, California, United States"
