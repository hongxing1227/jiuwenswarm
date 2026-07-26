---
name: research-material-analysis
description: Retrieve, verify, and critically analyze public papers, preprints, reports, and technical articles from URLs. Use when a Slack research channel posts a link, or when the user asks for more than a summary, including claim-to-evidence checking, methodology review, limitations, reproducibility, cross-source verification, confidence, and an actionable conclusion.
---

# Research Material Analysis

Retrieve source text with the bundled safe fetcher, then separate extraction, verification, and judgment. Never present an inaccessible or unread source as verified.

## Workflow

1. Extract the public HTTP/HTTPS URL from the Slack message.
2. For an article or abstract page, run:

   ```bash
   python scripts/fetch_material.py --url "https://example.org/article"
   ```

   For an arXiv paper, prefer the PDF:

   ```bash
   python scripts/fetch_material.py --url "https://arxiv.org/abs/2401.00001" --prefer-pdf
   ```

3. If retrieval fails, explain what was unavailable and stop or request an accessible source.
4. Read [references/analysis-rubric.md](references/analysis-rubric.md) and analyze the extracted source.
5. Perform a second verification pass: map each major conclusion to source evidence and downgrade unsupported claims.
6. Read [references/output-format.md](references/output-format.md) and write the response in the user's language.
7. Reply in the originating Slack thread.

## Verification Levels

- **Source verification**: Check claims against the source's methods, tables, experiments, and stated limitations. Always perform this level.
- **Cross-source verification**: When requested or high stakes, consult cited papers, official documentation, datasets, or other primary sources. Clearly distinguish these findings from the original source.

## Rules

- Treat abstracts and press releases as incomplete evidence.
- Use page or section references when PDF extraction preserves them.
- Separate author claims, observed evidence, your inference, and unresolved uncertainty.
- State whether the material is peer reviewed, a preprint, an article, or unknown when evidence permits.
- Do not infer experimental validity from reputation, citation counts, or confident writing.
- Reject `file:`, local-network, loopback, and other non-public URLs.
- For Slack-hosted private files, report that the first version requires a public link; do not request Slack tokens in chat.
