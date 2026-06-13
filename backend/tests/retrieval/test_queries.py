"""Unit tests for retrieval queries (semantic and full-text)."""

from unittest.mock import MagicMock
import pytest
from sqlalchemy import text

from app.retrieval.queries import ChunkRow, semantic_search, fulltext_search


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session."""
    return MagicMock()


def test_semantic_search_construction(mock_db):
    """Verify semantic search constructs correct SQL and parameter binding."""
    mock_rows = [
        MagicMock(
            chunk_id="chunk-1",
            document_id="doc-1",
            text="Apple iPhone revenue",
            chunk_metadata={"ticker": "AAPL"},
            score=0.95,
        ),
        MagicMock(
            chunk_id="chunk-2",
            document_id="doc-1",
            text="Services segment growth",
            chunk_metadata={"ticker": "AAPL"},
            score=0.87,
        ),
    ]
    mock_db.execute.return_value = mock_rows

    embedding = [0.1] * 1536
    results = semantic_search(mock_db, embedding, top_k=2)

    assert len(results) == 2
    assert results[0].chunk_id == "chunk-1"
    assert results[0].score == 0.95
    assert results[1].chunk_id == "chunk-2"
    assert results[1].score == 0.87

    call_args = mock_db.execute.call_args
    assert call_args is not None
    sql_query = call_args[0][0]
    params = call_args[0][1]

    assert "embedding <=> :embedding::vector" in str(sql_query)
    assert ":top_k" in str(sql_query)
    assert params["top_k"] == 2


def test_fulltext_search_construction(mock_db):
    """Verify full-text search constructs correct SQL and parameter binding."""
    mock_rows = [
        MagicMock(
            chunk_id="chunk-3",
            document_id="doc-2",
            text="Amazon AWS revenue increase",
            chunk_metadata={"ticker": "AMZN"},
            score=0.92,
        ),
    ]
    mock_db.execute.return_value = mock_rows

    query_text = "AWS revenue"
    results = fulltext_search(mock_db, query_text, top_k=5)

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-3"
    assert results[0].chunk_metadata.get("ticker") == "AMZN"

    call_args = mock_db.execute.call_args
    assert call_args is not None
    sql_query = call_args[0][0]
    params = call_args[0][1]

    assert "plainto_tsquery" in str(sql_query)
    assert "@@ plainto_tsquery" in str(sql_query)
    assert params["query"] == query_text
    assert params["top_k"] == 5


def test_chunk_row_dataclass():
    """ChunkRow should correctly hold chunk metadata."""
    chunk = ChunkRow(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="Test text",
        chunk_metadata={"ticker": "AAPL", "chunk_index": 5},
        score=0.85,
    )

    assert chunk.chunk_id == "chunk-1"
    assert chunk.document_id == "doc-1"
    assert chunk.chunk_metadata["ticker"] == "AAPL"
