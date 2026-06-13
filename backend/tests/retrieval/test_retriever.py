"""Unit tests for DocumentRetriever orchestration."""

from unittest.mock import MagicMock, patch
import pytest

from app.retrieval.retriever import DocumentRetriever, RetrievedPassage


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    client = MagicMock()
    client.embeddings.create.return_value.data = [
        MagicMock(embedding=[0.1] * 1536)
    ]
    return client


@pytest.fixture
def retriever(mock_openai_client):
    """DocumentRetriever instance with mocked OpenAI."""
    return DocumentRetriever(mock_openai_client, semantic_k=5, fulltext_k=5)


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session."""
    return MagicMock()


def test_retrieve_calls_embedding(retriever, mock_db, mock_openai_client):
    """retrieve() should embed the query."""
    with patch("app.retrieval.retriever.semantic_search") as mock_sem, \
         patch("app.retrieval.retriever.fulltext_search") as mock_ft, \
         patch("app.retrieval.retriever.reciprocal_rank_fusion") as mock_rrf:

        mock_sem.return_value = []
        mock_ft.return_value = []
        mock_rrf.return_value = []

        retriever.retrieve("test query", mock_db)

        mock_openai_client.embeddings.create.assert_called_once()
        call_kwargs = mock_openai_client.embeddings.create.call_args[1]
        assert call_kwargs["input"] == "test query"


def test_retrieve_calls_both_search_methods(retriever, mock_db, mock_openai_client):
    """retrieve() should call both semantic and full-text search."""
    with patch("app.retrieval.retriever.semantic_search") as mock_sem, \
         patch("app.retrieval.retriever.fulltext_search") as mock_ft, \
         patch("app.retrieval.retriever.reciprocal_rank_fusion") as mock_rrf:

        mock_sem.return_value = []
        mock_ft.return_value = []
        mock_rrf.return_value = []

        retriever.retrieve("test query", mock_db)

        mock_sem.assert_called_once()
        mock_ft.assert_called_once()


def test_retrieve_fuses_results(retriever, mock_db, mock_openai_client):
    """retrieve() should fuse semantic and full-text results."""
    with patch("app.retrieval.retriever.semantic_search") as mock_sem, \
         patch("app.retrieval.retriever.fulltext_search") as mock_ft, \
         patch("app.retrieval.retriever.reciprocal_rank_fusion") as mock_rrf:

        mock_sem.return_value = []
        mock_ft.return_value = []
        mock_rrf.return_value = []

        retriever.retrieve("test query", mock_db)

        mock_rrf.assert_called_once()
        fused_call = mock_rrf.call_args[0][0]
        assert isinstance(fused_call, list)
        assert len(fused_call) == 2


def test_retrieve_limits_top_k(retriever, mock_db, mock_openai_client):
    """retrieve() should respect top_k parameter before neighbor expansion."""
    with patch("app.retrieval.retriever.semantic_search") as mock_sem, \
         patch("app.retrieval.retriever.fulltext_search") as mock_ft, \
         patch("app.retrieval.retriever.reciprocal_rank_fusion") as mock_rrf, \
         patch.object(retriever, "_fetch_passages") as mock_fetch, \
         patch.object(retriever, "_expand_neighbors") as mock_expand:

        mock_sem.return_value = []
        mock_ft.return_value = []
        fused_ids = [("chunk-1", 1.0), ("chunk-2", 0.9), ("chunk-3", 0.8)]
        mock_rrf.return_value = fused_ids
        mock_fetch.side_effect = [[], []]
        mock_expand.return_value = []

        retriever.retrieve("test", mock_db, top_k=2)

        mock_fetch_call = mock_fetch.call_args_list[0]
        chunk_ids_arg = mock_fetch_call[0][1]
        assert len(chunk_ids_arg) == 2


def test_retrieved_passage_dataclass():
    """RetrievedPassage should store passage metadata."""
    passage = RetrievedPassage(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="Apple revenue",
        ticker="AAPL",
        filing_type="10-K",
        filing_year=2024,
        heading="Revenue",
        chunk_index=5,
        rrf_score=0.95,
        is_neighbor=False,
    )

    assert passage.chunk_id == "chunk-1"
    assert passage.ticker == "AAPL"
    assert passage.rrf_score == 0.95
    assert passage.is_neighbor is False
