# Scheduled ChatGPT task: AI Job Hunter

Use the connected GitHub repository `panurjoma/ai-job-hunter` as the authoritative source for this task.

1. Read `config/search_criteria.yaml`, `config/sources.yaml`, and the repository README at the start of every run. Never rely on stale criteria copied into the schedule.
2. Search permitted public job feeds and company career pages for newly posted or updated roles. Include AI/ML, software architecture, backend, space/aerospace, optimization, and AI/space Tech Lead roles.
3. Enforce fully remote roles and verify whether employment from the specified countries is allowed. Do not equate 'remote' with worldwide eligibility.
4. Treat annual gross salary below EUR 90,000 as disqualifying only when comparable compensation is confirmed. Mark undisclosed or ambiguous salary as unverified; do not invent it.
5. Normalize and deduplicate by canonical application URL and company/title/location. Rank against verified career-profile facts using a 0-100 score; shortlist jobs scoring >=65.
6. For each shortlisted job, preserve source URL, observed date, job description or excerpt, salary evidence, location restrictions, score and rationale.
7. If a verified master CV and HTML reference template are present, prepare factual tailored CVs without inventing achievements. If absent, report that CV generation is pending; do not fabricate a CV.
8. Use GitHub tools to propose or commit results to a dedicated results branch or PR, without overwriting concurrent changes. Do not apply for jobs.
9. Summarize new high-scoring roles and provide links to the source postings and GitHub output. If GitHub access is unavailable, report the blocker rather than claiming the repo was updated.

Do not expose secrets or personal CV details in public outputs. The repository must remain private. Avoid prohibited scraping and respect source terms and rate limits.
