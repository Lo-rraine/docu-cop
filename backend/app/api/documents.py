"""Document chunk context API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.chat import get_current_user_from_cookies
from app.database import get_db
from app.database.models.users import User
from app.database.documents import fetch_chunk_by_id, fetch_neighboring_chunks

router = APIRouter()


class ChunkDetail(BaseModel):
    """Details of a document chunk."""
    chunk_id: str
    text: str
    ticker: str
    filing_type: str
    filing_year: int
    heading: str | None
    chunk_index: int


class ChunkContextResponse(BaseModel):
    """Chunk with surrounding context."""
    chunk: ChunkDetail
    prev: ChunkDetail | None
    next: ChunkDetail | None


@router.get("/chunks/{chunk_id}/context", response_model=ChunkContextResponse)
async def get_chunk_context(
    chunk_id: str,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ChunkContextResponse:
    """Get a chunk with previous and next context chunks.

    Auth: HttpOnly cookie only (same as /chat/stream).

    Args:
        chunk_id: UUID of the chunk to retrieve

    Returns:
        Chunk with optional prev/next neighbors

    Raises:
        401: Unauthenticated
        404: Chunk not found
    """
    # Verify user is authenticated
    user = get_current_user_from_cookies(http_request, db)

    # Fetch the center chunk
    try:
        chunk_uuid = UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chunk ID format")

    center = fetch_chunk_by_id(db, chunk_id)
    if not center:
        raise HTTPException(status_code=404, detail="Chunk not found")

    # Fetch neighbors
    min_idx = max(0, center.chunk_index - 1)
    max_idx = center.chunk_index + 1
    neighbors = fetch_neighboring_chunks(db, center.document_id, min_idx, max_idx)

    # Organize neighbors (prev, center, next)
    prev_chunk = None
    next_chunk = None
    for n in neighbors:
        if n.chunk_index == center.chunk_index - 1:
            prev_chunk = n
        elif n.chunk_index == center.chunk_index + 1:
            next_chunk = n

    return ChunkContextResponse(
        chunk=ChunkDetail(
            chunk_id=center.chunk_id,
            text=center.text,
            ticker=center.ticker,
            filing_type=center.filing_type,
            filing_year=center.filing_year,
            heading=center.heading,
            chunk_index=center.chunk_index,
        ),
        prev=ChunkDetail(
            chunk_id=prev_chunk.chunk_id,
            text=prev_chunk.text,
            ticker=prev_chunk.ticker,
            filing_type=prev_chunk.filing_type,
            filing_year=prev_chunk.filing_year,
            heading=prev_chunk.heading,
            chunk_index=prev_chunk.chunk_index,
        ) if prev_chunk else None,
        next=ChunkDetail(
            chunk_id=next_chunk.chunk_id,
            text=next_chunk.text,
            ticker=next_chunk.ticker,
            filing_type=next_chunk.filing_type,
            filing_year=next_chunk.filing_year,
            heading=next_chunk.heading,
            chunk_index=next_chunk.chunk_index,
        ) if next_chunk else None,
    )
