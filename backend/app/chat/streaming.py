"""AI SDK-compatible SSE streaming utilities."""

import json

from app.assistant.outputs import Citation
from app.retrieval.retriever import RetrievedPassage


def text_event(token: str) -> str:
    """Emit a text delta event (AI SDK code 0)."""
    return f'0:{json.dumps(token)}\n'


def data_event(payload: dict) -> str:
    """Emit a data event (AI SDK code d, e.g. for citations)."""
    return f'd:{json.dumps(payload)}\n'


def error_event(message: str) -> str:
    """Emit an error event (AI SDK code e)."""
    return f'e:{json.dumps(message)}\n'


def citation_data_event(citation: Citation, passage: RetrievedPassage) -> str:
    """Emit a citation as a data event with passage metadata."""
    return data_event({
        "type": "citation",
        "data": {
            "citation_index": citation.citation_index,
            "chunk_id": str(citation.chunk_id),
            "excerpt": citation.excerpt,
            "ticker": passage.ticker,
            "filing_type": passage.filing_type,
            "filing_year": passage.filing_year,
            "heading": passage.heading,
        }
    })
