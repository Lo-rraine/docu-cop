"""Raw SQL queries for pgvector semantic search and Postgres full-text search."""

from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class ChunkRow:
    """Result row from a chunk search query."""
    chunk_id: str
    document_id: str
    text: str
    chunk_metadata: dict
    score: float


def semantic_search(
    db: Session, query_embedding: list[float], top_k: int = 20
) -> list[ChunkRow]:
    """Semantic search using pgvector cosine similarity.

    Args:
        db: SQLAlchemy session.
        query_embedding: Query embedding vector (1536 dims).
        top_k: Number of results to return.

    Returns:
        Sorted list of ChunkRow, ordered by similarity descending.
    """
    query = text(
        """
        SELECT
            id::text AS chunk_id,
            document_id::text AS document_id,
            text,
            chunk_metadata,
            (1 - (embedding <=> :embedding::vector)) AS score
        FROM document_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :embedding::vector
        LIMIT :top_k
        """
    )

    embedding_str = str(query_embedding)
    rows = db.execute(query, {"embedding": embedding_str, "top_k": top_k})

    return [
        ChunkRow(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            text=row.text,
            chunk_metadata=row.chunk_metadata or {},
            score=row.score,
        )
        for row in rows
    ]


def fulltext_search(
    db: Session, query_text: str, top_k: int = 20
) -> list[ChunkRow]:
    """Full-text search using Postgres tsvector and ts_rank.

    Uses plainto_tsquery (safe for free-form queries, strips operators).

    Args:
        db: SQLAlchemy session.
        query_text: Search query.
        top_k: Number of results to return.

    Returns:
        Sorted list of ChunkRow, ordered by rank descending.
    """
    query = text(
        """
        SELECT
            id::text AS chunk_id,
            document_id::text AS document_id,
            text,
            chunk_metadata,
            ts_rank(search_vector, plainto_tsquery('english', :query)) AS score
        FROM document_chunks
        WHERE search_vector @@ plainto_tsquery('english', :query)
        ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
        LIMIT :top_k
        """
    )

    rows = db.execute(query, {"query": query_text, "top_k": top_k})

    return [
        ChunkRow(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            text=row.text,
            chunk_metadata=row.chunk_metadata or {},
            score=row.score,
        )
        for row in rows
    ]
