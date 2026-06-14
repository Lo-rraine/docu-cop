"""Structured output models for the document agent."""

from uuid import UUID
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A single citation linking a claim to a source passage."""
    citation_index: int = Field(..., ge=1)  # 1-based, matches [n] marker in answer
    chunk_id: UUID
    excerpt: str = Field(..., max_length=125)  # verbatim quote, max 125 chars


class GroundedAnswer(BaseModel):
    """Structured answer from the document agent with citations."""
    answer: str  # plain-English with inline [n] markers
    citations: list[Citation] = Field(default_factory=list)
    insufficient_evidence: bool = False  # True if agent couldn't find support
