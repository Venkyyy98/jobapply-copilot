from app.compliance import check_for_unsupported_claims, check_profile_completeness


def test_profile_completeness_reports_missing_fields():
    profile = {"identity": {"full_name": "", "email": ""}, "experience": [], "education": []}
    issues = check_profile_completeness(profile)
    assert any("identity.full_name" in item for item in issues)
    assert any("experience" in item for item in issues)


def test_compliance_flags_unknown_years():
    profile = {
        "identity": {"full_name": "Test User", "email": "test@example.com"},
        "experience": [{"company": "Known Inc", "role": "Engineer", "start_date": "2020-01", "end_date": "2022-01"}],
        "education": [{"degree": "BS Computer Science"}],
        "certifications": ["AWS Certified Developer"],
    }
    outputs = ["I delivered 75% growth in 2025 at Unknown Corp."]
    issues = check_for_unsupported_claims(profile, outputs)
    assert any("2025" in item for item in issues)
