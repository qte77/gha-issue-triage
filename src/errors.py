"""Structured failure type for human-readable triage error comments."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TriageFailure:
    """Immutable description of a triage boundary failure.

    Fields
    ------
    class_name:   The exception class that triggered this failure.
    status:       HTTP status code, if available (None otherwise).
    summary:      One-line human-readable description.
    fix_markdown: Markdown block with remediation steps for the issue comment.
    """

    class_name: str
    status: int | None
    summary: str
    fix_markdown: str


class TriageFailureError(Exception):
    """Exception carrying a TriageFailure payload for boundary code to raise."""

    def __init__(self, failure: TriageFailure) -> None:
        super().__init__(failure.summary)
        self.failure = failure
