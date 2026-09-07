from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app import main
from app.models import JobActionType, MarkAppliedRequest, ReferralContact
from app.storage import _classify_role_family
from app.storage import Storage
from app.target_finder import Target, classify_shared_background


def test_jobs_are_scoped_to_their_owner(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    alice_job_id = storage.create_job(
        {
            "url": "https://example.com/alice",
            "title": "Data Analyst",
            "company": "Example Co",
            "job_text": "Data analyst role with SQL and dashboards.",
            "user_email": "alice@example.com",
        }
    )
    bob_job_id = storage.create_job(
        {
            "url": "https://example.com/bob",
            "title": "Data Engineer",
            "company": "Example Co",
            "job_text": "Data engineer role with pipelines.",
            "user_email": "bob@example.com",
        }
    )

    alice_jobs = storage.list_jobs(user_email="alice@example.com")
    assert [job["id"] for job in alice_jobs] == [alice_job_id]
    assert storage.get_job_for_user(alice_job_id, "alice@example.com") is not None
    assert storage.get_job_for_user(bob_job_id, "alice@example.com") is None


def test_extension_tokens_and_quota_events_are_user_specific(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    issued = storage.issue_extension_token("alice@example.com", user_name="Alice")
    user = storage.get_user_by_extension_token(issued["token"])

    assert user is not None
    assert user["email"] == "alice@example.com"

    storage.record_usage_event("alice@example.com", "analyze_job")
    since = datetime.now(timezone.utc) - timedelta(days=1)
    assert storage.count_usage_since("alice@example.com", "analyze_job", since) == 1
    assert storage.count_usage_since("bob@example.com", "analyze_job", since) == 0


def test_get_or_create_user_is_idempotent_and_preserves_identity(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    first = storage.get_or_create_user(
        "Alice@Example.com",
        name="Alice Example",
        image_url="https://example.com/alice.png",
    )
    second = storage.get_or_create_user("alice@example.com")

    assert second["id"] == first["id"]
    assert second["email"] == "alice@example.com"
    assert second["name"] == "Alice Example"
    assert second["image_url"] == "https://example.com/alice.png"


def test_role_family_title_signal_wins_for_data_scientist_job():
    role = _classify_role_family(
        "data scientist, Data & Analytics (Nashville, TN)",
        "Partner with teams to understand complex data relationships and build core data science models.",
    )

    assert role == "Data Scientist"


def test_referral_email_uses_requested_structure_and_job_specific_language():
    candidate = {
        "identity": {
            "full_name": "Venkatesh Mudaliar",
            "phone": "(201) 275-6554",
        },
        "links": {"linkedin": "https://linkedin.com/in/venkateshcmudaliar"},
        "education": [{"gpa": "3.89"}],
    }
    job = {
        "title": "AI Engineer",
        "company": "Workato",
        "job_text": "Build enterprise agentic systems, LLM agents, RAG, and production automation workflows.",
    }

    draft = main._fallback_referral_draft(
        candidate,
        job,
        "AI Engineer",
        "Workato",
        ReferralContact(name="David Chen", title="Engineering Manager"),
    )

    assert draft.email_subject == "Referral request: AI Engineer at Workato"
    assert draft.email_body.startswith("Hi David,\n\nI applied for the AI Engineer role at Workato")
    assert "A bit about me - I'm completing my M.S. in Data Science at Stevens Institute (GPA 3.89)" in draft.email_body
    assert "I'm genuinely interested in Workato specifically because" in draft.email_body
    assert "production LLM applications, RAG pipelines, and AI evaluation" in draft.email_body
    assert "I'd love a 15-minute call" in draft.email_body
    assert "Either way, thank you for your time." in draft.email_body
    assert draft.email_body.endswith(
        "Best,\nVenkatesh Mudaliar\n(201) 275-6554 | linkedin.com/in/venkateshcmudaliar"
    )
    assert "[" not in draft.email_body


def test_shared_company_contact_gets_contextual_linkedin_and_email_drafts():
    candidate = {
        "identity": {"full_name": "Venkatesh Mudaliar", "phone": "(201) 275-6554"},
        "links": {"linkedin": "https://linkedin.com/in/venkateshcmudaliar"},
        "education": [{"gpa": "3.82"}],
    }
    contact = ReferralContact(
        name="Shreya Apte",
        title="AI Manager",
        relationship_type="previous_company",
        shared_context="Accenture",
    )

    draft = main._fallback_referral_draft(
        candidate,
        {"title": "AI/ML Engineer - Associate Consultant", "job_text": "Build production AI systems."},
        "AI/ML Engineer - Associate Consultant",
        "Example Company",
        contact,
    )

    assert draft.linkedin_note.startswith("Hi Shreya, having worked at Accenture as well")
    assert "getting in touch with the right contact" in draft.linkedin_note
    assert draft.linkedin_note.endswith("Venkatesh.")
    assert "We both have experience at Accenture" in draft.email_body


def test_target_background_classification_uses_candidate_profile():
    profile = {
        "experience": [
            {"company": "Accenture"},
            {"company": "LTIMindtree Ltd."},
            {"company": "Stevens Institute of Technology"},
        ],
        "education": [{"school": "Stevens Institute of Technology"}],
    }
    former_colleague = classify_shared_background(
        Target(name="Shreya", evidence=["AI leader at Example Co. Previously at Accenture."]),
        profile,
    )
    alum = classify_shared_background(
        Target(name="Riju", evidence=["Example Co engineer and Stevens Institute of Technology graduate."]),
        profile,
    )
    unrelated = classify_shared_background(Target(name="David", evidence=["Recruiter at Example Co."]), profile)

    assert (former_colleague.relationship_type, former_colleague.shared_context) == ("previous_company", "Accenture")
    assert (alum.relationship_type, alum.shared_context) == ("school", "Stevens Institute of Technology")
    assert (unrelated.relationship_type, unrelated.shared_context) == ("beyond_network", "")


def test_complete_profile_required_for_signed_in_user_context(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "jobapply.db")
    monkeypatch.setattr(main, "storage", storage)

    with pytest.raises(HTTPException) as exc:
        main.require_complete_candidate_context({"email": "alice@example.com", "name": "Alice", "image_url": ""})

    assert exc.value.status_code == 409
    assert "Complete your beta profile" in str(exc.value.detail)


def test_saved_profile_inherits_updated_projects_and_normalizes_stale_location(tmp_path, monkeypatch):
    base_profile = {
        "identity": {"full_name": "Venkatesh Mudaliar", "location": "Antioch, CA"},
        "summary": "Updated applied AI summary.",
        "skills": ["Python", "Agentic AI"],
        "certifications": ["AWS Certified AI Practitioner"],
        "academic_projects": [
            {"id": "proj_4", "name": "SAP IntelliOps", "description": "Agentic SAP incident resolution."}
        ],
        "technical_skills": [{"category": "Generative AI and LLMs", "items": ["Tool Calling"]}],
    }
    storage = Storage(tmp_path / "jobapply.db")
    monkeypatch.setattr(main, "storage", storage)
    monkeypatch.setattr(main, "load_yaml", lambda _path: base_profile)
    storage.upsert_user_profile(
        "alice@example.com",
        {
            "identity": {"full_name": "Venkatesh Mudaliar", "location": "Jersey City, NJ"},
            "summary": "Old summary",
            "skills": ["SQL"],
            "academic_projects": [],
        },
        {},
    )

    candidate, _preferences = main.load_candidate_context(
        {"email": "alice@example.com", "name": "Alice", "image_url": ""}
    )

    assert candidate["identity"]["location"] == "Antioch, CA"
    assert "SQL" in candidate["skills"]
    assert "Agentic AI" in candidate["skills"]
    assert any(project["name"] == "SAP IntelliOps" for project in candidate["academic_projects"])


def test_signed_in_user_context_uses_saved_profile(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "jobapply.db")
    monkeypatch.setattr(main, "storage", storage)
    storage.upsert_user_profile(
        "alice@example.com",
        {
            "identity": {"full_name": "Alice Example", "email": "alice@example.com"},
            "experience": [{"company": "Known Inc", "role": "Engineer"}],
            "education": [{"degree": "BS Computer Science"}],
        },
        {},
    )

    candidate, preferences = main.require_complete_candidate_context(
        {"email": "alice@example.com", "name": "Alice", "image_url": ""}
    )

    assert candidate["identity"]["full_name"] == "Alice Example"
    assert preferences == {}


def test_mark_applied_records_pipeline_action(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "jobapply.db")
    monkeypatch.setattr(main, "storage", storage)
    job_id = storage.create_job(
        {
            "url": "https://example.com/job",
            "title": "Data Scientist",
            "company": "Example Co",
            "job_text": "Data scientist role with Python and machine learning.",
            "user_email": "alice@example.com",
            "fit_score": 85,
        }
    )

    response = main.mark_applied(
        MarkAppliedRequest(job_id=job_id, notes="Submitted on company site."),
        api_user={"email": "alice@example.com", "name": "Alice", "image_url": ""},
    )

    feed_items = storage.list_user_jobs("alice@example.com", status=JobActionType.APPLIED.value)
    assert response.status == main.JobStatus.MANUAL_SUBMISSION_REQUIRED
    assert len(feed_items) == 1
    assert feed_items[0]["title"] == "Data Scientist"
    assert feed_items[0]["aggregate_counts"]["applied"] == 1


def test_user_jobs_collapses_multiple_actions_per_feed_item(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    job_id = storage.create_job(
        {
            "url": "https://example.com/job",
            "title": "Data Scientist",
            "company": "Example Co",
            "job_text": "Data scientist role with Python and machine learning.",
            "user_email": "alice@example.com",
        }
    )
    feed_id = storage.upsert_feed_item_from_job(job_id)
    assert feed_id is not None
    storage.record_user_action("alice@example.com", feed_id, JobActionType.ANALYZED)
    storage.record_user_action("alice@example.com", feed_id, JobActionType.APPLIED)

    all_jobs = storage.list_user_jobs("alice@example.com")
    applied_jobs = storage.list_user_jobs("alice@example.com", status=JobActionType.APPLIED.value)

    assert [job["id"] for job in all_jobs] == [feed_id]
    assert all_jobs[0]["user_action"] == JobActionType.APPLIED.value
    assert all_jobs[0]["aggregate_counts"]["analyzed"] == 1
    assert all_jobs[0]["aggregate_counts"]["applied"] == 1
    assert all_jobs[0]["action_dates"]["analyzed"]
    assert all_jobs[0]["action_dates"]["applied"]
    assert [job["id"] for job in applied_jobs] == [feed_id]


def test_user_jobs_searches_company_and_role_across_tracked_applications(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    jobs = [
        ("AI Engineer", "Deloitte", "https://example.com/deloitte"),
        ("Data Scientist", "Sedgwick", "https://example.com/sedgwick"),
        ("Data Engineer", "Ancestry", "https://example.com/ancestry"),
    ]
    feed_ids = []
    for title, company, url in jobs:
        job_id = storage.create_job(
            {
                "url": url,
                "title": title,
                "company": company,
                "job_text": f"{title} role at {company}.",
                "user_email": "alice@example.com",
            }
        )
        feed_id = storage.upsert_feed_item_from_job(job_id)
        assert feed_id is not None
        feed_ids.append(feed_id)
        storage.record_user_action("alice@example.com", feed_id, JobActionType.APPLIED)

    by_company = storage.list_user_jobs("alice@example.com", search="deloitte")
    by_role = storage.list_user_jobs("alice@example.com", search="data scientist")
    partial_case_insensitive = storage.list_user_jobs("alice@example.com", search="ENGINEER")

    assert [job["id"] for job in by_company] == [feed_ids[0]]
    assert [job["id"] for job in by_role] == [feed_ids[1]]
    assert {job["id"] for job in partial_case_insensitive} == {feed_ids[0], feed_ids[2]}


def test_application_activity_counts_and_date_filters(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    job_id = storage.create_job(
        {
            "url": "https://example.com/tracked",
            "title": "AI Engineer",
            "company": "Example Co",
            "job_text": "AI engineer role building LLM and RAG services.",
            "user_email": "alice@example.com",
        }
    )
    feed_id = storage.upsert_feed_item_from_job(job_id)
    assert feed_id is not None
    storage.record_user_action("alice@example.com", feed_id, JobActionType.ANALYZED)
    storage.record_user_action("alice@example.com", feed_id, JobActionType.APPLIED)

    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    activity = storage.get_application_activity("alice@example.com", date_from=today, date_to=today)
    filtered_jobs = storage.list_user_jobs(
        "alice@example.com",
        status=JobActionType.APPLIED.value,
        date_from=today,
        date_to=today,
    )

    assert activity["periods"]["today"] == {"checked": 1, "applied": 1}
    assert activity["periods"]["week"] == {"checked": 1, "applied": 1}
    assert activity["periods"]["month"] == {"checked": 1, "applied": 1}
    assert activity["filtered"] == {"checked": 1, "applied": 1}
    assert activity["daily"][0] == {"date": today, "checked": 1, "applied": 1}
    assert [job["id"] for job in filtered_jobs] == [feed_id]


def test_application_activity_groups_utc_midnight_actions_by_eastern_date(tmp_path):
    storage = Storage(tmp_path / "jobapply.db")
    user = storage.get_or_create_user("alice@example.com")
    with storage._conn() as conn:
        for idx, created_at in enumerate(
            ["2026-06-10T23:45:00+00:00", "2026-06-11T00:03:00+00:00"],
            start=1,
        ):
            conn.execute(
                """
                INSERT INTO job_feed_items (
                    source_url, canonical_key, title, company, visibility, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'private', ?, ?)
                """,
                (f"https://example.com/{idx}", f"key-{idx}", f"Job {idx}", "Example", created_at, created_at),
            )
            feed_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """
                INSERT INTO user_job_actions (
                    user_id, job_feed_item_id, action_type, metadata, created_at, updated_at
                ) VALUES (?, ?, 'APPLIED', '{}', ?, ?)
                """,
                (user["id"], feed_id, created_at, created_at),
            )

    activity = storage.get_application_activity(
        "alice@example.com",
        date_from="2026-06-10",
        date_to="2026-06-10",
    )
    jobs = storage.list_user_jobs(
        "alice@example.com",
        status=JobActionType.APPLIED.value,
        date_from="2026-06-10",
        date_to="2026-06-10",
    )

    assert activity["filtered"]["applied"] == 2
    assert activity["daily"][0] == {"date": "2026-06-10", "checked": 0, "applied": 2}
    assert len(jobs) == 2
