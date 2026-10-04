# Integration Paths

Two paths for users of `gha-issue-triage`.

- **Path 0** — Stay on GitHub Models, switch to a smaller/faster model via the existing `MODEL` input. **GitHub Models was retired 2026-07-30 ([changelog][gh-models-retired-changelog]) — this path no longer works.** Kept documented only so the historical default is explained; move to Path B.
- **Path B** — OpenAI-compatible backend (Cloudflare Workers AI / Mistral / Cerebras / Ollama / vLLM). **New `api_base` + `llm-api-key` inputs, no code change for callers.**

## Current Wiring (Reference)

From [`src/llm.py`](../src/llm.py): three backends, dispatched in this order — OpenAI-compatible (`api_base` set) → Anthropic (`ANTHROPIC_API_KEY` set) → GitHub Models (default, retired). `ANTHROPIC_API_KEY` flips to Anthropic with model **hardcoded** at `claude-sonnet-4-6` (`src/llm.py:198`) — `MODEL` input only affects GitHub Models and OpenAI-compatible backends. `api_base` / `llm-api-key` are the canonical inputs; `OPENAI_API_BASE` / `AI_TOKEN` are deprecated aliases resolved by `action.yaml` for backward compatibility.

## Path 0 — Different model on GitHub Models (retired, historical)

The action's `MODEL` default `openai/gpt-4.1` worked but is one of dozens. Issue triage (~5K in / ~500 out, no long context) is a small/fast model task. GitHub Models exposed the same Chat-Completions endpoint for every model, so swapping was a one-line change — **this entire backend now returns HTTP 410 Gone and cannot be used; switch to Path B.**

Notable IDs available on GitHub Models ([catalog reference][gh-models-cat]):

| Model ID | Provider | Why for triage |
| --- | --- | --- |
| `openai/gpt-4.1` | OpenAI | Current default — strongest general model on free tier |
| `openai/gpt-4o-mini` | OpenAI | ~5× faster than gpt-4.1 at similar triage quality |
| `microsoft/phi-4-mini-instruct` | Microsoft | Tiny, fastest, cheapest — good for high-volume orgs |
| `mistral-ai/mistral-small-3.1` | Mistral | Agentic-leaning, small, fast |
| `meta/llama-4-scout-17b-16e-instruct` | Meta | Open weights, strong reasoning |
| `deepseek/deepseek-v3-0324` | DeepSeek | Strong code understanding for feasibility scoring |

Switching:

```yaml
with:
  MODEL: openai/gpt-4o-mini   # or any ID from the catalog
```

**Recommended free**: `openai/gpt-4o-mini` for speed-cost balance, `microsoft/phi-4-mini-instruct` for highest throughput.
**Recommended for code-heavy repos**: `deepseek/deepseek-v3-0324` (better feasibility analysis than gpt-4o-mini).

GitHub Models has no public per-model pricing — paid tier is "opt into paid usage or BYO API keys" once free-tier rate limits are hit ([GH Models docs][gh-models-docs]).

**Implementation effort: zero** — but the backend itself is gone (see above). Historical reference only.

## Auth for `llm-api-key` (GitHub Models specifically, retired)

The action's `llm-api-key` input (deprecated alias: `AI_TOKEN`) defaults to `${{ github.token }}`. Combined with `permissions: models: read` on the caller workflow, that was sufficient for the GitHub Models inference endpoint while it existed — **no separate PAT or org-level setup was required**. This repo's own [`self-triage.yml`](../.github/workflows/self-triage.yml) still shows the pattern, though the backend it targets now returns HTTP 410 (`github-models-retired`, see [Troubleshooting](#troubleshooting)) until it is updated to Path B.

Three valid token shapes for GitHub Models, in increasing setup cost:

| Token shape | Setup | Models access requirement |
| --- | --- | --- |
| `${{ github.token }}` (workflow default) | Add `permissions: models: read` to the caller workflow | Documented as valid syntax under `permissions:` in the [GitHub Actions workflow syntax docs](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions) |
| Classic PAT | *Settings → Developer settings → Personal access tokens (classic)* — **no scopes needed** | The REST [Models inference docs](https://docs.github.com/en/rest/models/inference?apiVersion=2022-11-28) note the `models:read` scope is required *only* "when using a fine-grained personal access token or when authenticating using a GitHub App" — classic PATs authenticate as a user without an explicit Models scope |
| Fine-grained PAT | *Settings → Personal access tokens (fine-grained)* — Account permissions → **Models: Read-only** (URL param `&user_models=read`) | Most-locked-down option; required scope is explicit |

### Rate-limit attribution

Per the [Models docs](https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models), rate limits are tied to the **Copilot subscription tier** of the user making the call, not the org's plan. Free / Pro / Business share a tier; Copilot Enterprise gets the most headroom.

What "the user making the call" means in each case is **not first-party documented** but coherent with empirical behaviour:

- `${{ github.token }}` → calls run as `github-actions[bot]`, which has no Copilot subscription → lowest free quota bucket. Sufficient for low-volume repos; can 429 on bursts.
- Classic / fine-grained PAT → inherits the **creating user's** Copilot tier. Useful if the maintainer has a higher tier than `github-actions[bot]`.

This path is **no longer usable** — GitHub Models is retired. Migrate to Path B.

## Path B — OpenAI-compatible backend (Cloudflare Workers AI / Mistral / Cerebras / Ollama / ...)

Shipped in [#11](https://github.com/qte77/gha-issue-triage/issues/11) (action ≥0.2.0); `api_base` + `llm-api-key` became the canonical input names in ≥0.4.0 (`OPENAI_API_BASE` / `AI_TOKEN` are deprecated aliases, still accepted). Any OpenAI-compatible Chat Completions endpoint plugs in via `api_base` — Cloudflare Workers AI, Mistral, Cerebras, Groq, Together, Fireworks, vLLM, Ollama. `llm-api-key` is sent as a Bearer; `MODEL` selects the model. Localhost `http://` is allowed for self-hosted; all other URLs must be `https://`.

References: [Cloudflare Workers AI OpenAI compatibility][cf-workers-ai-openai], [Devstral Small 2][devstral-card], [Mistral API docs][mistral-api].

### Caller workflows

Cloudflare Workers AI (recommended default — generous free tier, verified 2026-10-04):

```yaml
with:
  llm-api-key: ${{ secrets.CF_WORKERS_AI_TOKEN }}
  MODEL: "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
  api_base: ${{ vars.LLM_BASE_URL }}  # https://api.cloudflare.com/client/v4/accounts/<id>/ai/v1
```

Mistral Devstral (cloud):

```yaml
with:
  llm-api-key: ${{ secrets.MISTRAL_API_KEY }}
  MODEL: devstral-small-2505
  api_base: https://api.mistral.ai/v1
```

Cerebras (fast inference):

```yaml
with:
  llm-api-key: ${{ secrets.CEREBRAS_API_KEY }}
  MODEL: llama-3.3-70b
  api_base: https://api.cerebras.ai/v1
```

Self-hosted Ollama (RTX 4090 / Mac 32GB):

```yaml
with:
  llm-api-key: ollama-no-auth
  MODEL: devstral-small-2
  api_base: http://localhost:11434/v1
```

### Cost (10 issues/day, ~5K in / 500 out per issue)

| Backend | Monthly |
| --- | --- |
| GitHub Models (Path 0) | **retired — unusable** |
| Cloudflare Workers AI | $0 (10,000 Neurons/day free tier) |
| Anthropic Sonnet | ~$9 |
| Anthropic Opus | ~$34 |
| **Mistral Devstral API** | **~$0.20** |
| Self-hosted Devstral | ~$5–10 power |

## Recommendation Matrix

| Workload | Path | Why |
| --- | --- | --- |
| Low volume, public repo | **Path B** (Cloudflare Workers AI) | Free (10,000 Neurons/day), zero egress cost |
| Code-heavy repo, want better feasibility scoring | **Path B** (self-hosted DeepSeek, or any strong code model via `api_base`) | Pick any OpenAI-compatible model |
| High volume, free tier exhausted | **Path B** (Devstral API) | ~45× cheaper than Sonnet |
| Privacy / compliance | **Path B** (self-hosted) | No API egress |

Path 0 (GitHub Models) is omitted — it is retired and no longer a viable option.

## Suggested Follow-Ups

1. Optionally make the Anthropic model `MODEL`-driven when `ANTHROPIC_API_KEY` is set (Sonnet 4.6 is the current hardcoded default)

## Troubleshooting

When the action hits an auth/API failure it posts a sticky comment to the
triggering issue (via `src/comment.py:post_failure`) and exits non-zero so
CI stays red. Each class below corresponds to a `TriageFailure.class_name`
value emitted by the action. The comment posted to the issue links to this
section via anchor.

### `github-models-retired` — HTTP 410 from GitHub Models

GitHub Models was retired 2026-07-30 ([changelog][gh-models-retired-changelog])
and the inference endpoint now returns HTTP 410 Gone for every call. This is
not transient — re-running will not help. Switch to Path B: set `api_base` +
`llm-api-key` (see [Path B](#path-b--openai-compatible-backend-cloudflare-workers-ai--mistral--cerebras--ollama--)
above), or set `ANTHROPIC_API_KEY`.

### `provider-endpoint-gone` — HTTP 410 from an OpenAI-compatible endpoint

The endpoint at `api_base` returned HTTP 410 Gone. The base URL has likely
moved or the provider retired that path. Check the provider's current
OpenAI-compatible endpoint docs and update `api_base`.

### `missing-models-perm` — HTTP 401/403 from GitHub Models (retired)

The action's LLM call to `models.github.ai` was rejected — or, since
2026-07-30, returns 410 before this class is even reached (see
`github-models-retired` above). Historically the cause was a missing
`permissions: models: read` block in the caller workflow. Migrate to Path B
instead of chasing this: see [Auth for `llm-api-key`](#auth-for-llm-api-key-github-models-specifically-retired)
above.

### `invalid-anthropic-key` — HTTP 401 from Anthropic

`ANTHROPIC_API_KEY` is set but was rejected by `api.anthropic.com`. Rotate
the key in your repository secrets, or unset `ANTHROPIC_API_KEY` entirely to
fall back to the GitHub Models backend.

### `invalid-ai-token` — HTTP 401 from OpenAI-compatible endpoint

The Bearer token in `llm-api-key` (or the deprecated `AI_TOKEN`) was rejected
by the custom `api_base` endpoint. Verify the key is valid for that provider
and that the endpoint URL is correct.

### `llm-bad-response` — empty, non-JSON, or malformed-shape response body

The LLM backend returned a 2xx response this action could not parse: an
empty body, a non-JSON body (e.g. an HTML error page from a proxy), or JSON
missing the expected `choices` (OpenAI-compatible/GitHub Models) or `content`
(Anthropic) field. The failure comment names the host and HTTP status only —
never the bearer token. Verify `api_base` points at an actual OpenAI-compatible
Chat Completions endpoint and that `MODEL` is a valid ID for that provider.

### `llm-rate-limit` — HTTP 429 from LLM backend

The LLM backend returned a rate-limit response. Re-run the workflow after
the `Retry-After` window elapses. For sustained traffic, supply a PAT via
`llm-api-key` (higher per-user quota) or switch to an OpenAI-compatible backend
(Path B above) with its own quota.

### `llm-upstream` — HTTP 5xx from LLM backend

A transient upstream error was returned by the LLM provider. No caller change
is needed — re-run the workflow.

### `llm-network` — Network/TLS error reaching LLM backend

The runner could not reach the LLM host (DNS failure, TLS error, etc.).
This is typically a transient runner-side issue. Re-run the workflow.

### `missing-issues-write` — HTTP 403 from `gh issue edit` / `gh issue comment` / `gh label create`

The caller workflow's `GITHUB_TOKEN` lacks the `issues: write` permission.
Add the following to the job that calls this action:

```yaml
permissions:
  issues: write
```

### `fork-pr-readonly-token` — HTTP 403 with "Resource not accessible by integration"

The action was triggered from a forked-repository pull request, where
`GITHUB_TOKEN` is read-only by GitHub security policy. The action cannot
apply labels or post comments in this context. If you need triage on forked
PRs, use `pull_request_target` instead of `pull_request` — but read the
[security implications][pr-target-docs] carefully before doing so.

### `not-found` — HTTP 404 from any `gh` call

The action could not reach the issue or repository. Common causes:
- `GH_TOKEN` scope is too narrow (private repos require the `repo` scope)
- The issue number or repository slug in the event payload is incorrect

Supply a fine-grained PAT or classic PAT with `repo` scope via `GH_TOKEN`.

### `gh-rate-limit` — HTTP 429 from GitHub API

The GitHub REST API rate-limit was hit. Re-run the workflow after the limit
resets (typically within an hour). For high-volume repositories, supply a
PAT via `GH_TOKEN` — authenticated requests use a higher per-user quota than
the default `GITHUB_TOKEN` (`github-actions[bot]`).

[gh-models-cat]: https://github.com/marketplace/models
[gh-models-docs]: https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models
[gh-models-retired-changelog]: https://github.blog/changelog/2026-07-30-github-models-is-now-retired/
[cf-workers-ai-openai]: https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/
[devstral-card]: https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512
[mistral-api]: https://docs.mistral.ai/
[pr-target-docs]: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#pull_request_target
