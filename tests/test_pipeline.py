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


def test_maturity_unknown_is_review():
    from job_hunter.pipeline import company_maturity
    assert company_maturity({"company_profile": {"maturity_assessment": "unknown"}}, {})[0] == "review"


def test_maturity_verified_unproven_is_rejected():
    from job_hunter.pipeline import company_maturity
    job = {"company_profile": {
        "maturity_assessment": "new_unproven",
        "evidence_urls": ["https://example.com/company"],
    }}
    assert company_maturity(job, {"exclude_verified_new_unproven_companies": True})[0] == "rejected"


def test_end_to_end_example_inbox(tmp_path):
    from pathlib import Path
    from job_hunter.pipeline import run
    report = run(
        Path("data/inbox/example_jobs.json"),
        tmp_path / "output",
        Path("config/search_criteria.yaml"),
        Path("templates/master_cv_reference.html"),
        render_pdf=False,
    )
    assert report["total"] == 1
    assert report["unique"] == 1
    assert (tmp_path / "output" / "report.json").exists()
    assert report["results"][0]["company_maturity_status"] == "eligible"
