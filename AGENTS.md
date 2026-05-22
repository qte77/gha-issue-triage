# Agent Instructions for `gha-issue-triage`

Behavioral rules and compliance requirements for AI coding agents contributing
to this repository. For project overview see [README.md](README.md); for
integration paths and troubleshooting see
[`docs/integrations.md`](docs/integrations.md); for boundary failure policies
see [`docs/architecture.md`](docs/architecture.md).

## Core principles (MANDATORY)

These principles override all other guidance when conflicts arise.

- **KISS** — simplest solution that works. Clear over clever.
- **DRY** — single source of truth. Reference, don't duplicate.
- **YAGNI** — implement only what's requested. No speculative features.
- **Concise and focused** — minimal code/text for task. Touch only task-related code.
- **Reuse and extend** — use existing patterns and dependencies. Don't rebuild.
- **Root-cause and first-principles** — understand the *why*. Solve root problems.
- **Resolve ambiguity** — clarify vague requirements before acting. Never assume missing context.

## Behavioral rules

- **Never assume missing context** — ask if uncertain about requirements.
- **Never hallucinate libraries** — only use packages verified in `pyproject.toml`.
- **Never delete existing code** unless explicitly instructed or refactoring is documented in the PR description.
- **Always confirm file paths exist** before referencing in code or tests.
- **Document new patterns** in the PR description (not via separate sidecar files unless explicitly asked).

## Repository conventions

These are non-negotiable for any PR landing on `main`:

- **SHA-pin every `uses:`** in workflows and `action.yaml` — full-length commit SHA, never a tag/branch. Enforced by repo `sha_pinning_required: true` policy.
- **Squash-only merge** — repo ruleset `15253739` allows `squash` exclusively.
- **Required signatures** — commits on `main` must be cryptographically signed (GPG/SSH/web-flow). CLI commits without local signing config require `--admin` on `gh pr merge` (GitHub web-flow signs the squash commit).
- **Linear history** — no merge commits on `main`.
- **Required status checks** — `CodeFactor` + `CodeQL` must pass before merge.
- **No `${{ github.event.* }}` interpolation in `run:`** — caller inputs flow through `env:` and dereference as `$VAR` in shell. See the inline note in `action.yaml`.
- **Use bare imports in `src/`** (`from errors import ...`, not `from src.errors import ...`). The action runs with `PYTHONPATH=src` only — there is no `src` package on the path at runtime. Tests can use either form (pytest pythonpath includes `.`).

## Boundary failure policies

Every I/O boundary is pinned to exactly one policy in
[`docs/architecture.md`](docs/architecture.md). Before adding a new
`try/except` look up the row; if none exists for that boundary, add it as part
of the same PR.

The four policies in use:

- **fail-loud** — raise immediately.
- **wrap-degrade** — catch a specific exception, log a `WARNING`, return a degraded result.
- **wrap-continue** — `wrap-degrade` inside a loop.
- **wrap-comment-fail-loud** — catch a known auth/API failure, post a `TriageFailure` comment via the sticky-comment marker, then `sys.exit(1)`. Workflow stays red; users get a human-readable reason.

## Development workflow

- **Tests first** — TDD where applicable (one Red commit → one Green commit per observable behavior). Tiny commits squash cleanly. Regression-pin commits (Red-only) are appropriate when earlier-cycle impl already covers the behavior.
- **CI is authoritative** — local `uv run pytest` and `uv run ruff check .` are preferred when the sandbox permits; otherwise CI is the verification.
- **Update `CHANGELOG.md`** for non-trivial changes — append to the `[Unreleased]` section under `Added` / `Changed` / `Fixed` / `Removed` per Keep-a-Changelog.
- **Reference issues** in commit / PR bodies — `Closes #NN` auto-closes on merge.

## Subagent role boundaries

When spawning subagents (Task/Agent tool):

- **Architects** design and specify; do not implement.
- **Developers** implement to spec; do not redesign without architect approval.
- **Reviewers** check quality/security/standards; do not implement new features.
- **Researchers** gather and cite first-party sources; do not execute code changes.

Each subagent prompt must be self-contained — the subagent has no parent-session context. Include: cwd, repo, issue # + body, branch name, commit message style, the established `--admin --squash --delete-branch` pattern, and explicit instructions NOT to invoke unrelated skills (e.g. `fewer-permission-prompts`, `update-config`).

## Quality thresholds

Before starting any non-trivial task, ensure:

- **Context** ≥ 8/10 — understand requirements, codebase patterns, dependencies.
- **Clarity** ≥ 7/10 — clear implementation path and expected outcomes.
- **Alignment** ≥ 8/10 — follows project patterns and architectural decisions.
- **Success confidence** ≥ 7/10 — confident in completing correctly.

Below threshold: gather more context or stop and ask.

## Pre-task checklist

- [ ] Does this serve user value?
- [ ] Is this the simplest approach?
- [ ] Am I duplicating existing work?
- [ ] Do I actually need this?
- [ ] Am I touching only relevant code?
- [ ] What's the root cause I'm solving?

## Post-task review

Before finishing:

- **Did we forget anything?** — check requirements thoroughly
- **High-ROI enhancements?** — suggest, don't implement
- **Something to delete?** — remove obsolete/unnecessary code

Do NOT alter files based on this review. Only output suggestions to the user.

## When in doubt

**Stop. Ask.** Don't assume, don't over-engineer, don't add complexity.
