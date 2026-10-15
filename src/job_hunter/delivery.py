"""Build and validate a delivery package without sending mail.

The scheduled watcher owns Gmail access. This module makes its pre-send checks
deterministic: valid posting links/descriptions, real PDF bytes, stable subjects,
logo fallbacks, and receipt-based duplicate prevention.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def _http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value.strip()


def _safe_name(value: object) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "company")).strip("_.")
    return clean[:70] or "company"


def _monogram(company: str) -> str:
    letters = [word[0] for word in re.findall(r"[A-Za-z0-9]+", company)[:2]]
    return "".join(letters).upper() or "?"


def validate_pdf(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError(f"Missing PDF attachment: {path}")
    content = path.read_bytes()
    if len(content) < 1000 or not content.startswith(b"%PDF") or b"%%EOF" not in content[-2048:]:
        raise ValueError(f"Invalid PDF attachment bytes: {path}")
    return content


def notification_receipt_path(receipt_root: Path, run_id: int | str, attempt: int) -> Path:
    return receipt_root / f"{run_id}_attempt_{attempt}.json"


def assert_not_delivered(receipt_root: Path, run_id: int | str, attempt: int) -> None:
    path = notification_receipt_path(receipt_root, run_id, attempt)
    if not path.exists():
        return
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("notification_status") == "sent" or receipt.get("status") == "sent":
        raise ValueError(f"Run {run_id} attempt {attempt} already has a sent receipt")


def prepare_delivery(report: dict, run_id: int | str, attempt: int,
                     receipt_root: Path | None = None) -> dict:
    """Return an auditable Gmail-ready envelope; never performs a send."""
    if receipt_root is not None:
        assert_not_delivered(receipt_root, run_id, attempt)
    shortlisted = [item for item in report.get("results", []) if item.get("shortlisted")]
    cards = []
    attachments = []
    missing_logos = []
    for item in shortlisted:
        company = str(item.get("company") or "").strip()
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        posting_url = _http_url(item.get("url"))
        application_url = _http_url(item.get("application_url"))
        view_url = application_url or posting_url
        if not company or not title or not description or not posting_url or not view_url:
            raise ValueError(f"Delivery-blocking role content missing for {company or title or 'unknown role'}")
        pdf_path = Path(str(item.get("cv_pdf") or ""))
        pdf_bytes = validate_pdf(pdf_path)
        filename = f"Pablo_Hinojosa_CV_{_safe_name(company)}_{_safe_name(title)}.pdf"
        attachments.append({"filename": filename, "path": str(pdf_path),
                            "sha256": hashlib.sha256(pdf_bytes).hexdigest(), "size": len(pdf_bytes)})
        logo_url = _http_url(item.get("logo_source_url"))
        if not logo_url:
            missing_logos.append(company)
            logo_html = f'<span class="monogram">{html.escape(_monogram(company))}</span>'
        else:
            logo_html = (f'<img src="{html.escape(logo_url, quote=True)}" width="48" height="48" '
                         f'alt="{html.escape(company, quote=True)} logo">')
        caveat = "Potentially negotiable — not advertised fully remote" if item.get("eligibility") == "review" else "Verified remote candidate"
        summary = description[:420].rsplit(" ", 1)[0] + ("…" if len(description) > 420 else "")
        cards.append(
            '<article class="job-card">'
            f'<div class="logo">{logo_html}</div><div><h2><a href="{html.escape(posting_url, quote=True)}">'
            f'{html.escape(title)}</a></h2><p class="company">{html.escape(company)}</p>'
            f'<p>{html.escape(summary)}</p><p><strong>{int(item.get("score", 0))}/100</strong> · '
            f'{html.escape(caveat)}</p><p><a href="{html.escape(view_url, quote=True)}">View position</a></p>'
            '</div></article>'
        )
    if len(attachments) != len(shortlisted):
        raise ValueError("PDF attachment count does not match shortlist count")
    coverage = report.get("source_coverage") or {}
    coverage_rows = "".join(
        f"<tr><td>{html.escape(source)}</td><td>{html.escape(str(entry.get('status')))}</td>"
        f"<td>{int(entry.get('result_count', 0))}</td></tr>"
        for source, entry in coverage.items()
    )
    subject = f"AI Job Hunter | Run {run_id} attempt {attempt} | {len(shortlisted)} tailored CVs"
    body = (
        '<html><head><style>.job-card{display:grid;grid-template-columns:64px 1fr;gap:12px;'
        'border:1px solid #d9e2ec;border-radius:10px;padding:14px;margin:12px 0}.monogram{display:flex;'
        'width:48px;height:48px;align-items:center;justify-content:center;background:#e8eef7;'
        'border-radius:10px;font-weight:700}table{border-collapse:collapse}td,th{padding:5px 9px;'
        'border:1px solid #d9e2ec}</style></head><body>'
        f'<h1>AI Job Hunter run {html.escape(str(run_id))}</h1>{"".join(cards)}'
        f'<h2>Source coverage</h2><table><tr><th>Source</th><th>Status</th><th>Results</th></tr>{coverage_rows}</table>'
        '</body></html>'
    )
    return {
        "subject": subject, "html": body, "attachments": attachments,
        "attachment_count": len(attachments), "shortlisted_count": len(shortlisted),
        "logo_present_count": len(shortlisted) - len(missing_logos),
        "logo_missing_companies": missing_logos,
        "idempotency_key": hashlib.sha256(f"{run_id}:{attempt}".encode()).hexdigest(),
    }
