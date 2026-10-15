# Notification delivery receipts

After Gmail confirms a report email for a terminal GitHub Actions run, ChatGPT commits `RUN_ID_attempt_ATTEMPT.json` to this folder. Before sending, check existing receipts **and Gmail Sent** for that run identifier. Missing receipt means unconfirmed, not definitely unsent. Store only metadata (recipient, timestamp, message ID, workflow URL), never private email content or OAuth credentials. A failed receipt commit must be flagged for reconciliation. Never delete receipts.
