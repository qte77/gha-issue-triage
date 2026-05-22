"""Shared gh CLI error parser: maps stderr → TriageFailureError.

Used by labels.py, comment.py, and duplicates.py to enforce a consistent
failure policy (wrap-comment-fail-loud for 403/404/429; wrap-degrade for 5xx).
"""

from errors import TriageFailure, TriageFailureError


def raise_or_degrade_gh_error(stderr: str, context: str) -> None:
    """Parse gh CLI stderr and raise TriageFailureError for known errors.

    Policy (per docs/architecture.md boundary table):
    - 403 missing permissions → raise TriageFailureError(missing-issues-write)
    - 403 fork readonly token → raise TriageFailureError(fork-pr-readonly-token)
    - 404 not found         → raise TriageFailureError(not-found)
    - 429 rate limited      → raise TriageFailureError(gh-rate-limit)
    - 5xx transient         → wrap-degrade: print warning and return

    Parameters
    ----------
    stderr:  The stderr string from a failed subprocess.run call.
    context: A short description of the failed operation for the warning message.
    """
    if "HTTP 403" in stderr or "403 Forbidden" in stderr:
        if "Resource not accessible by integration" in stderr:
            raise TriageFailureError(
                TriageFailure(
                    class_name="fork-pr-readonly-token",
                    status=403,
                    summary=(
                        "Triage cannot run on forked-repo PRs — `GITHUB_TOKEN` is read-only there."
                    ),
                    fix_markdown=(
                        "Use `pull_request_target` only if you accept the security tradeoff. "
                        "See `docs/integrations.md#troubleshooting`."
                    ),
                )
            )
        raise TriageFailureError(
            TriageFailure(
                class_name="missing-issues-write",
                status=403,
                summary=("gh CLI 403 from issue/label call — caller workflow lacks issues: write."),
                fix_markdown=(
                    "Add `permissions: issues: write` to the caller workflow. "
                    "See `docs/integrations.md#troubleshooting`."
                ),
            )
        )
    if "HTTP 404" in stderr:
        raise TriageFailureError(
            TriageFailure(
                class_name="not-found",
                status=404,
                summary="gh CLI 404 — issue or repo not reachable from the supplied token.",
                fix_markdown=(
                    "`GH_TOKEN` scope likely too narrow; for private repos pass a PAT with "
                    "`repo` scope. See `docs/integrations.md#troubleshooting`."
                ),
            )
        )
    if "HTTP 429" in stderr:
        raise TriageFailureError(
            TriageFailure(
                class_name="gh-rate-limit",
                status=429,
                summary="GitHub API rate-limit hit (HTTP 429).",
                fix_markdown=(
                    "Re-run after the limit resets. For high-volume repos consider a PAT via "
                    "`GH_TOKEN` (higher per-user quota). "
                    "See `docs/integrations.md#troubleshooting`."
                ),
            )
        )
    # 5xx and other transient errors: wrap-degrade
    print(f"::warning::{context}: {stderr}")
