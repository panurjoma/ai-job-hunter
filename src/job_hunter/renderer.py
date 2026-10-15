"""Fact-preserving CV tailoring against the user's verified HTML template.

Never insert job-description claims into the candidate's CV. Tailoring selects
and prioritizes existing evidence only, preserving original employment facts.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from xml.etree import ElementTree

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



def _company_logo_data_uri(job: dict, template_path: Path) -> str | None:
    """Embed a verified local PNG/SVG; never fetch network images at render time."""
    relative = job.get("logo_path")
    if not relative:
        return None
    if not job.get("logo_source_url"):
        raise ValueError("logo_path requires a verified official logo_source_url")
    if not isinstance(relative, str) or not re.fullmatch(
        r"data/inbox/assets/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.(png|svg)", relative
    ):
        raise ValueError("logo_path must be a repository-local inbox asset")
    root = template_path.resolve().parent.parent
    asset = (root / relative).resolve()
    if not asset.is_relative_to((root / "data/inbox/assets").resolve()):
        raise ValueError("logo_path escapes allowed asset directory")
    raw = asset.read_bytes()
    if len(raw) > 150_000:
        raise ValueError("Logo exceeds 150 KB")
    if asset.suffix == ".png":
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid PNG logo")
        mime = "image/png"
    else:
        root_tag = ElementTree.fromstring(raw)
        allowed = {"svg", "g", "path", "rect", "circle", "ellipse", "polygon",
                   "polyline", "line", "defs", "linearGradient", "radialGradient",
                   "stop", "title", "desc"}
        for element in root_tag.iter():
            if element.tag.split("}")[-1] not in allowed:
                raise ValueError("Unsupported SVG logo element")
            for key, value in element.attrib.items():
                name = key.split("}")[-1].lower()
                if name.startswith("on") or name in ("href", "style") or "url(" in value.lower():
                    raise ValueError("Unsafe SVG logo attribute")
        mime = "image/svg+xml"
    return "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")


def render_cv(template_path: Path, output_path: Path, job: dict, render_pdf: bool = False) -> None:
    soup = BeautifulSoup(template_path.read_text(encoding="utf-8"), "html.parser")
    priorities = _priorities(job)
    logo_warning = None
    try:
        logo_uri = _company_logo_data_uri(job, template_path)
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        # A bad or unavailable logo is an observability warning, never a CV blocker.
        logo_uri = None
        logo_warning = str(exc)
    header = soup.select_one("header.header")
    if header is None:
        raise ValueError("CV template has no header")
    style = soup.new_tag("style")
    style.string = (
        ".company-logo,.company-monogram {float:right;width:58px;height:58px;margin:0 0 5px 12px;}"
        ".company-logo{object-fit:contain}.company-monogram{display:flex;align-items:center;"
        "justify-content:center;border-radius:12px;background:#e8eef7;color:#183153;font:700 20px Arial;}"
        ".target-role{font-size:10px;color:#52606d;margin-top:4px;letter-spacing:.01em}"
    )
    soup.head.append(style)
    if logo_uri:
        logo = soup.new_tag("img", src=logo_uri, alt="Target company logo")
        logo["class"] = "company-logo"
        header.insert(0, logo)
    else:
        company = str(job.get("company") or "Target company").strip()
        initials = "".join(word[0] for word in re.findall(r"[A-Za-z0-9]+", company)[:2]).upper() or "?"
        monogram = soup.new_tag("div")
        monogram["class"] = "company-monogram"
        monogram["aria-label"] = f"{company} logo unavailable"
        monogram.string = initials
        header.insert(0, monogram)
    target = soup.new_tag("div")
    target["class"] = "target-role"
    target.string = f"Target role: {job.get('title', 'Role')} · {job.get('company', 'Company')}"
    header.append(target)
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
        "company_logo_path": job.get("logo_path"),
        "company_logo_embedded": bool(logo_uri),
        "company_logo_status": "embedded" if logo_uri else "monogram_fallback",
        "company_logo_warning": logo_warning or (None if logo_uri else "No verified official logo asset"),
        "company_logo_source_url": job.get("logo_source_url"),
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
        pdf = output_path.with_suffix(".pdf")
        if not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF") or pdf.stat().st_size < 1000:
            raise RuntimeError(f"Playwright did not produce a valid PDF: {pdf}")

