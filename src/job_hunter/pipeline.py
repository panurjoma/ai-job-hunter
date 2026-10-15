"""Deterministic, auditable job ingestion, eligibility, matching and output."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml
from bs4 import BeautifulSoup

AREAS = {
    "ai_ml": ("ai", "machine learning", "llm", "rag", "agent", "retrieval", "reinforcement learning"),
    "architecture": ("architect", "architecture", "system design", "distributed", "microservices"),
    "backend": ("backend", "python", "c++", "api", "kafka", "kubernetes", "redis"),
    "space": ("space", "satellite", "aerospace", "esa", "constellation", "gnss", "orbital"),
    "optimization": ("optimization", "optimisation", "allocation", "planning", "scheduling", "numerical"),
}
LEAD = ("tech lead", "technical lead", "engineering lead", "staff", "principal", "architect", "senior")
REGIONS = {"spain", "portugal", "netherlands", "europe", "eu", "eea", "european union"}


def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    if p.scheme not in {"https", "http"} or not p.netloc:
        raise ValueError("job URL must be http(s)")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))


def normalize(raw: dict) -> dict:
    required = ("company", "title", "url", "description")
    if any(not isinstance(raw.get(k), str) or not raw[k].strip() for k in required):
        raise ValueError("company, title, url, description are required strings")
    job = dict(raw)
    job["url"] = canonical_url(raw["url"])
    job["id"] = hashlib.sha256(job["url"].encode()).hexdigest()[:16]
    job["description"] = BeautifulSoup(raw["description"], "html.parser").get_text(" ", strip=True)
    return job


def eligibility(job: dict, min_salary: int) -> tuple[str, list[str]]:
    reasons = []
    remote = str(job.get("remote_type", "unknown")).lower()
    if remote not in ("remote", "fully_remote", "remote_only"):
        return "rejected", ["Not verified fully remote"]
    countries = [str(x).lower() for x in (job.get("eligible_countries") or [])]
    if countries and not any(c in REGIONS for c in countries):
        return "rejected", ["Hiring geography excludes requested regions"]
    if not countries:
        reasons.append("Hiring-country eligibility unverified")
    salary = job.get("salary") or {}
    if salary and salary.get("min") is not None:
        if salary.get("currency") == "EUR" and salary.get("period") == "year":
            # Reject only when even the maximum available annual base salary is below the floor.
            ceiling = salary.get("max")
            if ceiling is not None and float(ceiling) < min_salary:
                return "rejected", ["Confirmed salary ceiling below minimum"]
            if float(salary["min"]) < min_salary:
                reasons.append("Salary range partially below minimum")
        else:
            reasons.append("Salary needs currency/period normalization")
    else:
        reasons.append("Salary unverified")
    return ("review" if reasons else "eligible"), reasons


def score(job: dict) -> tuple[int, dict]:
    text = (job["title"] + " " + job["description"]).lower()
    title = job["title"].lower()
    coverage = {k: sum(bool(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text)) for w in words) / len(words)
                for k, words in AREAS.items()}
    role = max(coverage.values())
    title_fit = min(1.0, sum(any(w in title for w in words) for words in AREAS.values()) / 2)
    leadership = 1.0 if any(t in title for t in LEAD) else 0.0
    technical = (coverage["ai_ml"] + coverage["architecture"] + coverage["backend"]) / 3
    domain = max(coverage["space"], coverage["optimization"])
    total = round(30 * title_fit + 35 * max(technical, role) + 20 * domain + 15 * leadership)
    return min(total, 100), {"title_fit": title_fit, "technical_fit": technical, "domain_fit": domain,
                              "leadership_fit": leadership, "area_coverage": coverage}


def run(input_path: Path, output_dir: Path, config_path: Path, template_path: Path,
        render_pdf: bool = False) -> dict:
    from .renderer import render_cv

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0" or not isinstance(data.get("jobs"), list):
        raise ValueError("Expected schema_version=1.0 and jobs array")
    criteria = yaml.safe_load(config_path.read_text(encoding="utf-8"))["search"]
    output_dir.mkdir(parents=True, exist_ok=True)
    seen = set()
    results = []
    for raw in data["jobs"]:
        try:
            job = normalize(raw)
        except (ValueError, TypeError) as exc:
            results.append({"status": "invalid", "error": str(exc)})
            continue
        if job["id"] in seen:
            continue
        seen.add(job["id"])
        status, reasons = eligibility(job, criteria["minimum_salary_eur"])
        match, breakdown = score(job)
        record = {**job, "eligibility": status, "eligibility_notes": reasons,
                  "score": match, "score_breakdown": breakdown,
                  "shortlisted": status != "rejected" and match >= criteria["minimum_match_score"]}
        if record["shortlisted"]:
            target = output_dir / job["id"]
            target.mkdir(exist_ok=True)
            (target / "job.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            render_cv(template_path, target / "tailored_cv.html", job, render_pdf=render_pdf)
            record["cv_html"] = str(target / "tailored_cv.html")
            if render_pdf:
                record["cv_pdf"] = str(target / "tailored_cv.pdf")
        results.append(record)
    report = {"schema_version": "1.0", "processed_at": datetime.now(timezone.utc).isoformat(),
              "input": str(input_path), "total": len(data["jobs"]), "unique": len(seen),
              "shortlisted": sum(bool(r.get("shortlisted")) for r in results), "results": results}
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
