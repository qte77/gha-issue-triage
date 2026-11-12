# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Decide shadow's raw-score job-log line no longer raises `OverflowError` on
  an absurdly large JSON integer from the backend -- it now logs `overflow`
  instead, preserving `run_shadow()`'s never-raises contract.

### Changed

- `self-triage.yml` and the README example pin v0.7.1

---

## [0.7.1] - 2026-11-12

### Added

- Decide shadow mode prints each `relevance_score` answer's raw number (and its confidence) to the job log, e.g. `decide-shadow raw relevance_score: 6.432 (confidence 0.04)`, so a live run can confirm the zero-based level index the comment's 1–10 value assumes. Never in the comment; a non-numeric value is logged by type name only

### Changed

- `self-triage.yml` and the README example pin v0.7.0

---

## [0.7.0] - 2026-11-12

### Added

- Relevance scoring reads `AGENTS.md` as repo context when the repo has no `CLAUDE.md`, as Claude Code does, and also when `CLAUDE.md` imports it with an `@AGENTS.md` line. Before, such repos were scored on `README.md` alone, or on the one-line import

### Fixed

- Decide shadow mode showed `-` for every `relevance_score`: the clef/jev backends answer a `score` question with a number (the probability-weighted, zero-based level index, per Clef's model page), which the sanitizer rejected because it only accepted the level labels. The number is now mapped to the nearest level label (`6.4` → `7`); an index outside the levels still shows `-`

### Changed

- `self-triage.yml` and the README example pin v0.6.0; self-triage turns on `decide-shadow`, so this repo's own issues collect decision-model probabilities

---

## [0.6.0] - 2026-11-11

### Added

- Optional `decide-shadow` mode: asks the triage's decision-shaped questions (relevance relevant/category/score, feasibility feasible/complexity/effort) through the shared `qte77/.github` `decide()` gate alongside the existing LLM triage, and appends the calibrated probabilities to the sticky summary comment as a separate section. Off by default (`decide-shadow: "false"`); never sets labels or changes the existing analysis, and a `decide()` failure degrades to `band: escalate` rather than failing the run. New inputs `decide-shadow`, `decide-backend` (default `clef`), `decide-model` (default `clef`), `decide-hi` (default `0.75`) — the `clef` backend reuses the existing `api_base` / `llm-api-key` inputs for credentials, no new secret required. The `jev` backend reads its key from the new `typesafe-api-key` input and never receives the Cloudflare credentials. See `docs/integrations.md#decide-shadow-mode-calibration`

---

## [0.5.0] - 2026-10-26

### Added

- Labels the bot creates get a default description (`labels.LABEL_DESCRIPTIONS`); existing labels with an empty description are backfilled on the next run, and a description already set is never overwritten. `gh label create --force` is no longer used, so existing labels are only touched to backfill an empty description (#93)

### Changed

- Env-var config centralized in `src/config.py` (`AppSettings`, a frozen `pydantic-settings` singleton): all `getenv()` callsites now read typed `config.settings.<field>`, so `MAX_DUPLICATES` / `SIMILARITY_THRESHOLD` no longer need manual `int()` / `float()`. Adds `pydantic-settings` as the action's first runtime dependency (#80)
- `self-triage.yml`: migrated from the retired GitHub Models default to Path B (Cloudflare Workers AI) — `api_base` + `llm-api-key` + `MODEL` inputs, `models: read` permission dropped. Requires repo secret `CF_WORKERS_AI_TOKEN` (owner-provisioned); `docs/integrations.md` updated to reflect the migration
- Releases: new thin `tag-release.yml` / `publish-release.yml` callers of the `qte77/.github` reusable workflows — a merged version bump in `pyproject.toml` is tagged `v{version}` and gets a GitHub Release from its `CHANGELOG.md` block automatically; neither ever deletes or overwrites a tag/Release (#100)
- `self-triage.yml`, README and `docs/integrations.md` examples: `api_base` now reads `secrets.LLM_BASE_URL` instead of `vars.LLM_BASE_URL`, so the Cloudflare account id in the URL stays out of logs
- `README.md` restructured to the qte77 README canon (Hero → Badges → What → How → Why → Refs → License); badges reordered License → Version → CI with a linked blue Version badge (bump-my-version search string updated to match). The Inputs table, provider table and sample summary comment moved to `docs/integrations.md`; duplicated model/backend sections removed from the README. Dead GitHub Models catalog link dropped (#98)

### Fixed

- Issue text could steer what the bot posts: the model's free-text `reasoning` was pasted into the public summary comment, and `category` / `complexity` / `estimated_effort` passed through unchecked. The comment now shows only fixed-list values, and out-of-list model values fall back to defaults (#122)
- `reopened` issues are triaged again; `app.py` skipped them although consumers subscribe to `reopened` (#122)
- With `api_base` set and `llm-api-key` empty, the GitHub token (the deprecated `AI_TOKEN` default) was sent to the LLM host as the bearer; the action now refuses with a `llm-key-is-github-token` failure comment (#122)

---

## [0.4.0] - 2026-10-04

### Added

- `api_base` + `llm-api-key` inputs — canonical names for the OpenAI-compatible backend wiring (Cloudflare Workers AI, Mistral, Cerebras, Ollama, ...). `OPENAI_API_BASE` / `AI_TOKEN` remain as deprecated aliases, resolved by `action.yaml` for backward compatibility (#109, #110)
- `TriageFailure` classes `github-models-retired` and `provider-endpoint-gone` for HTTP 410 Gone responses — previously unhandled, crashing with a raw traceback (#109)
- `TriageFailure` class `llm-bad-response` for an empty, non-JSON, or malformed-shape LLM response body — names the host + HTTP status, never the bearer token (#110)
- `docs/integrations.md` Cloudflare Workers AI caller example + cost row; `docs/architecture.md` boundary row for response-body decoding

### Changed

- `src/llm.py` internal env vars renamed `OPENAI_API_BASE` → `API_BASE`, `AI_TOKEN` → `LLM_API_KEY` (resolved by `action.yaml`; the public `OPENAI_API_BASE`/`AI_TOKEN` inputs still work as deprecated aliases)
- `docs/integrations.md` / `README.md`: GitHub Models (Path 0) marked retired 2026-07-30 and no longer recommended; Path B (OpenAI-compatible) promoted to the primary path, with Cloudflare Workers AI as the recommended default

---

## [0.3.0] - 2026-05-22

### Added

- `documentation` label added to bot vocabulary (#79)
- `TriageFailure` + sticky failure-comment (`comment.post_failure`) infrastructure (#83)
- LLM-boundary error wrapping (401/403/429/5xx/network) + `main()` catch (#84)
- gh-CLI-boundary error wrapping (401/403/404/429) via shared `_gh_errors.py`; transient 5xx degrades (#85, closes #61)
- `docs/integrations.md` Troubleshooting section, per-class canonical fixes (#85)
- `docs/architecture.md` boundary failure-policy table (#83)
- `.github/dependabot.yaml` + `.github/workflows/codeql.yml` (#73)
- Injection-safety comment in `action.yaml` `env:` block (#77)
- Live Dependabot status badge in README (#72)
- `AGENTS.md` agent governance file

### Changed

- **Label rename**: `good-first-issue` → `good first issue`; `needs-discussion` → `needs discussion` (matches GitHub defaults). Legacy spellings auto-removed via `DEPRECATED_LABELS` reconciliation (#79, closes #71, #63)
- Ruff `select` expanded: `+ N, UP, B, S, SIM, RUF, PT, TRY` (ignore `TRY003`); `mccabe max-complexity=10`; per-file-ignores for `tests/*` and `src/*`. Strictness rules deferred (see #62) (#82)
- `setup-uv` `cache-dependency-glob` pinned to action's own `uv.lock` — silences consumer warning (#81, closes #65)
- `github/codeql-action` 4.35.4 → 4.35.5 (#74)
- All workflow `uses:` SHA-pinned (#60)

### Removed

- README `## Branded claude[bot] author` section (#69)
- `docs/integrations.md` Path A (`apps/claude` recommendation) — over-privileged + misleading attribution; rationale in #68 / [`ai-agents-research#163`](https://github.com/qte77/ai-agents-research/issues/163) (#78, closes #68)

### Fixed

- Bare imports in `src/{comment,app,llm}.py` (`from src.errors` → `from errors`); would have failed at action runtime under `PYTHONPATH=src` (bundled in #85)
- README screenshot block repositioned under "What it does" (#69)

---

## [0.2.4] - 2026-05-17

### Fixed

- README and `docs/integrations.md` usage examples pinned to a real release tag (`@v0.2.4`); previously pointed at `@v0` and `@v1` respectively, neither of which exists — copy-pasted examples failed with `tag not found` (#TBD)

### Documentation

- Backfilled empty `[0.2.2]` and `[0.2.3]` sections in `CHANGELOG.md` with the actual changes that shipped under those tags (#TBD)

---

## [0.2.3] - 2026-05-17

### Fixed

- SHA-pin `actions/checkout@v6` → `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd` (v6.0.2) in `action.yaml`. Unblocks consumers in strict-pin-policy organizations that reject tag refs on every nested `uses:`, including inside composite actions (#54)

---

## [0.2.2] - 2026-05-15

### Fixed

- `action.yaml` `description` trimmed from 141 → 119 chars to pass GitHub Marketplace publication validation (≤124 chars). No behaviour change (#52)

---

## [0.2.1] - 2026-05-14

### Added

- Theme-aware screenshot of triaged issues in the README, collapsed under a `<details>` block (#46)
- `docs/integrations.md`: "Auth for `AI_TOKEN`" section documenting the three valid token shapes for GitHub Models (workflow `${{ github.token }}` with `permissions: models: read`, scopeless classic PAT, fine-grained PAT with `user_models:read`) plus rate-limit attribution caveats (#47)

### Changed

- Self-triage workflow uses the default `${{ github.token }}` for GitHub Models calls instead of a custom `GH_MODELS` PAT — `permissions: models: read` is sufficient. Callers no longer need to mint a PAT for the default Path 0 setup (#47)
- `.markdownlint.json` added at the repo root: disables MD013 (line-length), allows duplicate `### Added` / `### Fixed` headings under different version H2s, permits inline `<details>` / `<summary>` / `<picture>` / `<source>` / `<img>` for theme-aware images. Table separator rows in README and `docs/integrations.md` reformatted from `|---|---|` to `| --- | --- |` (#43, #46)

### Fixed

- Category label (`feature` / `bug` / `enhancement` / `needs-discussion`) is no longer applied when `relevance.irrelevant=true`; only `invalid` (plus feasibility/duplicate labels) is applied. Resolves the contradictory `invalid` + `feature` combo that appeared on out-of-scope issues (#41)
- `apply_labels` now reconciles the managed label set on every triage run: fossil labels within `VALID_LABELS` are removed, additions and removals happen in a single `gh issue edit` call, and a no-op fast-path skips the call entirely when the set is already in sync. Human-applied labels outside `VALID_LABELS` are preserved (#42)

---

## [0.2.0] - 2026-05-12

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
