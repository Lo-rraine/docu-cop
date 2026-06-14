"""Unit tests for streaming utilities."""

import json
from uuid import UUID

from app.chat.streaming import text_event, data_event, error_event, citation_data_event
from app.assistant.outputs import Citation
from app.retrieval.retriever import RetrievedPassage


def test_text_event():
    """text_event formats as 0:json(token)."""
    event = text_event("hello ")
    assert event == '0:"hello "\n'


def test_data_event():
    """data_event formats as d:json(payload)."""
    payload = {"type": "status", "message": "searching"}
    event = data_event(payload)
    assert event.startswith("d:")
    assert event.endswith("\n")
    data = json.loads(event[2:-1])
    assert data["type"] == "status"
    assert data["message"] == "searching"


def test_error_event():
    """error_event formats as e:json(message)."""
    event = error_event("something went wrong")
    assert event == 'e:"something went wrong"\n'


def test_citation_data_event():
    """citation_data_event includes citation and passage metadata."""
    citation = Citation(
        citation_index=1,
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        excerpt="Apple revenue increased"
    )
    passage = RetrievedPassage(
        chunk_id="00000000-0000-0000-0000-000000000001",
        document_id="doc-1",
        text="Apple revenue increased by 10%",
        ticker="AAPL",
        filing_type="10-K",
        filing_year=2024,
        heading="Revenue",
        chunk_index=5,
        rrf_score=0.95,
    )

    event = citation_data_event(citation, passage)
    assert event.startswith("d:")
    data = json.loads(event[2:-1])

    assert data["type"] == "citation"
    assert data["data"]["citation_index"] == 1
    assert data["data"]["ticker"] == "AAPL"
    assert data["data"]["filing_type"] == "10-K"
    assert data["data"]["filing_year"] == 2024
    assert data["data"]["excerpt"] == "Apple revenue increased"
