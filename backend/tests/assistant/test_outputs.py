"""Unit tests for assistant output models."""

import pytest
from uuid import UUID
from pydantic import ValidationError

from app.assistant.outputs import Citation, GroundedAnswer


def test_citation_valid():
    """Valid citation constructs cleanly."""
    citation = Citation(
        citation_index=1,
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        excerpt="Apple revenue increased"
    )
    assert citation.citation_index == 1
    assert citation.chunk_id == UUID("00000000-0000-0000-0000-000000000001")
    assert citation.excerpt == "Apple revenue increased"


def test_citation_zero_index_fails():
    """citation_index must be ≥1."""
    with pytest.raises(ValidationError):
        Citation(
            citation_index=0,
            chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
            excerpt="text"
        )


def test_citation_negative_index_fails():
    """citation_index must be ≥1."""
    with pytest.raises(ValidationError):
        Citation(
            citation_index=-1,
            chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
            excerpt="text"
        )


def test_citation_excerpt_too_long_fails():
    """excerpt must be max 125 characters."""
    long_excerpt = "a" * 126
    with pytest.raises(ValidationError):
        Citation(
            citation_index=1,
            chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
            excerpt=long_excerpt
        )


def test_grounded_answer_valid():
    """Valid GroundedAnswer constructs cleanly."""
    answer = GroundedAnswer(
        answer="Apple revenue increased [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
                excerpt="Apple revenue"
            )
        ],
        insufficient_evidence=False
    )
    assert answer.answer == "Apple revenue increased [1]."
    assert len(answer.citations) == 1
    assert answer.insufficient_evidence is False


def test_grounded_answer_defaults():
    """GroundedAnswer citations default to empty list."""
    answer = GroundedAnswer(answer="Some answer")
    assert answer.answer == "Some answer"
    assert answer.citations == []
    assert answer.insufficient_evidence is False


def test_grounded_answer_insufficient_evidence():
    """GroundedAnswer with insufficient_evidence flag."""
    answer = GroundedAnswer(
        answer="The corpus does not contain enough information.",
        insufficient_evidence=True
    )
    assert answer.insufficient_evidence is True
    assert answer.citations == []


def test_grounded_answer_serialization():
    """GroundedAnswer round-trips through JSON."""
    original = GroundedAnswer(
        answer="Test [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
                excerpt="test"
            )
        ],
    )

    json_data = original.model_dump_json()
    restored = GroundedAnswer.model_validate_json(json_data)

    assert restored.answer == original.answer
    assert len(restored.citations) == 1
    assert restored.citations[0].citation_index == 1
