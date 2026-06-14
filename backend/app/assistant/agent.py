"""PydanticAI document agent definition and tools."""

from pathlib import Path
from uuid import UUID
import asyncio
from typing import Optional

from pydantic_ai import Agent, RunContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.assistant.deps import DocumentAgentDeps, TurnRegistry
from app.assistant.outputs import GroundedAnswer
from app.retrieval.retriever import RetrievedPassage
from app.database.documents import fetch_chunk_by_id, fetch_neighboring_chunks

# Load instructions from markdown file
_INSTRUCTIONS_PATH = Path(__file__).parent / "instructions.md"
INSTRUCTIONS = _INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def get_document_agent() -> Agent[DocumentAgentDeps, GroundedAnswer]:
    """Create and configure the document agent."""
    model_name = f'openai:{settings.openai_chat_model}'
    agent = Agent(
        model_name,
        deps_type=DocumentAgentDeps,
        output_type=GroundedAnswer,
        instructions=INSTRUCTIONS,
    )

    # Register tools
    @agent.tool
    def search_filings(
        ctx: RunContext[DocumentAgentDeps],
        query: str,
        ticker: Optional[str] = None,
        filing_type: Optional[str] = None,
        year: Optional[int] = None,
        top_k: int = 10,
    ) -> str:
        """Search SEC filings for relevant passages using hybrid search.

        Args:
            query: Natural-language search term
            ticker: Optional company ticker filter (e.g., "AAPL")
            filing_type: Optional filter (e.g., "10-K", "10-Q")
            year: Optional year filter (e.g., 2024)
            top_k: Number of results to return

        Returns:
            Formatted list of relevant passages with chunk IDs and excerpts
        """
        ctx.deps.emit_status(f"search_filings: searching for '{query}'")

        passages = ctx.deps.retriever.retrieve(query, ctx.deps.db, top_k=top_k)

        # Apply optional filters
        if ticker:
            passages = [p for p in passages if p.ticker.upper() == ticker.upper()]
        if filing_type:
            passages = [p for p in passages if p.filing_type == filing_type]
        if year:
            passages = [p for p in passages if p.filing_year == year]

        # Register passages in the registry (citation allowlist)
        ctx.deps.registry.register_many(passages)

        # Format for agent consumption
        result = []
        for i, p in enumerate(passages[:top_k], 1):
            result.append(
                f"[{i}] {p.ticker} {p.filing_type} {p.filing_year}\n"
                f"Section: {p.heading or 'N/A'}\n"
                f"Chunk ID: {p.chunk_id}\n"
                f"Text: {p.text}\n"
            )

        ctx.deps.emit_status(f"search_filings: found {len(passages)} passages")
        return "\n".join(result)

    @agent.tool
    def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: str) -> str:
        """Retrieve a specific document chunk by ID.

        Args:
            chunk_id: UUID of the chunk to retrieve

        Returns:
            Formatted chunk text with metadata, or error message if not found
        """
        try:
            chunk_uuid = UUID(chunk_id)
        except ValueError:
            return f"Invalid chunk ID format: {chunk_id}"

        ctx.deps.emit_status(f"read_chunk: fetching {chunk_id}")

        passage = fetch_chunk_by_id(ctx.deps.db, str(chunk_uuid))
        if not passage:
            return f"Chunk {chunk_id} not found"

        ctx.deps.registry.register(passage)
        return (
            f"{passage.ticker} {passage.filing_type} {passage.filing_year}\n"
            f"Section: {passage.heading or 'N/A'}\n"
            f"Text: {passage.text}"
        )

    @agent.tool
    def read_chunks(ctx: RunContext[DocumentAgentDeps], chunk_ids: list[str]) -> str:
        """Retrieve multiple document chunks by ID.

        Args:
            chunk_ids: List of chunk UUIDs

        Returns:
            Formatted chunk texts with metadata
        """
        ctx.deps.emit_status(f"read_chunks: fetching {len(chunk_ids)} chunks")

        results = []
        for chunk_id in chunk_ids:
            try:
                chunk_uuid = UUID(chunk_id)
            except ValueError:
                results.append(f"Invalid chunk ID: {chunk_id}")
                continue

            passage = fetch_chunk_by_id(ctx.deps.db, str(chunk_uuid))
            if not passage:
                results.append(f"Chunk {chunk_id} not found")
                continue

            ctx.deps.registry.register(passage)
            results.append(
                f"{passage.ticker} {passage.filing_type} {passage.filing_year}\n"
                f"Section: {passage.heading or 'N/A'}\n"
                f"Text: {passage.text}"
            )

        return "\n\n---\n\n".join(results)

    @agent.tool
    def read_surrounding_chunks(
        ctx: RunContext[DocumentAgentDeps],
        chunk_id: str,
        radius: int = 1,
    ) -> str:
        """Retrieve neighboring chunks for context.

        Args:
            chunk_id: UUID of the center chunk
            radius: How many chunks to fetch on each side (±radius)

        Returns:
            Formatted list of surrounding chunks
        """
        try:
            chunk_uuid = UUID(chunk_id)
        except ValueError:
            return f"Invalid chunk ID format: {chunk_id}"

        ctx.deps.emit_status(f"read_surrounding_chunks: fetching neighbors of {chunk_id}")

        # First, get the center chunk to find its document_id and chunk_index
        center = fetch_chunk_by_id(ctx.deps.db, str(chunk_uuid))
        if not center:
            return f"Center chunk {chunk_id} not found"

        ctx.deps.registry.register(center)

        # Now fetch neighbors by (document_id, chunk_index ± radius)
        min_idx = max(0, center.chunk_index - radius)
        max_idx = center.chunk_index + radius

        neighbors = fetch_neighboring_chunks(ctx.deps.db, center.document_id, min_idx, max_idx)
        ctx.deps.registry.register_many(neighbors)

        results = [
            f"{n.ticker} {n.filing_type} {n.filing_year}\n"
            f"Section: {n.heading or 'N/A'}\n"
            f"Chunk {n.chunk_index}: {n.text}"
            for n in neighbors
        ]

        ctx.deps.emit_status(f"read_surrounding_chunks: found {len(neighbors)} neighbors")
        return "\n\n---\n\n".join(results)

    return agent


# Singleton agent instance
_agent: Agent[DocumentAgentDeps, GroundedAnswer] | None = None


def get_agent() -> Agent[DocumentAgentDeps, GroundedAnswer]:
    """Get or create the singleton document agent."""
    global _agent
    if _agent is None:
        _agent = get_document_agent()
    return _agent


async def run_document_agent(
    query: str, deps: DocumentAgentDeps
) -> tuple[GroundedAnswer, dict]:
    """Execute the agent (async wrapper)."""
    deps.emit_status("agent:start")

    def run_sync():
        return get_agent().run_sync(query, deps=deps)

    # Run in thread to avoid blocking
    result = await asyncio.to_thread(run_sync)

    deps.emit_status("agent:done")
    return result.output, {"tokens": result.usage.output_tokens if result.usage else 0}
