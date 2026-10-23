"""Reliable Gmail delivery from persisted run outputs; stdlib only.

Requires GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN and
GMAIL_SENDER; OAuth refresh token must have gmail.send and gmail.readonly scopes.
"""
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from job_hunter.delivery import prepare_delivery, validate_pdf

ROOT = Path("data")
RECIPIENT = os.getenv("JOB_HUNTER_RECIPIENT", "pablohl50@gmail.com")
RECEIPTS = ROOT / "notifications"


def request_json(url, token=None, payload=None, form=False):
    data = None
    headers = {}
    if payload is not None:
        data = urllib.parse.urlencode(payload).encode() if form else json.dumps(payload).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=35) as response:
        return json.load(response)


def access_token():
    values = {name: os.environ[name] for name in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")}
    response = request_json("https://oauth2.googleapis.com/token", payload={
        "client_id": values["GMAIL_CLIENT_ID"],
        "client_secret": values["GMAIL_CLIENT_SECRET"],
        "refresh_token": values["GMAIL_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, form=True)
    return response["access_token"]


def sent_matches(token, run_id, attempt):
    query = f'in:sent to:{RECIPIENT} subject:"AI Job Hunter" "{run_id}"'
    result = request_json("https://gmail.googleapis.com/gmail/v1/users/me/messages?" +
                          urllib.parse.urlencode({"q": query, "maxResults": 100}), token)
    matches = []
    for item in result.get("messages", []):
        detail = request_json(f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{item["id"]}?format=metadata&metadataHeaders=Subject', token)
        headers = detail.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
        if re.search(rf'\bRun {re.escape(str(run_id))}\b', subject, re.I) and (
                f"attempt {attempt}" in subject or attempt == 1):
            matches.append({"id": item["id"], "subject": subject})
    return matches


def make_message(package, sender):
    msg = EmailMessage()
    msg["To"] = RECIPIENT
    msg["From"] = sender
    msg["Subject"] = package["subject"]
    msg["X-Job-Hunter-Idempotency"] = package["idempotency_key"]
    msg.set_content("AI Job Hunter results: open this message in an HTML-capable email client.")
    msg.add_alternative(package["html"], subtype="html")
    for attachment in package["attachments"]:
        data = validate_pdf(Path(attachment["path"]))
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=attachment["filename"])
    return msg


def pending_runs():
    receipts = sorted((ROOT / "runs").glob("*_attempt_*.json"), key=lambda p: p.stat().st_mtime)
    for path in receipts:
        receipt = json.loads(path.read_text())
        if receipt.get("status") != "success":
            continue
        run_id, attempt = receipt["run_id"], receipt["attempt"]
        notification = RECEIPTS / f"{run_id}_attempt_{attempt}.json"
        if notification.exists() and json.loads(notification.read_text()).get("notification_status") == "sent":
            continue
        yield receipt, notification


def deliver(receipt, notification, token):
    run_id, attempt = receipt["run_id"], receipt["attempt"]
    matches = sent_matches(token, run_id, attempt)
    if matches:
        print(f"Run {run_id} already exists in Gmail Sent ({matches[0]['id']}); skipping duplicate")
        return
    root = ROOT / "generated" / str(run_id) / f"attempt_{attempt}"
    packages = []
    for report_path in sorted(root.glob("*/report.json")):
        report = json.loads(report_path.read_text())
        for item in report.get("results", []):
            if item.get("shortlisted"):
                item["cv_pdf"] = str(report_path.parent / "jobs" / item["id"] / "tailored_cv.pdf")
        packages.append(prepare_delivery(report, run_id, attempt))
    if not packages:
        raise RuntimeError(f"Missing persisted report for run {run_id}")
    # All batches in one run must be sent in one digest; reject ambiguous multi-batch input.
    if len(packages) != 1:
        raise RuntimeError(f"Multiple batches in run {run_id}; refusing partial delivery")
    package = packages[0]
    sender = os.environ["GMAIL_SENDER"]
    msg = make_message(package, sender)
    if len(list(msg.iter_attachments())) != package["attachment_count"]:
        raise RuntimeError("Outgoing MIME PDF count mismatch")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")
    sent = request_json("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                        token, {"raw": raw})
    if not sent.get("id"):
        raise RuntimeError("Gmail send returned no message ID")
    notification.parent.mkdir(parents=True, exist_ok=True)
    notification.write_text(json.dumps({
        "schema_version": "1.0", "run_id": run_id, "attempt": attempt,
        "notification_status": "sent", "gmail_message_id": sent["id"],
        "recipient": RECIPIENT, "subject": package["subject"],
        "attachment_count": package["attachment_count"],
        "shortlisted_count": package["shortlisted_count"],
        "logo_present_count": package["logo_present_count"],
        "logo_missing_companies": package["logo_missing_companies"],
        "corrected_report": False,
        "sent_at": datetime.now(timezone.utc).isoformat()
    }, indent=2) + "\n")
    print(f"Sent run {run_id}, Gmail message {sent['id']}")


def main():
    runs = list(pending_runs())
    if not runs:
        print("No pending successful runs")
        return
    token = access_token()
    failed = []
    for receipt, notification in runs:
        try:
            deliver(receipt, notification, token)
        except Exception as exc:
            failed.append(f"{receipt['run_id']}: {exc}")
            print(f"Delivery failed: {failed[-1]}", file=sys.stderr)
    if failed:
        raise SystemExit("; ".join(failed))


if __name__ == "__main__":
    main()
