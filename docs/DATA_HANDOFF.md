# ChatGPT → GitHub → Python: event-driven inbox contract

**ChatGPT is the daily scheduler.** It writes a validated JSON payload to the **default branch `main`** under `data/inbox/jobs_YYYY-MM-DD_HHMMSS.json`. This path-specific GitHub `push` event runs `.github/workflows/daily-job-search.yml`. No GitHub cron or workflow dispatch tool is required.

**Important:** the workflow must first be merged into `main` to be active for commits to `main`. ChatGPT must not commit inbox files to a separate branch expecting the main-only trigger to run. GitHub Actions runs under GitHub's identity; it cannot inherit ChatGPT's Gmail or LinkedIn OAuth credentials.

## Schema v1.1
See `data/inbox/example_jobs.json` for the canonical example. Each job must contain:
- Identity: `source`, `source_job_id` (if available), `company`, `title`, `url`, `application_url`, `source_url`.
- Timestamps: `posted_at` (if published), `observed_at`, `description_captured_at` in UTC ISO 8601.
- Remote: `remote_type`, `remote_evidence`, `eligible_countries`, `eligible_countries_evidence`. Unknown is **not** confirmed remote/country eligibility.
- Compensation: `salary` object with `min`, `max`, `currency`, `period`, `compensation_type`, `evidence`; use null for unknown, not fabricated values.
- Description: `description` as a faithful, readable full text extraction; `description_sections` with responsibilities, requirements, preferred, benefits arrays; `description_language`, `description_completeness` (`full`, `partial`, `unknown`), `description_source_url`, `description_truncated`, `description_notes`. Keep qualifications distinct from benefits, and preserve must-have vs nice-to-have wording.
- Context: `employment_type`, `seniority` where known.

## Description quality
Use the original company posting when possible. Preserve substantive responsibilities, stack, leadership scope, seniority, reporting line, remote location restrictions and compensation evidence. Strip navigation, cookies and marketing boilerplate. Never generate requirements or invent missing details. If only a snippet is accessible, set `description_completeness=partial` and `description_truncated=true`; mark eligibility unknown as needed. Retain source URLs for audit. Avoid sending HTML scripts, personal identifiers or tokens.

## Processing
`python -m job_hunter.cli --input data/inbox/jobs_YYYY-MM-DD_HHMMSS.json --output output/<batch> --pdf`

The pipeline deduplicates within a batch, validates eligibility, ranks jobs, and creates a separate role-prioritized HTML/PDF CV per shortlist entry. It does **not** auto-apply. The Action stores output as private workflow artifacts for 30 days; **artifacts are not commits to GitHub source history**. The ChatGPT task can send its Gmail report after it verifies the run/artifact state, but must not claim completion if it cannot inspect the result.

## Security and operational constraints
- This workflow uses `contents: read` and does not push output commits, preventing recursive workflow triggers.
- Keep the repo private: inbox files include job descriptions and the master CV contains personal details.
- New JSON file names per run prevent silent overwrite. Commits to `main` can be restricted by branch protection; if protected, use a dedicated ingestion branch and update the workflow trigger accordingly.
- GitHub's `push` path filtering requires a workflow file present on the pushed branch. Test with a real commit after merging the PR.
- Existing score is deterministic keyword matching, not calibrated ML; review high-scoring jobs manually. Historical deduplication and semantic CV rewriting remain future improvements.

## Company maturity filter
ChatGPT should investigate the employer, not just the vacancy: founded year, years actively operating, whether a real product/service exists, credible customers or sustained operations, reputable parent company, and funding/runway evidence when public. Save the structured `company_profile` shown in the example payload with supporting evidence URLs. **Small size is not a rejection criterion.** Prefer companies with roughly 3+ years of demonstrable operations; a younger business may still qualify if it has unusually strong evidence of established commercial operations or backing. Explicitly unproven newly created companies should be rejected; unknown maturity goes to review, never invent evidence. The Python backend enforces the verified unproven exclusion and flags missing evidence for review.
