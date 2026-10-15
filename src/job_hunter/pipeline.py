"""Deterministic, auditable job ingestion, eligibility, matching and output."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import yaml
from bs4 import BeautifulSoup


EXPECTED_SOURCES = ("linkedin", "wellfound", "himalayas", "we_work_remotely",
                    "remote_ok", "greenhouse", "lever", "ashby")


def validate_source_coverage(data: dict) -> dict:
    """Require an auditable attempt for all eight sources, even when blocked/empty."""
    coverage = data.get("source_coverage")
    if not isinstance(coverage, dict):
        raise ValueError("Missing source_coverage: every run must attempt all eight sources")
    missing = sorted(set(EXPECTED_SOURCES) - set(coverage))
    if missing:
        raise ValueError("Missing required source attempts: " + ", ".join(missing))
    valid_statuses = {"searched", "no_matches", "blocked", "error"}
    for source in EXPECTED_SOURCES:
        entry = coverage[source]
        if not isinstance(entry, dict) or entry.get("status") not in valid_statuses:
            raise ValueError(f"Invalid coverage status for {source}")
        if not isinstance(entry.get("attempted_at"), str) or not entry["attempted_at"].strip():
            raise ValueError(f"Missing attempted_at for {source}")
        if entry["status"] in {"blocked", "error"} and not str(entry.get("reason") or "").strip():
            raise ValueError(f"Missing failure reason for {source}")
        if entry["status"] in {"searched", "no_matches"}:
            queries = entry.get("queries")
            legacy_query = entry.get("query_or_url")
            if not ((isinstance(queries, list) and any(str(x).strip() for x in queries))
                    or (isinstance(legacy_query, str) and legacy_query.strip())):
                raise ValueError(f"Missing attempted queries/URLs for {source}")
            if not isinstance(entry.get("pages_attempted"), int) or entry["pages_attempted"] < 1:
                raise ValueError(f"Missing pages_attempted for {source}")
        if not isinstance(entry.get("result_count"), int) or entry["result_count"] < 0:
            raise ValueError(f"Missing result_count for {source}")
        if not isinstance(entry.get("truncated"), bool):
            raise ValueError(f"Missing truncation disclosure for {source}")
        if entry["status"] == "no_matches" and entry["result_count"]:
            raise ValueError(f"no_matches source {source} cannot report results")
    return coverage

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


def _key_text(value: object) -> str:
    text = unquote(str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _company_key(value: object) -> str:
    words = _key_text(value).split()
    suffixes = {"inc", "incorporated", "ltd", "limited", "llc", "gmbh", "bv", "b v", "sa", "s a"}
    while words and words[-1] in suffixes:
        words.pop()
    return " ".join(words)


def _location_key(job: dict) -> str:
    explicit = job.get("location") or job.get("hybrid_office_country")
    if explicit:
        return _key_text(explicit)
    countries = sorted(_key_text(x) for x in (job.get("eligible_countries") or []) if x)
    return "|".join(countries)


def _is_verified_linkedin_job(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        return False
    host = parsed.netloc.casefold().removeprefix("www.")
    return host.endswith("linkedin.com") and bool(re.fullmatch(r"/jobs/view/(?:[^/]*-)?\d+", parsed.path.rstrip("/")))


def _candidate_urls(job: dict) -> list[str]:
    values = [job.get("url"), job.get("application_url"), job.get("source_url")]
    extra = job.get("source_urls") or []
    if isinstance(extra, list):
        values.extend(extra)
    urls = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            clean = canonical_url(value)
        except ValueError:
            continue
        if clean not in urls:
            urls.append(clean)
    return urls


def _merge_jobs(group: list[dict]) -> dict:
    """Merge only strong duplicate matches and retain every source/provenance URL."""
    preferred = max(group, key=lambda item: (
        _is_verified_linkedin_job(str(item.get("url") or "")),
        len(str(item.get("description") or "")),
    ))
    merged = dict(preferred)
    all_urls = []
    provenance = []
    for item in group:
        urls = _candidate_urls(item)
        for url in urls:
            if url not in all_urls:
                all_urls.append(url)
        provenance.append({
            "source": item.get("source"),
            "source_job_id": item.get("source_job_id"),
            "url": item.get("url"),
            "source_url": item.get("source_url"),
        })
        if len(str(item.get("description") or "")) > len(str(merged.get("description") or "")):
            for key in ("description", "description_sections", "description_language",
                        "description_completeness", "description_source_url",
                        "description_captured_at", "description_truncated", "description_notes"):
                if item.get(key) is not None:
                    merged[key] = item[key]
        if not (merged.get("logo_path") and merged.get("logo_source_url")) and (
                item.get("logo_path") and item.get("logo_source_url")):
            merged["logo_path"] = item["logo_path"]
            merged["logo_source_url"] = item["logo_source_url"]
    linkedin = next((url for url in all_urls if _is_verified_linkedin_job(url)), None)
    direct = next((url for item in group for url in _candidate_urls({"url": item.get("application_url")})
                   if not _is_verified_linkedin_job(url)), None)
    if linkedin:
        merged["url"] = linkedin
    if direct:
        merged["application_url"] = direct
    elif merged.get("application_url"):
        merged["application_url"] = canonical_url(str(merged["application_url"]))
    merged["source_urls"] = all_urls
    merged["provenance"] = provenance
    merged["sources"] = list(dict.fromkeys(str(x.get("source")) for x in group if x.get("source")))
    merged["deduplicated_count"] = len(group)
    identity = "|".join((_company_key(merged.get("company")), _key_text(merged.get("title")),
                         _location_key(merged)))
    merged["id"] = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return merged


def deduplicate_jobs(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deduplicate before scoring using exact normalized role identity or posting URL."""
    groups: list[list[dict]] = []
    by_url: dict[str, int] = {}
    by_role: dict[tuple[str, str, str], int] = {}
    invalid: list[dict] = []
    for index, raw in enumerate(jobs):
        try:
            job = normalize(raw)
        except (ValueError, TypeError) as exc:
            invalid.append({"status": "invalid", "input_index": index, "error": str(exc)})
            continue
        urls = _candidate_urls(job)
        role_key = (_company_key(job.get("company")), _key_text(job.get("title")), _location_key(job))
        group_index = next((by_url[url] for url in urls if url in by_url), None)
        role_match = by_role.get(role_key) if role_key[2] else None
        if group_index is None and role_match is not None:
            existing = groups[role_match]
            same_source_distinct_id = any(
                item.get("source") == job.get("source")
                and item.get("source_job_id") and job.get("source_job_id")
                and item.get("source_job_id") != job.get("source_job_id")
                for item in existing
            )
            if not same_source_distinct_id:
                group_index = role_match
        if group_index is None:
            group_index = len(groups)
            groups.append([])
        groups[group_index].append(job)
        if role_key[2]:
            by_role[role_key] = group_index
        for url in urls:
            by_url[url] = group_index
    return [_merge_jobs(group) for group in groups], invalid


def normalize(raw: dict) -> dict:
    required = ("company", "title", "url", "description")
    if any(not isinstance(raw.get(k), str) or not raw[k].strip() for k in required):
        raise ValueError("company, title, url, description are required strings")
    job = dict(raw)
    job["url"] = canonical_url(raw["url"])
    job["id"] = hashlib.sha256(job["url"].encode()).hexdigest()[:16]
    job["description"] = BeautifulSoup(raw["description"], "html.parser").get_text(" ", strip=True)
    if not job["description"]:
        raise ValueError("job description is empty after HTML cleanup")
    return job


def eligibility(job: dict, min_salary: int, hybrid_config: dict | None = None) -> tuple[str, list[str]]:
    """Remote preferred; evidence-backed remote-negotiation candidates are review-only.

    Negotiability evidence is explicit structured job data, never inferred from
    generic keyword matches or an employer's unverified remote-work claims.
    """
    reasons = []
    remote = str(job.get("remote_type", "unknown")).lower()
    if remote in ("remote", "fully_remote", "remote_only"):
        countries = [str(x).strip().lower() for x in (job.get("eligible_countries") or [])]
        if countries and not any(c in REGIONS for c in countries):
            return "rejected", ["Hiring geography excludes requested regions"]
        if not countries:
            reasons.append("Hiring-country eligibility unverified")
    elif remote in ("hybrid", "hybrid_work", "onsite", "on_site", "office", "unknown"):
        cfg = hybrid_config or {}
        allowed_countries = {str(x).lower() for x in cfg.get("allowed_countries", [])}
        location = str(job.get("hybrid_office_country") or "").strip().lower()
        evidence = job.get("hybrid_location_evidence")
        technology_evidence = job.get("company_technology_evidence_url")
        technology_description = str(job.get("company_technology_evidence") or "").strip()
        remote_jobs = job.get("company_other_remote_jobs") or []
        remote_evidence = [
            x for x in remote_jobs
            if isinstance(x, dict) and x.get("url")
            and str(x.get("remote_type", "")).lower() in ("remote", "fully_remote", "remote_only")
        ]
        if not allowed_countries or location not in allowed_countries:
            return "rejected", ["Office location not verified in Spain or Portugal"]
        if cfg.get("require_hybrid_location_evidence", True) and not evidence:
            return "rejected", ["Office location lacks evidence"]
        if cfg.get("require_technology_evidence", True) and not (
            technology_evidence and technology_description
        ):
            return "rejected", ["Technology-forward employer not evidenced"]
        if cfg.get("require_evidence_of_other_remote_jobs", False) and not remote_evidence:
            return "rejected", ["No cited fully remote vacancy at the same employer"]
        if remote in ("onsite", "on_site", "office"):
            return "rejected", ["Explicitly onsite-only job; remote negotiation not substantiated"]
        if remote == "unknown" and not cfg.get("allow_unknown_remote_policy_with_technology_evidence", False):
            return "rejected", ["Unknown work model is not eligible"]
        reasons.append("REMOTE-NEGOTIABLE CANDIDATE: this vacancy is not confirmed fully remote")
        if remote_evidence:
            reasons.append("Employer advertises other fully remote vacancies; this role's remote approval is not guaranteed")
        else:
            reasons.append("No verified remote vacancy at this employer; remote feasibility is speculative")
    else:
        return "rejected", ["Not verified fully remote or qualifying remote-negotiable role"]
    salary = job.get("salary") or {}
    if salary and salary.get("min") is not None:
        if salary.get("currency") == "EUR" and salary.get("period") == "year":
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


def company_maturity(job: dict, config: dict) -> tuple[str, list[str]]:
    """Evidence-based assessment; small headcount is never a rejection."""
    profile = job.get("company_profile") or {}
    assessment = str(profile.get("maturity_assessment") or "unknown").lower()
    notes = []
    if assessment == "new_unproven" and config.get("exclude_verified_new_unproven_companies", True):
        if profile.get("evidence_urls"):
            return "rejected", ["Verified newly established/unproven employer"]
        notes.append("Unproven assessment lacks supporting evidence")
    if assessment not in ("established", "consolidated"):
        notes.append("Employer maturity requires verification")
    if not profile.get("evidence_urls"):
        notes.append("No cited company maturity evidence")
    return ("review" if notes else "eligible"), notes



def employment_quality(job: dict, config: dict) -> tuple[str, list[str]]:
    """Reject task-based gigs and unassigned talent pools, not genuine employment."""
    company = str(job.get("company") or "").strip().casefold()
    excluded = [str(x).casefold() for x in config.get("excluded_companies", [])]
    if company in excluded or company.removesuffix(".ai") in excluded:
        return "rejected", ["Excluded contingent-work company"]
    model = str(job.get("engagement_model") or "").strip().lower()
    if model in config.get("excluded_models", []):
        return "rejected", ["Contingent/task-based work or unassigned talent pool"]
    assured = job.get("project_assured")
    if assured is False:
        return "rejected", ["No guaranteed project or ongoing work"]
    if assured is None and str(job.get("employment_type") or "").lower() in (
        "contract", "freelance", "contractor", "part_time_contract",
    ):
        return "review", ["Contract project/guaranteed hours not verified"]
    return "eligible", []


def score(job: dict) -> tuple[int, dict]:
    """Broad, evidence-based transferable-skill fit, not keyword saturation.

    A role matching one strong specialization can score well; it need not
    mention every satellite, AI, optimization, and backend keyword.
    """
    text = (job["title"] + " " + job["description"]).lower()
    title = job["title"].lower()
    sections = job.get("description_sections") or {}
    requirements = " ".join(str(x) for x in sections.get("requirements", []))
    context = (text + " " + requirements.lower())
    coverage = {
        area: sum(bool(re.search(r"(?<!\\w)" + re.escape(term) + r"(?!\\w)", context))
                  for term in terms) / len(terms)
        for area, terms in AREAS.items()
    }
    title_fit = min(1.0, sum(
        any(term in title for term in terms)
        for terms in AREAS.values()
    ) / 2)
    leadership = 1.0 if any(term in title for term in LEAD) else 0.0
    # A single relevant specialization is sufficient: don't dilute strong
    # Python/backend experience because the vacancy omits space or ML terms.
    strongest_area = max(coverage.values())
    relevant_areas = sum(value > 0 for value in coverage.values())
    transferable_fit = min(1.0, strongest_area * 2.5 + 0.15 * max(0, relevant_areas - 1))
    technical = max(coverage["ai_ml"], coverage["architecture"], coverage["backend"])
    domain = max(coverage["space"], coverage["optimization"])
    # Explicitly reward relevant role families, even for short descriptions.
    role_family = 1.0 if any(term in title for term in (
        "engineer", "developer", "architect", "tech lead", "technical lead",
        "platform", "backend", "software", "ml", "ai", "optimization",
    )) else 0.0
    total = round(
        20 * title_fit + 35 * transferable_fit + 15 * leadership
        + 20 * role_family + 10 * max(technical, domain)
    )
    return min(total, 100), {
        "title_fit": title_fit, "technical_fit": technical,
        "domain_fit": domain, "leadership_fit": leadership,
        "role_family_fit": role_family, "transferable_fit": transferable_fit,
        "area_coverage": coverage,
    }


def run(input_path: Path, output_dir: Path, config_path: Path, template_path: Path,
        render_pdf: bool = False) -> dict:
    from .renderer import render_cv

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if data.get("schema_version") not in ("1.0", "1.1") or not isinstance(data.get("jobs"), list):
        raise ValueError("Expected schema_version=1.0 or 1.1 and jobs array")
    coverage = validate_source_coverage(data)
    criteria = yaml.safe_load(config_path.read_text(encoding="utf-8"))["search"]
    output_dir.mkdir(parents=True, exist_ok=True)
    unique_jobs, invalid = deduplicate_jobs(data["jobs"])
    results = list(invalid)
    for job in unique_jobs:
        status, reasons = eligibility(job, criteria["minimum_salary_eur"], criteria.get("hybrid_exception"))
        maturity_status, maturity_notes = company_maturity(job, criteria.get("company_maturity", {}))
        reasons.extend(maturity_notes)
        work_status, work_notes = employment_quality(job, criteria.get("employment_quality", {}))
        reasons.extend(work_notes)
        if maturity_status == "rejected" or work_status == "rejected":
            status = "rejected"
        elif (maturity_status == "review" or work_status == "review") and status == "eligible":
            status = "review"
        match, breakdown = score(job)
        if job.get("description_completeness") in ("partial", "unknown") or job.get("description_truncated"):
            reasons.append("Incomplete job description; matching may be unreliable")
            if status == "eligible":
                status = "review"
        record = {**job, "eligibility": status, "eligibility_notes": reasons,
                  "company_maturity_status": maturity_status, "employment_quality_status": work_status,
                  "hybrid_exception": str(job.get("remote_type", "")).lower() in ("hybrid", "hybrid_work"),
                  "score": match, "score_breakdown": breakdown,
                  "shortlisted": status != "rejected" and match >= criteria["minimum_match_score"]}
        if record["shortlisted"]:
            target = output_dir / job["id"]
            target.mkdir(exist_ok=True)
            (target / "job.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            render_cv(template_path, target / "tailored_cv.html", record, render_pdf=render_pdf)
            record["cv_html"] = str(target / "tailored_cv.html")
            if render_pdf:
                record["cv_pdf"] = str(target / "tailored_cv.pdf")
                pdf = Path(record["cv_pdf"])
                if not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF") or pdf.stat().st_size < 1000:
                    raise RuntimeError(f"Invalid generated PDF for {job['id']}")
        results.append(record)
    report = {"schema_version": "1.1", "source_coverage": coverage, "processed_at": datetime.now(timezone.utc).isoformat(),
              "input": str(input_path), "total": len(data["jobs"]), "unique": len(unique_jobs),
              "duplicates_removed": len(data["jobs"]) - len(unique_jobs) - len(invalid),
              "deduplication_order": "before_scoring",
              "shortlisted": sum(bool(r.get("shortlisted")) for r in results), "results": results}
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report

