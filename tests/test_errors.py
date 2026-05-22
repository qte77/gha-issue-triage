"""Tests for errors.py — TriageFailure dataclass."""

import dataclasses

import pytest

from src.errors import TriageFailure


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
