from job_hunter.pipeline import canonical_url, eligibility, normalize, score


def test_canonical_url_drops_tracking():
    assert canonical_url("https://Example.com/jobs/123/?utm_source=x") == "https://example.com/jobs/123"


def test_remote_required():
    assert eligibility({"remote_type": "hybrid"}, 90000)[0] == "rejected"


def test_salary_ceiling():
    job = {"remote_type": "remote", "eligible_countries": ["Spain"],
           "salary": {"min": 70000, "max": 85000, "currency": "EUR", "period": "year"}}
    assert eligibility(job, 90000)[0] == "rejected"


def test_normalize_html():
    job = normalize({"company": "A", "title": "Senior AI Architect", "url": "https://a.com/x",
                     "description": "<p>Space <b>optimization</b></p>"})
    assert job["description"] == "Space optimization"
    assert isinstance(score(job)[0], int)
