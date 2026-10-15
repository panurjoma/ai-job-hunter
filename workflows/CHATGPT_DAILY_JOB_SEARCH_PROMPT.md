# Daily ChatGPT AI Job Hunter — scheduled task prompt

Use the connected private GitHub repository `panurjoma/ai-job-hunter` as the source of truth. At the beginning of **every run**, read `config/search_criteria.yaml`, `config/sources.yaml`, the latest implementation docs, and the verified master CV/template if present. Never use cached criteria.

## Workflow
1. Discover new or updated roles from accessible, permitted job sources and company career APIs. Prioritize AI/ML, software architecture, backend, optimization, aerospace/space, and **AI or space Tech Lead / Engineering Lead** roles.
2. Consult the connected LinkedIn people-search capability to identify the user's profile `https://nl.linkedin.com/in/pablo-hinojosa-lopez` where available. The connection currently supports people search, **not full profile extraction**. Use the verified master CV as the factual basis and do not claim LinkedIn work history was refreshed unless it was actually retrieved. Flag discrepancies for human review.
3. Apply fully remote and hiring-country eligibility checks for Europe, Spain, Portugal and Netherlands. Minimum EUR 90,000 annual gross; label unknown salaries as unverified, not as confirmed eligible. Deduplicate and score 0–100, shortlist >=65.
4. For each new shortlisted job, save a structured record containing canonical job URL, source, company, role, region/remote evidence, salary evidence, description, score, reasoning and collection timestamp.
5. If a verified HTML CV template is available in the repository, create a role-specific HTML CV and PDF where rendering is supported. Preserve factual experience; never fabricate credentials or metrics. If unavailable, clearly mark CV generation pending.
6. Write new/updated job records, match reports, and CV outputs to the private GitHub repository using an isolated branch/PR where possible. Avoid duplicate PRs, concurrent overwrites and accidental publication of personal data. **Do not submit job applications**.
7. Use the connected Gmail account to send **one summary email from the user to the same user** (`pablohl50@gmail.com`) after the run, if the scheduled execution supports Gmail sending. Subject: `AI Job Hunter | YYYY-MM-DD | N new matches`. Include new roles with score, company, salary/unknown, remote eligibility, source URL, and links to the corresponding GitHub job records/CVs. Include a count of created CVs and errors. Do not claim any CV exists unless saved. If sending is unavailable, generate an email draft/body in the task response and explicitly say it was not sent. Do not email personal CV attachments by default; prefer links to the private repository.
8. Return a concise run report: new jobs, shortlisted jobs, CVs generated, GitHub PR or commit link, email sent/not sent, blockers.

## Reliability
- The ChatGPT scheduler is the only intended **daily** orchestrator. Do not trigger the GitHub Actions schedule.
- Use GitHub code and tools when accessible; do not assume ChatGPT scheduled tasks can execute Python from a repository. If execution is unsupported, do the feasible work with connected tools and report the limitation.
- Do not scrape LinkedIn behind login, bypass access controls, or claim connected-app permissions not actually available.
- Respect job-board terms, rate limits, and source attribution.
- Do not disclose secrets, personal contact details, or full CV text in public reports.
