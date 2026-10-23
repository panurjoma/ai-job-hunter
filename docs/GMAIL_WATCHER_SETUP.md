# Automated Gmail delivery watcher

The job processing workflow persists PDFs and a run receipt. A separate GitHub
Actions workflow, `.github/workflows/deliver-job-emails.yml`, retries delivery
hourly and can also be launched manually with **Run workflow**. It reads all
successful runs lacking a sent notification, validates the persisted PDFs and
posting details, sends the complete HTML digest with actual PDF attachments,
then commits `data/notifications/<run>_attempt_<attempt>.json` only after Gmail
returns a message ID. If Gmail or the report is invalid, the run fails loudly.

## One-time required setup

In GitHub repository **Settings → Secrets and variables → Actions**, configure:

- `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET`: OAuth client credentials.
- `GMAIL_REFRESH_TOKEN`: refresh token for the sender account, authorized
  with `https://www.googleapis.com/auth/gmail.send` and
  `https://www.googleapis.com/auth/gmail.readonly`.
- `GMAIL_SENDER`: authenticated sender email address.

Enable Gmail API in the associated Google Cloud project. Keep credentials in
GitHub Actions secrets; never commit tokens. The workflow has no way to
authenticate until these secrets are configured. The default recipient is
`pablohl50@gmail.com`.

## Reliability

- A successful pipeline run does **not** imply email delivery; only Gmail's
  returned message ID confirms delivery.
- Gmail Sent is queried before every send, even when the repository receipt is
  absent, to prevent duplicate emails after a crash or Git push failure.
- Missing official logos are rendered as monograms; they never prevent delivery.
- Missing role descriptions, invalid posting URLs, or absent/invalid PDF bytes
  stop the digest rather than silently dropping jobs.
- Every successful run is processed independently. Runs with multiple batches
  are currently rejected for manual review rather than partially delivered.
- The watcher retries hourly. Failed sends do not write a sent receipt.
- A confirmed Gmail send followed by a failed Git receipt push is **not**
  automatically reconstructed as a receipt; the watcher skips duplicates and
  reports the reconciliation gap. Inspect Gmail Sent and record it manually.
- This workflow never performs a new job search or applies to vacancies.

**Deployment:** Merge the PR after CI passes, configure the four secrets,
then use Actions → Deliver AI Job Hunter emails → Run workflow to test. The
scheduler only runs from the default branch after merge.
