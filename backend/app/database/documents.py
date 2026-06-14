"""Shared document chunk query helpers."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.retriever import RetrievedPassage


def fetch_chunk_by_id(db: Session, chunk_id: str) -> RetrievedPassage | None:
    """Fetch a single chunk by ID from the database."""
    query = text(
        """
        SELECT
            id::text AS chunk_id,
            document_id::text AS document_id,
            text,
            chunk_metadata,
            source_documents.ticker,
            source_documents.filing_type,
            source_documents.filing_year
        FROM document_chunks
        LEFT JOIN source_documents ON document_chunks.document_id = source_documents.id
        WHERE id::text = :chunk_id
        """
    )

    row = db.execute(query, {"chunk_id": chunk_id}).first()
    if not row:
        return None

    metadata = row.chunk_metadata or {}
    return RetrievedPassage(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        text=row.text,
        ticker=row.ticker or "UNKNOWN",
        filing_type=row.filing_type or "UNKNOWN",
        filing_year=row.filing_year or 0,
        heading=metadata.get("heading"),
        chunk_index=int(metadata.get("chunk_index", -1)),
        rrf_score=1.0,
        is_neighbor=False,
    )


def fetch_neighboring_chunks(
    db: Session, document_id: str, min_idx: int, max_idx: int
) -> list[RetrievedPassage]:
    """Fetch chunks from a document within an index range."""
    query = text(
        """
        SELECT
            id::text AS chunk_id,
            document_id::text AS document_id,
            text,
            chunk_metadata,
            source_documents.ticker,
            source_documents.filing_type,
            source_documents.filing_year
        FROM document_chunks
        LEFT JOIN source_documents ON document_chunks.document_id = source_documents.id
        WHERE document_id::text = :document_id
          AND (chunk_metadata->>'chunk_index')::int BETWEEN :min_idx AND :max_idx
        ORDER BY (chunk_metadata->>'chunk_index')::int
        """
    )

    rows = db.execute(
        query,
        {"document_id": document_id, "min_idx": min_idx, "max_idx": max_idx},
    )

    passages = []
    for row in rows:
        metadata = row.chunk_metadata or {}
        passages.append(
            RetrievedPassage(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                text=row.text,
                ticker=row.ticker or "UNKNOWN",
                filing_type=row.filing_type or "UNKNOWN",
                filing_year=row.filing_year or 0,
                heading=metadata.get("heading"),
                chunk_index=int(metadata.get("chunk_index", -1)),
                rrf_score=1.0,
                is_neighbor=True,
            )
        )

    return passages
