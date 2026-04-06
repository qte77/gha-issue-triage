# gha-issue-triage

![Version](https://img.shields.io/badge/version-0.1.0-8A2BE2)
[![Tests](https://github.com/qte77/gha-issue-triage/actions/workflows/test.yml/badge.svg)](https://github.com/qte77/gha-issue-triage/actions/workflows/test.yml)
[![Lint](https://github.com/qte77/gha-issue-triage/actions/workflows/ruff.yml/badge.svg)](https://github.com/qte77/gha-issue-triage/actions/workflows/ruff.yml)

AI-powered issue triage GitHub Action. Detects duplicates, scores relevance,
analyzes feasibility, and auto-labels issues.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `GH_TOKEN` | Yes | — | GitHub token for gh CLI |
| `AI_TOKEN` | No | `github.token` | GitHub Models API token |
| `MODEL` | No | `openai/gpt-4.1` | LLM model |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key (alternative backend) |
| `MAX_DUPLICATES` | No | `10` | Max duplicate candidates |
| `SIMILARITY_THRESHOLD` | No | `0.6` | Fuzzy match threshold (0-1) |

## Usage

```yaml
name: Issue Triage
on:
  issues:
    types: [opened, edited]

jobs:
  triage:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: read
    steps:
      - uses: qte77/gha-issue-triage@v0
        with:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Features

- **Duplicate Detection** — Fuzzy matches new issues against existing ones using `difflib.SequenceMatcher`
- **Relevance Scoring** — LLM-based scoring against repo scope (README.md, CLAUDE.md)
- **Feasibility Analysis** — Complexity estimation with codebase file context
- **Auto-Labeling** — Applies labels: `duplicate`, `bug`, `feature`, `enhancement`, `good-first-issue`, `needs-discussion`, `invalid`

## License

[MIT](LICENSE)
