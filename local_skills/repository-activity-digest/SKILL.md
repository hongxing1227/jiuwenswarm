---
name: repository-activity-digest
description: Fetch and analyze recently created or updated GitHub issues and pull requests, then produce an evidence-linked engineering digest with themes, risks, blockers, and recommended actions. Use for scheduled repository monitoring, daily or weekly engineering updates, triage summaries, or requests about activity during the last N hours.
---

# Repository Activity Digest

Use the bundled fetcher for deterministic GitHub API access and pagination. Analyze its JSON output; do not invent repository activity.

## Workflow

1. Determine the repository (`owner/name`), time window, activity mode, and target audience.
2. Run:

   ```bash
   python scripts/fetch_repository_activity.py \
     --repo owner/name \
     --hours 24 \
     --mode created \
     --state-file memory/repository-activity-owner-name.json
   ```

3. If the command fails, report the error and stop. Never replace missing API data with guesses.
4. Read [references/report-format.md](references/report-format.md).
5. Group related items, identify risks and blockers, and connect each conclusion to issue or pull-request URLs.
6. State the exact UTC window and whether state recovery extended it.
7. Write the final digest in the user's language.

## Rules

- Treat `created` as the default for “new issues and pull requests”; use `updated` only when requested.
- Prefer `GITHUB_TOKEN` from the environment. Never print or persist the token.
- Keep the state file outside the skill folder so skill upgrades do not erase the watermark.
- Distinguish facts from inference. Label weak signals and avoid judging code quality without patch evidence.
- If no items match, return a short “no new activity” result with the inspected window.
- For deeper PR analysis, fetch referenced patches or CI evidence with available tools before claiming a regression or failure.

## Scheduled Use

Create a JiuwenSwarm cron job with `targets: slack`. Put the repository, hours, mode, state-file path, and desired analysis in the cron description. The Slack instance must configure `default_channel_id`.
