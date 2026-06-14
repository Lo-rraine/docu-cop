"""Dependencies and context for the document agent."""

from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.retrieval.retriever import DocumentRetriever, RetrievedPassage


@dataclass
class TurnRegistry:
    """Citation allowlist — tools register passages here; validator checks against it."""

    passages_by_chunk_id: dict[str, RetrievedPassage] = field(default_factory=dict)

    def register(self, passage: RetrievedPassage) -> None:
        """Register a single passage."""
        self.passages_by_chunk_id[passage.chunk_id] = passage

    def register_many(self, passages: list[RetrievedPassage]) -> None:
        """Register multiple passages."""
        for p in passages:
            self.register(p)

    def get(self, chunk_id: str) -> RetrievedPassage | None:
        """Retrieve a registered passage by chunk_id."""
        return self.passages_by_chunk_id.get(chunk_id)


@dataclass
class DocumentAgentDeps:
    """Dependencies injected into the document agent."""

    retriever: DocumentRetriever
    registry: TurnRegistry
    db: Session
    thread_id: UUID
    user_id: UUID
    on_status: Callable[[str], None] | None = None

    def emit_status(self, message: str) -> None:
        """Emit a status update via the registered callback."""
        if self.on_status:
            self.on_status(message)
