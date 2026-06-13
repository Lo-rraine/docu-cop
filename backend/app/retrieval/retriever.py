"""Hybrid retrieval orchestrator: semantic + full-text + RRF fusion."""

from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.queries import fulltext_search, semantic_search


@dataclass
class RetrievedPassage:
    """A retrieved document chunk with metadata and retrieval score."""
    chunk_id: str
    document_id: str
    text: str
    ticker: str
    filing_type: str
    filing_year: int
    heading: Optional[str]
    chunk_index: int
    rrf_score: float
    is_neighbor: bool = False


class DocumentRetriever:
    """Orchestrates hybrid retrieval: semantic + keyword search with RRF fusion."""

    def __init__(
        self,
        openai_client: OpenAI,
        semantic_k: int = 20,
        fulltext_k: int = 20,
        embedding_model: str = settings.openai_embedding_model,
    ):
        self.openai_client = openai_client
        self.semantic_k = semantic_k
        self.fulltext_k = fulltext_k
        self.embedding_model = embedding_model

    def retrieve(
        self,
        query: str,
        db: Session,
        top_k: int = 10,
        neighbor_window: int = 1,
    ) -> list[RetrievedPassage]:
        """Retrieve relevant passages using hybrid search.

        Args:
            query: User query (natural language).
            db: SQLAlchemy session.
            top_k: Number of top results to return (before neighbor expansion).
            neighbor_window: Number of adjacent chunks to include as context (±window).

        Returns:
            List of RetrievedPassage, ordered by RRF score descending.
        """
        embedding = self._embed_query(query)

        semantic_results = semantic_search(db, embedding, top_k=self.semantic_k)
        fulltext_results = fulltext_search(db, query, top_k=self.fulltext_k)

        semantic_ids = [row.chunk_id for row in semantic_results]
        fulltext_ids = [row.chunk_id for row in fulltext_results]

        fused = reciprocal_rank_fusion([semantic_ids, fulltext_ids])

        top_chunk_ids = [chunk_id for chunk_id, _ in fused[:top_k]]

        passages = self._fetch_passages(db, top_chunk_ids, is_neighbor=False)

        if neighbor_window > 0:
            already_fetched = {p.chunk_id for p in passages}
            neighbor_ids = self._expand_neighbors(db, passages, neighbor_window)
            neighbor_ids = [nid for nid in neighbor_ids if nid not in already_fetched]
            neighbors = self._fetch_passages(db, neighbor_ids, is_neighbor=True)
            passages.extend(neighbors)

        sorted_passages = sorted(passages, key=lambda p: p.rrf_score, reverse=True)

        return sorted_passages

    def _embed_query(self, query: str) -> list[float]:
        """Embed query using OpenAI embedding model."""
        response = self.openai_client.embeddings.create(
            input=query,
            model=self.embedding_model,
        )
        return response.data[0].embedding

    def _fetch_passages(
        self,
        db: Session,
        chunk_ids: list[str],
        is_neighbor: bool = False,
    ) -> list[RetrievedPassage]:
        """Fetch full chunk rows and build RetrievedPassage objects."""
        if not chunk_ids:
            return []

        query = text(
            f"""
            SELECT
                id::text,
                document_id::text,
                text,
                chunk_metadata,
                source_documents.ticker,
                source_documents.filing_type,
                source_documents.filing_year
            FROM document_chunks
            LEFT JOIN source_documents ON document_chunks.document_id = source_documents.id
            WHERE id::text IN ({','.join([f"'{cid}'" for cid in chunk_ids])})
            """
        )

        rows = db.execute(query)

        rrf_scores = {chunk_ids[i]: 1.0 / (60 + i + 1) for i in range(len(chunk_ids))}

        passages = []
        for row in rows:
            metadata = row.chunk_metadata or {}
            passages.append(
                RetrievedPassage(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    text=row.text,
                    ticker=row.ticker or "UNKNOWN",
                    filing_type=row.filing_type or "UNKNOWN",
                    filing_year=row.filing_year or 0,
                    heading=metadata.get("heading"),
                    chunk_index=int(metadata.get("chunk_index", -1)),
                    rrf_score=rrf_scores.get(row.id, 0.0),
                    is_neighbor=is_neighbor,
                )
            )

        return passages

    def _expand_neighbors(
        self,
        db: Session,
        passages: list[RetrievedPassage],
        neighbor_window: int,
    ) -> list[str]:
        """Find neighboring chunk IDs for context."""
        neighbor_ids = set()

        for passage in passages:
            if passage.is_neighbor:
                continue

            min_idx = max(0, passage.chunk_index - neighbor_window)
            max_idx = passage.chunk_index + neighbor_window

            query = text(
                """
                SELECT id::text
                FROM document_chunks
                WHERE document_id = :doc_id
                  AND (chunk_metadata->>'chunk_index')::int BETWEEN :min_idx AND :max_idx
                ORDER BY (chunk_metadata->>'chunk_index')::int
                """
            )

            rows = db.execute(
                query,
                {
                    "doc_id": passage.document_id,
                    "min_idx": min_idx,
                    "max_idx": max_idx,
                },
            )

            for row in rows:
                neighbor_ids.add(row.id)

        return list(neighbor_ids)
