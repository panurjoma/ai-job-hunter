"""Tailor only verified statements already in the source HTML; preserve CSS/layout."""
from __future__ import annotations

from pathlib import Path
from bs4 import BeautifulSoup

TERMS = {
    "ai": ("ai", "machine learning", "llm", "rag", "agent", "retrieval", "reinforcement"),
    "space": ("space", "satellite", "aerospace", "constellation", "navigation", "gnss"),
    "architecture": ("architect", "distributed", "microservices", "kafka", "system design"),
    "optimization": ("optimization", "allocation", "planning", "scheduling", "numerical"),
}


def render_cv(template_path: Path, output_path: Path, job: dict, render_pdf: bool = False) -> None:
    soup = BeautifulSoup(template_path.read_text(encoding="utf-8"), "html.parser")
    title = job["title"].lower()
    description = job["description"].lower()
    priorities = sorted(TERMS, key=lambda area: (
        sum(t in title for t in TERMS[area]) * 3 + sum(t in description for t in TERMS[area])), reverse=True)
    # Reorder existing verified summary bullets; no invented claims.
    section = next((s for s in soup.select("section") if s.find("h2") and
                    s.find("h2").get_text(strip=True) == "Professional Summary"), None)
    if section and section.find("ul"):
        ul = section.find("ul")
        bullets = list(ul.find_all("li", recursive=False))
        def relevance(li):
            body = li.get_text(" ", strip=True).lower()
            return sum((len(priorities) - i) * sum(term in body for term in TERMS[area])
                       for i, area in enumerate(priorities))
        for li in sorted(bullets, key=relevance, reverse=True):
            ul.append(li)
    # Preserve user's original name, role titles, employment dates, claims, and contact details.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(str(soup), encoding="utf-8")
    if render_pdf:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install playwright and run: playwright install chromium") from exc
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(output_path.resolve().as_uri(), wait_until="load")
            page.pdf(path=str(output_path.with_suffix(".pdf")), format="A4",
                     print_background=True, prefer_css_page_size=True)
            browser.close()
