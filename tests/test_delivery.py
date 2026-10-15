import json
from pathlib import Path

import pytest

from job_hunter.delivery import assert_not_delivered, prepare_delivery, validate_pdf


def _pdf(path: Path):
    path.write_bytes(b"%PDF-1.7\n" + b"x" * 1100 + b"\n%%EOF")


def test_delivery_validates_attachments_and_uses_logo_fallback(tmp_path):
    pdf = tmp_path / "cv.pdf"
    _pdf(pdf)
    report = {
        "source_coverage": {"linkedin": {"status": "searched", "result_count": 1}},
        "results": [{"shortlisted": True, "company": "Acme", "title": "AI Engineer",
                     "description": "Build production AI systems with Python for a remote European team.",
                     "url": "https://linkedin.com/jobs/view/123", "application_url": "https://acme.test/jobs/1",
                     "score": 85, "eligibility": "eligible", "cv_pdf": str(pdf)}],
    }
    delivery = prepare_delivery(report, 123, 1)
    assert delivery["attachment_count"] == 1
    assert delivery["logo_missing_companies"] == ["Acme"]
    assert "View position" in delivery["html"]
    assert "Run 123 attempt 1" in delivery["subject"]


def test_delivery_rejects_fake_pdf(tmp_path):
    fake = tmp_path / "cv.pdf"
    fake.write_text("not a pdf")
    with pytest.raises(ValueError, match="Invalid PDF"):
        validate_pdf(fake)


def test_sent_receipt_prevents_duplicate(tmp_path):
    receipt = tmp_path / "123_attempt_1.json"
    receipt.write_text(json.dumps({"notification_status": "sent"}))
    with pytest.raises(ValueError, match="already has a sent receipt"):
        assert_not_delivered(tmp_path, 123, 1)
