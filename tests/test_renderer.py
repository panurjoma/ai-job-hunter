from pathlib import Path

from bs4 import BeautifulSoup

from job_hunter.renderer import render_cv


def test_cv_preserves_verified_claims_and_roles(tmp_path):
    template = Path("templates/master_cv_reference.html")
    original = BeautifulSoup(template.read_text(encoding="utf-8"), "html.parser")
    target = tmp_path / "tailored.html"
    job = {
        "title": "AI Software Tech Lead",
        "url": "https://example.com/jobs/123",
        "description": "AI agent architecture, RAG, Python and distributed systems",
        "description_sections": {"requirements": ["Python", "AI architecture"]},
    }
    render_cv(template, target, job)
    result = BeautifulSoup(target.read_text(encoding="utf-8"), "html.parser")
    assert result.find("h1").get_text(strip=True) == original.find("h1").get_text(strip=True)
    assert sorted(x.get_text(" ", strip=True) for x in result.select("article.role li")) == sorted(
        x.get_text(" ", strip=True) for x in original.select("article.role li")
    )
    assert [x.get_text(" ", strip=True) for x in result.select(".role-meta")] == [
        x.get_text(" ", strip=True) for x in original.select(".role-meta")
    ]
    assert (tmp_path / "tailoring_manifest.json").is_file()


def test_role_specific_prioritization(tmp_path):
    template = Path("templates/master_cv_reference.html")
    paths = [tmp_path / "ai.html", tmp_path / "space.html"]
    jobs = [
        {"title": "AI Architect", "url": "https://example.com/a",
         "description": "LLM RAG embeddings agent orchestration", "description_sections": {}},
        {"title": "Space Systems Engineer", "url": "https://example.com/b",
         "description": "satellite constellation GNSS navigation", "description_sections": {}},
    ]
    for path, job in zip(paths, jobs):
        render_cv(template, path, job)
    assert paths[0].read_text(encoding="utf-8") != paths[1].read_text(encoding="utf-8")


def test_cv_manifest_reports_missing_official_logo(tmp_path):
    import json
    template = Path("templates/master_cv_reference.html")
    job = {"title": "Senior AI Engineer", "url": "https://example.com/job",
           "description": "Build AI services", "logo_path": None}
    render_cv(template, tmp_path / "cv.html", job)
    manifest = json.loads((tmp_path / "tailoring_manifest.json").read_text())
    assert manifest["company_logo_embedded"] is False
    assert manifest["company_logo_status"] == "missing_official_asset"
    assert not BeautifulSoup((tmp_path / "cv.html").read_text(), "html.parser").select(".company-logo")


def test_cv_rejects_logo_without_source(tmp_path):
    import pytest
    from job_hunter.renderer import _company_logo_data_uri
    with pytest.raises(ValueError, match="verified official"):
        _company_logo_data_uri({"logo_path": "data/inbox/assets/batch/job.png"},
                               Path("templates/master_cv_reference.html"))
