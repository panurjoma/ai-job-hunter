# Implementation plan

## Current MVP
- Configurable search criteria including AI and space tech-lead roles
- Remotive public API ingestion; GitHub Actions scheduled and manual discovery
- Raw JSON results uploaded as a workflow artifact
- ChatGPT scheduled-task prompt in workflows/

## Next milestones
1. Implement Greenhouse, Lever and Ashby company-board connectors with tests.
2. Normalize postings, enforce remote-country eligibility, salary conversion and unknown-salary review.
3. Persist deduplicated postings and historical status.
4. Add reproducible rule-based scoring and optional LLM semantic scoring >=65.
5. Import verified LinkedIn profile export or user-authorized data; do not scrape private LinkedIn.
6. After receiving HTML CV template, implement factual tailoring and PDF/DOCX rendering.
7. Add results branch/PR publication and human review, keeping CVs private.

The GitHub workflow currently collects raw data only. It does not claim to match or generate CVs.
