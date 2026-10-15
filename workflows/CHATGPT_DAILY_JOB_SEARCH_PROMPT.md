# Daily ChatGPT Job Hunter — scheduled task prompt

Use private GitHub repository `panurjoma/ai-job-hunter` as the source of truth. At the start of every run, read `config/search_criteria.yaml`, `config/sources.yaml`, `docs/DATA_HANDOFF.md`, and this prompt.

1. Discover new or updated jobs from permitted sources for AI/ML, architecture, backend, optimization, aerospace/space and AI/space Tech Lead roles.
2. Consult available LinkedIn people search for `https://nl.linkedin.com/in/pablo-hinojosa-lopez`. **Do not claim full profile access**; use verified master CV and flag factual conflicts.
3. For each job, collect a structured object conforming to `data/inbox/example_jobs.json` schema version 1.0, with source, company, title, canonical URL, full relevant description, remote_type, eligible_countries, and salary object. Record unknown fields as unknown/null, never infer salary or eligibility. Filter obviously irrelevant jobs before submitting.
4. Commit one `data/inbox/jobs_YYYY-MM-DD.json` file to a dedicated GitHub branch and link it. Avoid overwriting concurrent work. Never commit tokens or API secrets.
5. Invoke the Python backend if a supported execution bridge is available. The existing `.github/workflows/daily-job-search.yml` accepts `workflow_dispatch` input `input_path`; **the current ChatGPT GitHub connector does not expose dispatch**, so do not pretend this was triggered. Until a verified bridge exists, report the committed inbox file and state processing is pending. Do not fabricate CV outputs.
6. Once execution is verified, retrieve `output/report.json` and tailored CV artifacts, publish to a private results branch/PR, and summarize match scores, job URLs and CV paths. Do not submit job applications.
7. Send a summary email from and to the connected Gmail account `pablohl50@gmail.com` **only if Gmail sending is available in this scheduled run**. Subject: `AI Job Hunter | YYYY-MM-DD | N new matches`. Include verified new roles, salary/eligibility status, GitHub links, CVs actually generated, errors and pending actions. If no execution occurred, explicitly label matching and CVs as pending. If Gmail is unavailable, provide the unsent draft in the task response.
8. Return concise status with jobs found, input branch/PR, processing state, actual CV count, and Gmail send state.

ChatGPT is the only daily scheduler. GitHub Actions is manual execution fallback; no automatic cron. Respect site terms, privacy and rate limits.
