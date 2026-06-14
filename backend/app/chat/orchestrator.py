"""Orchestration of a single chat turn: retrieval → agent → validation → streaming → persistence."""

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy.orm import Session
from openai import OpenAI

from app.database.models.chat import ChatThread, ChatMessage
from app.database.models.citations import MessageCitation
from app.database.models.users import User
from app.assistant.agent import run_document_agent
from app.assistant.deps import DocumentAgentDeps, TurnRegistry
from app.assistant.outputs import GroundedAnswer
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever
from app.chat.streaming import text_event, data_event, error_event, citation_data_event
from app.utils.tokens import count_tokens
from uuid import UUID

log = logging.getLogger(__name__)


MAX_RETRIES = 2


def generate_thread_title(response: str) -> str:
    """Generate a thread title from the first assistant response.

    Prefers markdown headings, falls back to first line, or default.
    """
    lines = [line.strip() for line in response.splitlines() if line.strip()]

    # Prefer first markdown heading
    for line in lines:
        if line.startswith("#"):
            return line.lstrip("#").strip()[:255]

    # Otherwise first non-empty line
    if lines:
        return lines[0][:255]

    return "New Chat"


async def run_turn(
    user_message: str,
    thread: ChatThread,
    user: User,
    db: Session,
    retriever: DocumentRetriever,
    openai_client: OpenAI,
) -> AsyncGenerator[str, None]:
    """Execute one turn of the chat: agent reasoning → validation → streaming → persistence.

    Args:
        user_message: The user's input query
        thread: The chat thread
        user: The authenticated user
        db: Database session
        retriever: Document retriever for tools
        openai_client: OpenAI client (for grounding validator, optional)

    Yields:
        SSE events (0:, d:, e: format)
    """
    if not user_message.strip():
        yield error_event("Empty message")
        return

    # Log input tokens
    user_msg_tokens = count_tokens(user_message)
    log.info(f"[TURN] Starting turn for query: {user_message[:50]}")
    log.info(f"[TURN] User message: {user_msg_tokens} tokens")

    # Load instructions size for reference
    from app.assistant.agent import INSTRUCTIONS
    instr_tokens = count_tokens(INSTRUCTIONS)
    log.info(f"[TURN] System instructions: {instr_tokens} tokens")

    status_queue: asyncio.Queue[str] = asyncio.Queue()

    def on_status(msg: str):
        """Queue status update for later emission."""
        status_queue.put_nowait(msg)

    validator = GroundingValidator(openai_client)
    grounded: GroundedAnswer | None = None
    valid = False

    # Retry loop for validation
    for attempt in range(MAX_RETRIES + 1):
        log.info(f"[TURN] Validation attempt {attempt + 1}/{MAX_RETRIES + 1}")
        registry = TurnRegistry()
        deps = DocumentAgentDeps(
            retriever=retriever,
            registry=registry,
            db=db,
            thread_id=thread.id,
            user_id=user.id,
            on_status=on_status,
        )

        # Run agent in thread (sync blocking call)
        log.info(f"[TURN] About to run agent")
        try:
            grounded, metadata = await run_document_agent(user_message, deps)
            log.info(f"[TURN] Agent completed successfully")
        except Exception as e:
            log.error(f"[TURN] Agent error: {e}", exc_info=True)
            yield error_event(f"Agent error: {e}")
            return

        # Validate citations
        validation = validator.validate(grounded, registry)
        if validation.ok:
            valid = True
            break

        if attempt < MAX_RETRIES:
            on_status(f"Validation failed (attempt {attempt + 1}), retrying...")
        else:
            yield error_event(f"Grounding validation failed after {MAX_RETRIES} retries: {'; '.join(validation.errors)}")
            return

    if not valid:
        return

    # Emit any queued status events
    while not status_queue.empty():
        yield data_event({"type": "status", "message": status_queue.get_nowait()})

    # If insufficient evidence, stream a clear message
    if grounded.insufficient_evidence:
        full_text = grounded.answer if grounded.answer.strip() else "Unable to find relevant information in the available filings to answer this question."
    else:
        full_text = grounded.answer
    for word in full_text.split():
        yield text_event(word + " ")
        await asyncio.sleep(0.01)

    # Stream citation events
    for citation in grounded.citations:
        passage = registry.get(str(citation.chunk_id))
        if passage:
            yield citation_data_event(citation, passage)

    # Persist assistant message + citations to database
    try:
        msg = ChatMessage(thread_id=thread.id, role="assistant", content=full_text)
        db.add(msg)
        db.flush()  # Get msg.id

        for citation in grounded.citations:
            passage = registry.get(str(citation.chunk_id))
            db.add(
                MessageCitation(
                    message_id=msg.id,
                    chunk_id=citation.chunk_id,  # already UUID in Citation
                    section=passage.heading if passage else None,
                )
            )

        # Auto-title thread from first assistant response
        if not thread.title or thread.title == "New Chat":
            thread.title = generate_thread_title(full_text)
            log.info(f"[TURN] Auto-titled thread: {thread.title}")

        thread.updated_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        db.rollback()
        yield error_event(f"Persistence error: {e}")
