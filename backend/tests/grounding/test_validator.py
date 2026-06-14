"""Unit tests for citation validation."""

import pytest
from uuid import UUID

from app.assistant.outputs import Citation, GroundedAnswer
from app.assistant.deps import TurnRegistry
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import RetrievedPassage


@pytest.fixture
def registry_with_passages():
    """Create a registry with sample passages."""
    reg = TurnRegistry()
    reg.register(RetrievedPassage(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="Apple revenue increased",
        ticker="AAPL",
        filing_type="10-K",
        filing_year=2024,
        heading="Revenue",
        chunk_index=5,
        rrf_score=0.95,
    ))
    reg.register(RetrievedPassage(
        chunk_id="chunk-2",
        document_id="doc-1",
        text="Services segment grew",
        ticker="AAPL",
        filing_type="10-K",
        filing_year=2024,
        heading="Revenue",
        chunk_index=6,
        rrf_score=0.87,
    ))
    return reg


def test_valid_answer_with_citations(registry_with_passages):
    """Valid answer with citations in registry."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="Apple [1] and Services [2] grew.",
        citations=[
            Citation(citation_index=1, chunk_id=UUID("00000000-0000-0000-0000-000000000001"), excerpt="Apple revenue"),
            Citation(citation_index=2, chunk_id=UUID("00000000-0000-0000-0000-000000000002"), excerpt="Services grew"),
        ],
        insufficient_evidence=False,
    )
    # Register with correct IDs for validation
    registry_with_passages.passages_by_chunk_id["00000000-0000-0000-0000-000000000001"] = \
        registry_with_passages.passages_by_chunk_id.pop("chunk-1")
    registry_with_passages.passages_by_chunk_id["00000000-0000-0000-0000-000000000002"] = \
        registry_with_passages.passages_by_chunk_id.pop("chunk-2")

    result = validator.validate(answer, registry_with_passages)
    assert result.ok is True
    assert len(result.errors) == 0


def test_insufficient_evidence_with_citations():
    """insufficient_evidence=True but citations present → fails."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="Not enough evidence.",
        citations=[Citation(citation_index=1, chunk_id=UUID("00000000-0000-0000-0000-000000000001"), excerpt="some text")],
        insufficient_evidence=True,
    )
    registry = TurnRegistry()

    result = validator.validate(answer, registry)
    assert result.ok is False
    assert any("insufficient_evidence=True" in e for e in result.errors)


def test_no_citations_and_not_insufficient_evidence():
    """No citations when insufficient_evidence=False → fails."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="Some answer.",
        citations=[],
        insufficient_evidence=False,
    )
    registry = TurnRegistry()

    result = validator.validate(answer, registry)
    assert result.ok is False
    assert any("No citations" in e for e in result.errors)


def test_non_contiguous_citation_indices():
    """Citation indices jump from [1] to [3] → fails."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="First [1] and third [3].",
        citations=[
            Citation(citation_index=1, chunk_id=UUID("00000000-0000-0000-0000-000000000001"), excerpt="first"),
            Citation(citation_index=3, chunk_id=UUID("00000000-0000-0000-0000-000000000003"), excerpt="third"),
        ],
        insufficient_evidence=False,
    )
    registry = TurnRegistry()

    result = validator.validate(answer, registry)
    assert result.ok is False
    assert any("contiguous" in e.lower() for e in result.errors)


def test_marker_mismatch():
    """Answer has [1] and [2] but citations only have [1] → fails."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="One [1] and two [2].",
        citations=[
            Citation(citation_index=1, chunk_id=UUID("00000000-0000-0000-0000-000000000001"), excerpt="one"),
        ],
        insufficient_evidence=False,
    )
    registry = TurnRegistry()

    result = validator.validate(answer, registry)
    assert result.ok is False
    assert any("[n] markers" in e for e in result.errors)


def test_chunk_not_in_registry():
    """Citation references chunk_id not in registry → fails."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="Text [1].",
        citations=[
            Citation(citation_index=1, chunk_id=UUID("00000000-0000-0000-0000-000000000099"), excerpt="text"),
        ],
        insufficient_evidence=False,
    )
    registry = TurnRegistry()

    result = validator.validate(answer, registry)
    assert result.ok is False
    assert any("not in the registry" in e for e in result.errors)


def test_empty_answer_text():
    """Empty answer text → fails."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="",
        citations=[],
        insufficient_evidence=False,
    )
    registry = TurnRegistry()

    result = validator.validate(answer, registry)
    assert result.ok is False
    assert any("empty" in e.lower() for e in result.errors)


def test_insufficient_evidence_accepted():
    """insufficient_evidence=True with empty citations → passes."""
    validator = GroundingValidator(None)
    answer = GroundedAnswer(
        answer="The corpus does not contain information about this.",
        citations=[],
        insufficient_evidence=True,
    )
    registry = TurnRegistry()

    result = validator.validate(answer, registry)
    assert result.ok is True
    assert len(result.errors) == 0
