# gha-issue-triage

![Version](https://img.shields.io/badge/version-0.1.1-8A2BE2)
![License](https://img.shields.io/badge/license-MIT-blue)
[![Tests](https://github.com/qte77/gha-issue-triage/actions/workflows/test.yml/badge.svg)](https://github.com/qte77/gha-issue-triage/actions/workflows/test.yml)
![CodeFactor](https://www.codefactor.io/repository/github/qte77/gha-issue-triage/badge)
![Dependabot](https://img.shields.io/badge/dependabot-enabled-025e8c)
[![Ruff](https://github.com/qte77/gha-issue-triage/actions/workflows/ruff.yml/badge.svg)](https://github.com/qte77/gha-issue-triage/actions/workflows/ruff.yml)

AI-powered issue triage GitHub Action. Detects duplicates, scores relevance,
analyzes feasibility, and auto-labels issues.

## What it does

1. **Duplicate Detection** — Fuzzy matches new issues against existing ones using `difflib.SequenceMatcher`
2. **Relevance Scoring** — LLM-based scoring against repo scope (README.md, CLAUDE.md)
3. **Feasibility Analysis** — Complexity estimation with codebase file context
4. **Auto-Labeling** — Applies labels: `duplicate`, `bug`, `feature`, `enhancement`, `good-first-issue`, `needs-discussion`, `invalid`

## Inputs

| Name | Required | Default | Description |
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

## Try it in this repo

This repo dogfoods the action via [`.github/workflows/self-triage.yml`](.github/workflows/self-triage.yml). Add the `triage/run` label to any issue and the action triages it on the next `issues` event. Side effects: label create/add only — no comments.

## Choosing a model

`MODEL` defaults to `openai/gpt-4.1` (GitHub Models). Issue triage is a small/fast model workload — swap to a cheaper or faster model with a one-line caller change. No code change required.

| Use case | Suggested `MODEL` |
|---|---|
| Default — strongest general model on free tier | `openai/gpt-4.1` |
| Speed/cost balance | `openai/gpt-4o-mini` |
| Highest throughput | `microsoft/phi-4-mini-instruct` |
| Code-heavy repo (better feasibility scoring) | `deepseek/deepseek-v3-0324` |
| Open-weights preference | `meta/llama-4-scout-17b-16e-instruct` |

See [`docs/integrations.md`](docs/integrations.md) for the full catalog, rationale, and per-model notes.

## Branded `claude[bot]` author via Claude GitHub App

Use the [Claude GitHub App](https://github.com/apps/claude) (or any custom App with `issues: write`, `contents: read`) so comments and labels are authored by `claude[bot]` instead of `github-actions[bot]`. Caller-side only — no code change.

```yaml
- id: app-token
  uses: actions/create-github-app-token@v1
  with:
    app-id: ${{ secrets.CLAUDE_APP_ID }}
    private-key: ${{ secrets.CLAUDE_APP_PRIVATE_KEY }}

- uses: qte77/gha-issue-triage@v0
  with:
    GH_TOKEN: ${{ steps.app-token.outputs.token }}
```

See [`docs/integrations.md`](docs/integrations.md) for cross-repo scope, token refresh, and a full breakdown of integration paths (including a cheaper self-hosted backend).

## License

[MIT](LICENSE)
