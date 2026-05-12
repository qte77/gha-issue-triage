# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `OPENAI_API_BASE` input — third LLM backend for any OpenAI-compatible Chat Completions endpoint (Mistral / Devstral, Ollama, vLLM, self-hosted). Takes precedence over Anthropic and GitHub Models when set. Localhost `http://` allowed for self-hosted; all other URLs must be `https://` (#11)
- Sticky AI summary comment per issue, idempotent across re-runs via a hidden marker (#28, #29)
- Self-triage workflow: every new/edited issue in this repo is triaged automatically (#24, #32)
- New `feasibility` (yes/no) field in the analysis output, distinct from `complexity` (low/medium/high). Renders as its own line in the summary comment; `Complexity:` is omitted when `feasibility=no`.
- README sections for Path 0 (model alternatives) and Path A (Claude GitHub App auth), plus a sample summary comment (#22, #23, #33)
- `docs/integrations.md`: integration paths overview (Path 0/A/B) with cost matrix (#9)

### Changed

- Anthropic model bumped to `claude-sonnet-4-6` (#17)
- Rendered analysis line: `Feasibility:` → `Complexity:` to match the underlying field's semantics (high = hard) (#31)
- `astral-sh/setup-uv` pinned to v8.1.0 SHA — clears the Node-20 deprecation warning and `url.parse` DEP0169 (#25, #26)
- README license references updated MIT → Apache-2.0 to match `LICENSE` (#31)
- `app.py` now accepts `issues: labeled` events for label-gated callers (#25)

### Fixed

- `find_duplicates` excludes the current issue from the candidate pool — no more spurious self-match `duplicate` label (#27)
- Summary comment renders balanced parens regardless of `estimated_effort` value (#29)
- `_request_with_retry` validates `https://` scheme before `urllib.urlopen` (Bandit B310) (#15)
- `parser` typed as `Callable[[dict], str]` instead of the builtin `callable` (#31)
- `uv.lock` synced to project version 0.1.1 (#16)

---

## [0.1.1] - 2026-05-08

### Added

- Initial release: AI-powered issue triage GitHub Action
- Duplicate detection via difflib fuzzy matching
- Relevance scoring via LLM (GitHub Models API or Anthropic)
- Feasibility analysis with codebase context
- Auto-labeling via gh CLI
