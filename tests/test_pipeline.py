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


def test_end_to_end_pdf_render(tmp_path):
    from pathlib import Path
    from job_hunter.pipeline import run
    report = run(
        Path("data/inbox/example_jobs.json"),
        tmp_path / "output",
        Path("config/search_criteria.yaml"),
        Path("templates/master_cv_reference.html"),
        render_pdf=True,
    )
    assert report["shortlisted"] >= 1
    shortlisted = [r for r in report["results"] if r.get("shortlisted")]
    for job in shortlisted:
        pdf = Path(job["cv_pdf"])
        assert pdf.exists()
        assert pdf.read_bytes().startswith(b"%PDF")
        assert pdf.stat().st_size > 1000


def test_transferable_backend_role_short_description_scores_above_50():
    from job_hunter.pipeline import score
    job = {
        "title": "Senior Backend Engineer",
        "description": "Develop reliable Python APIs and distributed backend services.",
    }
    value, breakdown = score(job)
    assert value >= 50
    assert breakdown["role_family_fit"] == 1


def test_unrelated_role_is_not_inflated():
    from job_hunter.pipeline import score
    value, _ = score({
        "title": "Sales Account Executive",
        "description": "Close deals and manage sales accounts.",
    })
    assert value < 50


def test_shortlist_threshold_is_60():
    from pathlib import Path
    import yaml
    criteria = yaml.safe_load(Path("config/search_criteria.yaml").read_text())["search"]
    assert criteria["minimum_match_score"] == 60


def test_exclude_contingent_gigs_even_with_high_score():
    from job_hunter.pipeline import employment_quality
    config = {
        "excluded_companies": ["outlier.ai", "outlier"],
        "excluded_models": ["task_based_gig", "ai_training_evaluator", "talent_pool",
                            "contingent_project_matching", "unassigned_contract"],
    }
    assert employment_quality({"company": "Outlier.ai"}, config)[0] == "rejected"
    assert employment_quality({"company": "G2i", "engagement_model": "ai_training_evaluator"}, config)[0] == "rejected"
    assert employment_quality({"company": "Proxify AB", "project_assured": False}, config)[0] == "rejected"
    assert employment_quality({"company": "Established Consultancy", "employment_type": "full_time"}, config)[0] == "eligible"


def test_company_logo_embedded_in_html(tmp_path):
    from pathlib import Path
    from job_hunter.renderer import render_cv
    root = tmp_path
    templates = root / "templates"
    templates.mkdir()
    template = templates / "cv.html"
    template.write_text("<html><head></head><body><header class='header'><h1>Candidate</h1></header></body></html>")
    logo = root / "data/inbox/assets/testbatch/official.svg"
    logo.parent.mkdir(parents=True)
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#123456"/></svg>')
    output = root / "out/cv.html"
    render_cv(template, output, {
        "title": "Senior Backend Engineer", "description": "Python backend",
        "url": "https://example.org/job", "logo_path": "data/inbox/assets/testbatch/official.svg",
        "logo_source_url": "https://example.org/brand/official.svg"
    })
    assert 'class="company-logo"' in output.read_text()
    assert "data:image/svg+xml;base64," in output.read_text()
    assert '"company_logo_embedded": true' in (output.parent / "tailoring_manifest.json").read_text()


def test_logo_rejects_external_path(tmp_path):
    from job_hunter.renderer import _company_logo_data_uri
    from pathlib import Path
    import pytest
    with pytest.raises(ValueError):
        _company_logo_data_uri({"logo_path": "https://example.org/logo.svg"}, Path("templates/master_cv_reference.html"))



def test_technology_forward_hybrid_across_any_domain():
    cfg = {"allowed_countries": ["Spain", "Portugal"],
           "require_technology_evidence": True,
           "require_hybrid_location_evidence": True,
           "allow_unknown_remote_policy_with_technology_evidence": True}
    job = {
        "remote_type": "hybrid", "hybrid_office_country": "Portugal",
        "hybrid_location_evidence": "Lisbon hybrid role on employer careers page",
        "company_domain": "renewable_energy",
        "company_technology_evidence_url": "https://example.com/engineering",
        "company_technology_evidence": "Software-first energy optimization product",
        "salary": {"min": 90000, "max": 115000, "currency": "EUR", "period": "year"},
    }
    status, notes = eligibility(job, 90000, cfg)
    assert status == "review"
    assert any("speculative" in note for note in notes)
    assert eligibility({**job, "remote_type": "unknown"}, 90000, cfg)[0] == "review"
    assert eligibility({**job, "company_domain": "healthcare"}, 90000, cfg)[0] == "review"
    assert eligibility({**job, "hybrid_office_country": "Netherlands"}, 90000, cfg)[0] == "rejected"
    assert eligibility({**job, "company_technology_evidence_url": None}, 90000, cfg)[0] == "rejected"
    assert eligibility({**job, "remote_type": "onsite"}, 90000, cfg)[0] == "rejected"
    assert eligibility({**job, "salary": {"min": 60000, "max": 85000, "currency": "EUR", "period": "year"}}, 90000, cfg)[0] == "rejected"


def test_other_remote_jobs_strengthen_but_are_not_required():
    cfg = {"allowed_countries": ["Spain"], "require_technology_evidence": True}
    job = {"remote_type": "hybrid", "hybrid_office_country": "Spain",
           "hybrid_location_evidence": "Employer careers page confirms Madrid hybrid office",
           "company_technology_evidence_url": "https://example.com/technology",
           "company_technology_evidence": "Technology product engineering",
           "company_other_remote_jobs": [{"url": "https://example.com/jobs/remote", "remote_type": "remote"}]}
    status, notes = eligibility(job, 90000, cfg)
    assert status == "review"
    assert any("other fully remote" in note for note in notes)


def test_all_eight_sources_required():
    import pytest
    from job_hunter.pipeline import EXPECTED_SOURCES, validate_source_coverage
    coverage = {s: {"status": "no_matches", "attempted_at": "2026-10-15T10:00:00Z",
                    "query_or_url": "fixture://query", "pages_attempted": 1,
                    "result_count": 0, "truncated": False}
                for s in EXPECTED_SOURCES}
    assert len(validate_source_coverage({"source_coverage": coverage})) == 8
    del coverage["linkedin"]
    with pytest.raises(ValueError, match="linkedin"):
        validate_source_coverage({"source_coverage": coverage})
    coverage["linkedin"] = {"status": "blocked", "attempted_at": "2026-10-15T10:00:00Z",
                            "result_count": 0, "truncated": True}
    with pytest.raises(ValueError, match="reason"):
        validate_source_coverage({"source_coverage": coverage})


def test_deduplicates_before_scoring_and_prefers_linkedin_posting():
    from job_hunter.pipeline import deduplicate_jobs
    direct = {
        "source": "greenhouse", "source_job_id": "gh-42", "company": "Example, Inc.",
        "title": "Senior Backend Engineer", "location": "Europe",
        "url": "https://boards.greenhouse.io/example/jobs/42",
        "application_url": "https://boards.greenhouse.io/example/jobs/42#app",
        "description": "Build Python distributed backend systems.",
    }
    linkedin = {
        "source": "linkedin", "source_job_id": "123456789", "company": "Example",
        "title": "Senior Backend Engineer", "location": "Europe",
        "url": "https://www.linkedin.com/jobs/view/senior-backend-engineer-123456789?trk=x",
        "description": "Build Python distributed backend systems for a European product.",
    }
    jobs, invalid = deduplicate_jobs([direct, linkedin])
    assert not invalid
    assert len(jobs) == 1
    assert jobs[0]["url"] == "https://www.linkedin.com/jobs/view/senior-backend-engineer-123456789"
    assert jobs[0]["application_url"] == "https://boards.greenhouse.io/example/jobs/42"
    assert jobs[0]["sources"] == ["greenhouse", "linkedin"]
    assert len(jobs[0]["source_urls"]) == 2
    assert jobs[0]["deduplicated_count"] == 2


def test_linkedin_search_page_is_never_preferred():
    from job_hunter.pipeline import deduplicate_jobs
    base = {"company": "Example", "title": "AI Engineer", "location": "Spain",
            "description": "Build AI systems"}
    jobs, _ = deduplicate_jobs([
        {**base, "source": "lever", "url": "https://jobs.lever.co/example/abc"},
        {**base, "source": "linkedin", "url": "https://linkedin.com/jobs/search/?keywords=AI"},
    ])
    assert jobs[0]["url"] == "https://jobs.lever.co/example/abc"


def test_distinct_same_source_requisitions_are_not_destructively_merged():
    from job_hunter.pipeline import deduplicate_jobs
    base = {"source": "greenhouse", "company": "Example", "title": "Backend Engineer",
            "location": "Spain", "description": "Build backend services"}
    jobs, _ = deduplicate_jobs([
        {**base, "source_job_id": "1", "url": "https://boards.greenhouse.io/example/jobs/1"},
        {**base, "source_job_id": "2", "url": "https://boards.greenhouse.io/example/jobs/2"},
    ])
    assert len(jobs) == 2

