# Architecture: Boundary Policies

Every I/O boundary in this action is pinned to **exactly one** failure
policy. Adopted from `py-harden-ruff.md` section 5 (pattern surfaced in
the sibling repo `qte77/analyze-stock-kpi`).

## Policies

- **fail-loud** — raise immediately. Failure is a programmer / infra /
  config problem that silent degradation would hide.
- **wrap-degrade** — catch a specific exception, log a `WARNING`, return
  a degraded result (`None`, sparse, empty list).
- **wrap-continue** — `wrap-degrade` inside a loop; per-item failure
  doesn't abort the batch.
- **wrap-comment-fail-loud** (hybrid, specific to this action) — catch
  a known auth/API failure, post a `TriageFailure` comment to the
  triggering issue via the existing sticky-comment marker, then
  `sys.exit(1)` so the workflow stays red. Users get a human-readable
  reason on the issue page without losing the CI signal.

## Boundary table

| Boundary | File / function | Policy | On failure |
| --- | --- | --- | --- |
| LLM call (GitHub Models / Anthropic / OpenAI-compat) | `llm.call_llm` | wrap-comment-fail-loud | post `TriageFailure` comment, `sys.exit(1)` |
| gh CLI invocations (`issue view/edit/comment`, `label create`) | `labels`, `comment`, `duplicates` | wrap-comment-fail-loud for 401/403/404/429; wrap-degrade for transient 5xx | comment + exit OR log warning + continue |
| Sticky-comment post itself | `comment.post_summary` | wrap-degrade | log warning; never block (labels are already applied by then) |
| Duplicate detection in-process | `duplicates.find_duplicates` | wrap-degrade | empty list; triage continues |

When a code reviewer sees a new `try/except`, they look up the row. If
no row exists for that boundary, add it as part of the PR that
introduces the boundary.
