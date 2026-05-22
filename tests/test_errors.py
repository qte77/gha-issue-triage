"""Tests for errors.py — TriageFailure dataclass."""

import dataclasses

import pytest

from src.errors import TriageFailure, TriageFailureError


def test_triage_failure_shape():
    """TriageFailure has four fields and is frozen (immutable)."""
    failure = TriageFailure(
        class_name="x",
        status=401,
        summary="y",
        fix_markdown="z",
    )
    assert failure.class_name == "x"
    assert failure.status == 401
    assert failure.summary == "y"
    assert failure.fix_markdown == "z"

    # Frozen semantics: mutation must raise FrozenInstanceError
    with pytest.raises(dataclasses.FrozenInstanceError):
        failure.class_name = "mutated"  # type: ignore[misc]


def test_triage_failure_error_carries_payload():
    """TriageFailureError wraps a TriageFailure and str(err) == failure.summary."""
    failure = TriageFailure(
        class_name="missing-models-perm",
        status=401,
        summary="GitHub Models inference call returned 401/403.",
        fix_markdown="Add `permissions: models: read`.",
    )
    err = TriageFailureError(failure)
    assert err.failure is failure
    assert str(err) == failure.summary
