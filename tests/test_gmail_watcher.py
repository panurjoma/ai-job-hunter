import json
from email import message_from_bytes
from pathlib import Path

import pytest

from job_hunter.gmail_watcher import make_message, pending_runs, sent_matches


def test_mime_contains_one_pdf_per_shortlisted_job(tmp_path):
    path = tmp_path / "cv.pdf"
    path.write_bytes(b"%PDF-1.7\n" + b"x" * 1200 + b"\n%%EOF")
    package = {
        "subject": "AI Job Hunter | Run 123 attempt 1 | 1 tailored CVs",
        "html": "<html><body><a href='https://example.org/jobs/1'>View position</a></body></html>",
        "idempotency_key": "abc",
        "attachment_count": 1,
        "attachments": [{"filename": "CV_Acme.pdf", "path": str(path)}],
    }
    msg = make_message(package, "sender@example.org")
    parsed = message_from_bytes(msg.as_bytes())
    assert parsed.get_content_type() == "multipart/mixed"
    assert [part.get_filename() for part in parsed.walk() if part.get_filename()] == ["CV_Acme.pdf"]
    assert "View position" in msg.get_body(preferencelist=("html",)).get_content()


def test_pending_runs_excludes_sent_and_failed(monkeypatch, tmp_path):
    from job_hunter import gmail_watcher
    monkeypatch.setattr(gmail_watcher, "ROOT", tmp_path)
    monkeypatch.setattr(gmail_watcher, "RECEIPTS", tmp_path / "notifications")
    (tmp_path / "runs").mkdir()
    (tmp_path / "notifications").mkdir()
    for run, status in [(101, "success"), (102, "failure"), (103, "success")]:
        (tmp_path / "runs" / f"{run}_attempt_1.json").write_text(json.dumps({
            "run_id": run, "attempt": 1, "status": status
        }))
    (tmp_path / "notifications" / "103_attempt_1.json").write_text(
        json.dumps({"notification_status": "sent"})
    )
    assert [item[0]["run_id"] for item in pending_runs()] == [101]


def test_sent_lookup_matches_run_not_other_subject(monkeypatch):
    from job_hunter import gmail_watcher
    def fake_request(url, token=None, payload=None, form=False):
        if "messages?" in url:
            return {"messages": [{"id": "a"}, {"id": "b"}]}
        if "/a?" in url:
            return {"payload": {"headers": [{"name": "Subject", "value": "AI Job Hunter | Run 123 attempt 1"}]}}
        return {"payload": {"headers": [{"name": "Subject", "value": "AI Job Hunter | Run 1234 attempt 1"}]}}
    monkeypatch.setattr(gmail_watcher, "request_json", fake_request)
    assert [m["id"] for m in sent_matches("token", 123, 1)] == ["a"]
