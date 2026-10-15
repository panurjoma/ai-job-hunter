# ChatGPT → GitHub → Python handoff

The ChatGPT scheduled task commits one JSON payload to `data/inbox/jobs_YYYY-MM-DD.json` (schema v1.0). Each item needs `source`, `company`, `title`, `url`, `description`, `remote_type`, `eligible_countries` and `salary`. Missing remote/country/salary evidence must be represented as unknown/null, never guessed. `salary` shape: `{min, max, currency, period}`.

The Python backend runs `python -m job_hunter.cli --input data/inbox/jobs_YYYY-MM-DD.json --output output/YYYY-MM-DD --pdf`. It normalizes, deduplicates within the batch by canonical URL, checks remote/salary/geography, scores, and generates a distinct HTML/PDF CV for each shortlisted job using verified source text. CV tailoring currently **reorders verified summary bullets**; it does not yet rewrite individual accomplishments or perform cross-run historical deduplication.

## Execution options
- **Recommended**: ChatGPT commits JSON then dispatches a `workflow_dispatch` GitHub Action with the exact input path. The Action executes the backend and uploads results as artifacts. A further write-enabled step or connected GitHub call is needed to persist results to a branch/PR. Verify scheduled ChatGPT's GitHub dispatch capability before activation.
- **Alternative**: ChatGPT commits JSON to an inbox branch, then a narrowly scoped `push` GitHub Action reacts to `data/inbox/*.json`. This is a robust execution bridge without relying on a dispatch connector, but must restrict branch/path and avoid recursive triggers.
- **Alternative**: ChatGPT calls an authenticated external job-processing API, requiring deployment and secrets.

ChatGPT/Gmail/LinkedIn OAuth connectors are **not inherited** by GitHub Actions. The daily ChatGPT task sends its Gmail summary with connected Gmail permissions, if available. GitHub Actions stays manual-only unless the input-trigger architecture is explicitly approved.

Never commit OAuth tokens or private keys. Do not claim a job application was submitted; this pipeline only prepares CVs.
