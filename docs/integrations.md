# Integration Paths

Three non-breaking paths for users of `gha-issue-triage`. GitHub-Models default is preserved in all of them.

- **Path 0** — Stay on GitHub Models, switch to a smaller/faster model via the existing `MODEL` input. **No code change.**
- **Path A** — Use [`apps/claude`](https://github.com/apps/claude) for GitHub auth instead of `github.token`. **No code change.**
- **Path B** — Add OpenAI-compatible backend (Mistral / Devstral / Ollama / vLLM). **One small change in `src/llm.py` + new input.**

## Current Wiring (Reference)

From [`src/llm.py`](../src/llm.py): two backends. `ANTHROPIC_API_KEY` flips to Anthropic with model **hardcoded** at `claude-sonnet-4-6` (`src/llm.py:51`) — `MODEL` input only affects GitHub Models.

## Path 0 — Different model on GitHub Models

The action's `MODEL` default `openai/gpt-4.1` works but is one of dozens. Issue triage (~5K in / ~500 out, no long context) is a small/fast model task. GitHub Models exposes the same Chat-Completions endpoint for every model, so swapping is a one-line change.

Notable IDs available on GitHub Models ([catalog reference][gh-models-cat]):

| Model ID | Provider | Why for triage |
|---|---|---|
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

**Implementation effort: zero** — works today.

## Path A — Claude GitHub App auth

```yaml
- id: app-token
  uses: actions/create-github-app-token@v1
  with:
    app-id: ${{ secrets.CLAUDE_APP_ID }}
    private-key: ${{ secrets.CLAUDE_APP_PRIVATE_KEY }}

- uses: qte77/gha-issue-triage@v1
  with:
    GH_TOKEN: ${{ steps.app-token.outputs.token }}
```

Effect: comments authored by `claude[bot]`, cross-repo scope, refreshable token. Requires `apps/claude` (or custom App with `issues: write`, `contents: read`) installed on the org.

**Implementation effort: zero** — works today via existing `GH_TOKEN` input.

## Path B — OpenAI-compatible backend (Mistral / Devstral / Ollama)

[Devstral](https://mistral.ai/news/devstral) (Apache 2.0, 24B, 68.0% SWE-Bench Verified) and any other OpenAI-compatible provider plug in via a new `OPENAI_API_BASE` input. References: [Devstral Small 2][devstral-card], [Mistral API docs][mistral-api].

### Required action change

```python
# src/llm.py
OPENAI_API_BASE = getenv("OPENAI_API_BASE", "")

def call_llm(system_prompt, user_prompt):
    if OPENAI_API_BASE:
        return _call_openai_compat(system_prompt, user_prompt)
    if ANTHROPIC_API_KEY:
        return _call_anthropic(system_prompt, user_prompt)
    return _call_github_models(system_prompt, user_prompt)
```

`_call_openai_compat` reuses `_parse_github_models` — GitHub Models response shape mirrors OpenAI Chat Completions, so the parser is identical. Add `OPENAI_API_BASE` input to `action.yaml` (default empty).

### Caller workflows

Mistral API:

```yaml
with:
  AI_TOKEN: ${{ secrets.MISTRAL_API_KEY }}
  MODEL: devstral-small-2505
  OPENAI_API_BASE: https://api.mistral.ai/v1
```

Self-hosted Ollama (RTX 4090 / Mac 32GB):

```yaml
with:
  AI_TOKEN: ollama-no-auth
  MODEL: devstral-small-2
  OPENAI_API_BASE: http://localhost:11434/v1
```

### Cost (10 issues/day, ~5K in / 500 out per issue)

| Backend | Monthly |
|---|---|
| GitHub Models (Path 0, any model) | $0 (rate-limited) |
| Anthropic Sonnet | ~$9 |
| Anthropic Opus | ~$34 |
| **Mistral Devstral API** | **~$0.20** |
| Self-hosted Devstral | ~$5–10 power |

### Implementation effort

`OPENAI_API_BASE` input + `_call_openai_compat` + tests + README update — **~1.5 h**.

## Recommendation Matrix

| Workload | Path | Why |
|---|---|---|
| Low volume, public repo | **Path 0** (any free GH Models ID) | Free, rate limits sufficient |
| Code-heavy repo, want better feasibility scoring | **Path 0 + DeepSeek** | `deepseek-v3-0324` for code understanding |
| Want branded `claude[bot]` author + cross-repo auth | **Path A** | Caller-side only |
| High volume, free tier exhausted | **Path B** (Devstral API) | ~45× cheaper than Sonnet |
| Privacy / compliance | **Path B** (self-hosted) | No API egress |

## Suggested Follow-Ups

1. Implement Path B (`OPENAI_API_BASE` + OpenAI-compat backend)
2. Document Path 0 model alternatives + Path A in README
3. Optionally make the Anthropic model `MODEL`-driven when `ANTHROPIC_API_KEY` is set (Sonnet 4.6 is the current hardcoded default)

[gh-models-cat]: https://github.com/marketplace/models
[gh-models-docs]: https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models
[devstral-card]: https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512
[mistral-api]: https://docs.mistral.ai/
