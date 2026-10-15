# ChatGPT Scheduled Task — AI Job Hunter

Run once daily. Use the connected **private** GitHub repository `panurjoma/ai-job-hunter` as source of truth. At every run read `config/search_criteria.yaml`, `config/sources.yaml`, `docs/DATA_HANDOFF.md` and the verified CV template.

## Priority sources (five)
1. LinkedIn Jobs — public/authorized listings; LinkedIn people-search connector can identify a profile but is **not** a LinkedIn Jobs connector.
2. Wellfound — startup and AI engineering roles.
3. Himalayas — location-aware remote roles.
4. We Work Remotely — engineering and technical leadership.
5. Remote OK — distributed software/AI jobs.

Also search relevant official Greenhouse, Lever and Ashby company boards when useful; do not count them as additional top-five job websites. Respect robots, login restrictions, rate limits and site terms. Do not invent job postings or scrape private pages.

## Extract and hand off
1. Seek remote-only senior/staff/principal/tech-lead/architect roles in AI/ML, backend, optimization and space/aerospace, hiring from Spain/Portugal/Netherlands/Europe and with >=EUR 90k gross salary when confirmed. Mark unknown salary/eligibility for review. Minimum matching threshold 65.
2. Obtain the **full original job description** where permitted. Capture responsibilities, mandatory requirements, preferred qualifications, technical stack, leadership scope, compensation, remote policy and hiring geography. Remove navigation/cookie boilerplate without summarizing away requirements. Never invent missing details. When only a snippet exists, mark it partial/truncated and preserve source URL.
3. Produce JSON exactly following `data/inbox/example_jobs.json` **schema_version 1.1** and `docs/DATA_HANDOFF.md`. Preserve original `description` plus structured `description_sections`, source/evidence URLs, timestamps, salary currency/period and confidence flags.
4. **Commit a NEW JSON file to `main`** at `data/inbox/jobs_YYYY-MM-DD_HHMMSS.json`. The GitHub `push` workflow `.github/workflows/daily-job-search.yml` will detect this path and run Python. The workflow must first be merged into `main`. If `main` is protected or push fails, report the blocker rather than silently committing to a non-triggering branch.
5. Where available, inspect the GitHub Actions run status and its `matched-jobs-and-cvs-<run_id>` artifact. The artifact includes match reports, one HTML/PDF CV per shortlisted job and a tailoring provenance manifest. **Do not claim a run completed, an output was committed, or a CV was created without verifying it.** Outputs currently live in workflow artifacts, not permanent repository commits.
6. Check the user's LinkedIn profile `https://nl.linkedin.com/in/pablo-hinojosa-lopez` only to the extent supported by connected tools; people search alone does not refresh employment details. Never invent CV facts.
7. Send one email **from and to** the connected Gmail account `pablohl50@gmail.com` if Gmail sending is supported by this scheduled run. Subject `AI Job Hunter | YYYY-MM-DD | N new matches`. Include verified roles, source URLs, salary/remote evidence, match scores when actually processed, GitHub workflow/artifact link, CV count and any pending/error state. If no result was verified, say 'processing pending' instead of inventing a score. If Gmail is unavailable, include an unsent summary in the task response.
8. Return a concise run report. Do not auto-apply to jobs, and never expose credentials or the user's private CV in public messages.

GitHub has no daily cron: the ChatGPT scheduled task is the only time-based scheduler. Each new JSON inbox commit is an **event** that triggers Python processing. Confirm this capability with a real post-merge commit before treating the automation as production-ready.
