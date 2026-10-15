"""Fact-preserving CV tailoring against the user's verified HTML template.

Never insert job-description claims into the candidate's CV. Tailoring selects
and prioritizes existing evidence only, preserving original employment facts.
"""
from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

TERMS = {
    "ai": ("ai", "machine learning", "llm", "rag", "agent", "retrieval", "reinforcement"),
    "space": ("space", "satellite", "aerospace", "constellation", "navigation", "gnss"),
    "architecture": ("architect", "distributed", "microservices", "kafka", "system design"),
    "optimization": ("optimization", "allocation", "planning", "scheduling", "numerical"),
    "backend": ("backend", "python", "c++", "api", "kubernetes", "redis"),
}


def _priorities(job: dict) -> list[str]:
    title = job["title"].lower()
    description = job["description"].lower()
    sections = job.get("description_sections") or {}
    requirements = " ".join(str(x) for x in sections.get("requirements", [])).lower()
    return sorted(TERMS, key=lambda area: (
        5 * sum(term in title for term in TERMS[area])
        + 3 * sum(term in requirements for term in TERMS[area])
        + sum(term in description for term in TERMS[area])
    ), reverse=True)


def _relevance(text: str, priorities: list[str]) -> int:
    text = text.lower()
    return sum((len(priorities) - rank) * sum(term in text for term in TERMS[area])
               for rank, area in enumerate(priorities))


def _sort_children(parent, tag: str, priorities: list[str]) -> None:
    if parent is None:
        return
    children = parent.find_all(tag, recursive=False)
    # Stable sorting: equally relevant original statements retain their order.
    for child in sorted(children, key=lambda el: _relevance(el.get_text(" ", strip=True), priorities),
                        reverse=True):
        parent.append(child)


def render_cv(template_path: Path, output_path: Path, job: dict, render_pdf: bool = False) -> None:
    soup = BeautifulSoup(template_path.read_text(encoding="utf-8"), "html.parser")
    priorities = _priorities(job)
    # Professional summary: reorder only verified existing bullets.
    summary = next((s for s in soup.select("section") if s.find("h2")
                    and s.find("h2").get_text(strip=True) == "Professional Summary"), None)
    if summary:
        _sort_children(summary.find("ul"), "li", priorities)

    # Prioritize existing bullets within each role, retaining role order, title and dates.
    for role in soup.select("article.role"):
        _sort_children(role.find("ul"), "li", priorities)

    # Reorder core expertise groups and tags, retaining the original skills and CSS.
    expertise = next((s for s in soup.select("section") if s.find("h2")
                      and s.find("h2").get_text(strip=True) == "Core Expertise"), None)
    if expertise:
        groups = expertise.select("p.skill-group")
        for group in sorted(groups, key=lambda el: _relevance(el.get_text(" ", strip=True), priorities),
                            reverse=True):
            expertise.append(group)

    # Do not add employer keywords, unsupported leadership claims or synthetic achievements.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(str(soup), encoding="utf-8")
    (output_path.parent / "tailoring_manifest.json").write_text(json.dumps({
        "job_url": job["url"],
        "job_title": job["title"],
        "priority_areas": priorities,
        "method": "Reordered original verified summary, role bullets and expertise blocks",
        "facts_source": str(template_path),
        "claims_added": 0,
        "requires_human_review": True
    }, indent=2), encoding="utf-8")

    if render_pdf:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install playwright and run: playwright install chromium") from exc
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 1600}, device_scale_factor=1)
            page.goto(output_path.resolve().as_uri(), wait_until="load")
            page.emulate_media(media="print")
            page.pdf(path=str(output_path.with_suffix(".pdf")), format="A4",
                     print_background=True, prefer_css_page_size=True)
            browser.close()
