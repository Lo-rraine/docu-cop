# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "docling==2.26.0",
#     "openai==2.40.0",
#     "pgvector==0.4.2",
#     "psycopg2-binary==2.9.12",
#     "sqlalchemy==2.0.50",
#     "tiktoken==0.8.0",
# ]
# ///
"""Phase 4: Ingestion pipeline for chunking, embedding, and storing document chunks."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

import tiktoken
from docling.chunking import HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from docling_core.types import DoclingDocument
from docling_core.transforms.chunker import DocChunk
from openai import OpenAI, RateLimitError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Fix Windows console encoding using reconfigure instead of manual wrapping
sys.stdout.reconfigure(encoding="utf-8")

# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_TOKENS_PER_CHUNK = 1000
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE_EMBEDDINGS = 5
MIN_WAIT_BETWEEN_BATCHES = 0.5

DATA_DIR = Path(__file__).resolve().parent
MARKDOWN_DIR = DATA_DIR / "markdown"
CONVERSION_MANIFEST = MARKDOWN_DIR / "conversion_manifest.json"

# Load configuration from environment
from dotenv import load_dotenv

backend_env = DATA_DIR.parent / "backend" / ".env"
load_dotenv(backend_env)

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# ============================================================================
# PHASE 1: FOUNDATION
# ============================================================================

# 1. Tokenizer setup
_tokenizer_cache = None


def get_tokenizer():
    """Get or initialize tokenizer (cl100k_base for OpenAI)."""
    global _tokenizer_cache
    if _tokenizer_cache is None:
        _tokenizer_cache = tiktoken.get_encoding("cl100k_base")
    return _tokenizer_cache


def count_tokens(text: str) -> int:
    """Count tokens in text using OpenAI tokenizer."""
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))


# 2. Markdown I/O
def load_and_parse_markdown(markdown_path: Path) -> str:
    """Load and parse markdown file."""
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")
    return markdown_path.read_text(encoding="utf-8")


def load_markdown_files(base_dir: Path = MARKDOWN_DIR) -> list[tuple[str, Path]]:
    """
    Load markdown files from directory.

    Returns:
        List of (document_id, markdown_path) tuples
    """
    files = []
    for md_file in sorted(base_dir.glob("*/*.md")):
        # Extract from filename: e.g., "aapl_10-k_2024-11-01_0000320193-24-000123.md"
        doc_id = md_file.stem
        files.append((doc_id, md_file))
    return files


# 3. Docling integration
def markdown_to_docling(markdown_content: str, doc_name: str = "document") -> DoclingDocument:
    """Convert markdown string to DoclingDocument."""
    import tempfile

    # Write markdown to temp file, as convert() expects a file path
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(markdown_content)
        temp_path = f.name

    try:
        converter = DocumentConverter()
        result = converter.convert(temp_path)
        if result.document is None:
            raise ValueError(f"Failed to convert {doc_name} to DoclingDocument")
        return result.document
    finally:
        import os
        os.unlink(temp_path)


# 4. Hashing utilities
def compute_document_hash(content: str) -> str:
    """Compute SHA-256 hash of document content."""
    return hashlib.sha256(content.encode()).hexdigest()


def compute_chunk_hash(text: str) -> str:
    """Compute SHA-256 hash of chunk text."""
    return hashlib.sha256(text.encode()).hexdigest()


# 5. Chunking service
def chunk_document(doc: DoclingDocument, max_tokens: int = MAX_TOKENS_PER_CHUNK) -> list[DocChunk]:
    """Chunk document using HybridChunker."""
    chunker = HybridChunker(
        max_tokens=max_tokens,
        repeat_table_header=True,
        merge_peers=True,
        always_emit_headings=False,
    )
    chunks = list(chunker.chunk(dl_doc=doc))
    return chunks


# 6. Manifest parsing
def load_manifest() -> dict:
    """Load conversion manifest with document metadata."""
    if not CONVERSION_MANIFEST.exists():
        raise FileNotFoundError(f"Manifest not found: {CONVERSION_MANIFEST}")
    return json.loads(CONVERSION_MANIFEST.read_text(encoding="utf-8"))


def parse_document_metadata(filename: str, manifest: dict) -> dict:
    """
    Extract document metadata from filename using manifest.

    Args:
        filename: Document filename (e.g., "aapl_10-k_2024-11-01_0000320193-24-000123")
        manifest: Manifest dict from load_manifest()

    Returns:
        {ticker, filing_type, filing_year, filing_date, url, ...}
    """
    original_manifest = manifest.get("original_manifest", {})
    filings = original_manifest.get("filings", [])

    for filing in filings:
        local_path = filing.get("local_path", "").replace("\\", "/")
        # Extract the filename part without extension
        if filename in local_path:
            return {
                "ticker": filing["ticker"].upper(),
                "filing_type": filing["form"],
                "filing_year": int(local_path.split("/")[0]),
                "filing_date": datetime.fromisoformat(
                    filing["filing_date"].replace("Z", "+00:00")
                ),
                "source_url": filing["source_url"],
                "accession_number": filing.get("accession_number"),
            }

    raise ValueError(f"Could not find manifest entry for {filename}")


def get_source_document_id(source_url: str, db_engine) -> str:
    """
    Look up source_documents.id UUID by source_url.

    Uses ORDER BY created_at ASC LIMIT 1 to handle duplicate entries
    (takes the earliest one).

    Args:
        source_url: URL of the source document
        db_engine: SQLAlchemy engine

    Returns:
        source_documents.id as UUID string

    Raises:
        ValueError: If document not found in source_documents
    """
    with db_engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT id FROM source_documents
                WHERE url = :url
                ORDER BY created_at ASC
                LIMIT 1
            """),
            {"url": source_url},
        ).fetchone()

        if result is None:
            raise ValueError(f"Source document not found for URL: {source_url}")

        return str(result[0])


# ============================================================================
# PHASE 2: EXTERNAL SERVICES
# ============================================================================

# 7. OpenAI embedding (single)
def generate_embedding(text: str, client: OpenAI) -> list[float]:
    """Generate embedding for text using OpenAI API."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        encoding_format="float",
    )
    embedding = response.data[0].embedding
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(embedding)}"
        )
    return embedding


# 8. OpenAI embedding (batch)
def batch_generate_embeddings(
    texts: list[str],
    client: OpenAI,
    batch_size: int = BATCH_SIZE_EMBEDDINGS,
    min_wait: float = MIN_WAIT_BETWEEN_BATCHES,
) -> list[list[float]]:
    """
    Generate embeddings for texts in batches.

    Args:
        texts: List of texts to embed
        client: OpenAI client
        batch_size: Texts per API request
        min_wait: Seconds to wait between batches

    Returns:
        List of embeddings, same order as input texts
    """
    import time

    embeddings = [None] * len(texts)

    for start_idx in range(0, len(texts), batch_size):
        end_idx = min(start_idx + batch_size, len(texts))
        batch_texts = texts[start_idx:end_idx]

        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                response = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch_texts,
                    encoding_format="float",
                )

                # Extract embeddings in correct order
                for data in response.data:
                    embeddings[start_idx + data.index] = data.embedding

                # Rate limiting
                if end_idx < len(texts):
                    time.sleep(min_wait)

                break  # Success

            except RateLimitError:
                retry_count += 1
                wait_time = min_wait * (2**retry_count)
                if retry_count < max_retries:
                    time.sleep(wait_time)
                else:
                    raise

            except Exception as e:
                print(f"✗ Batch {start_idx}-{end_idx-1}: {e}")
                for idx in range(start_idx, end_idx):
                    embeddings[idx] = None
                break

    return embeddings


# 9. Database session management (done in next phase)

# 10. Idempotency check
def check_document_exists(
    doc_id: str,
    document_hash: str,
    db_engine,
) -> bool:
    """
    Check if document already fully ingested with same hash.

    Returns:
        True if document exists with matching hash (skip re-processing)
    """
    with db_engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT COUNT(*) as cnt,
                       COUNT(DISTINCT (chunk_metadata->>'document_hash')) as hash_count
                FROM document_chunks
                WHERE document_id = :doc_id
            """),
            {"doc_id": doc_id},
        ).fetchone()

        if result is None or result[0] == 0:
            return False

        # All chunks have same hash?
        hash_match = conn.execute(
            text("""
                SELECT COUNT(*) as cnt
                FROM document_chunks
                WHERE document_id = :doc_id
                AND chunk_metadata->>'document_hash' = :hash
            """),
            {"doc_id": doc_id, "hash": document_hash},
        ).scalar()

        return hash_match == result[0]


# ============================================================================
# PHASE 3: DATABASE WRITE
# ============================================================================

# 11. Chunk metadata builder (inline in insert_chunks_to_db)

# 12. Insert logic
def insert_chunks_to_db(
    db_engine,
    document_id: str,
    document_metadata: dict,
    chunks: list[DocChunk],
    embeddings: list[list[float]],
    document_hash: str,
) -> dict:
    """
    Insert chunks with embeddings into database.

    Args:
        db_engine: SQLAlchemy engine
        document_id: UUID string of source_document
        document_metadata: {ticker, filing_type, filing_year, filing_date, source_url}
        chunks: List of DocChunk objects
        embeddings: List of embedding vectors (same order as chunks)
        document_hash: SHA-256 of document content

    Returns:
        {inserted: int, skipped: int, failed: int}
    """
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    results = {
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
    }

    try:
        chunks_to_insert = []

        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Check if chunk already exists (idempotency)
            existing = session.execute(
                text("""
                    SELECT id FROM document_chunks
                    WHERE document_id = :doc_id
                    AND chunk_metadata->>'chunk_index' = CAST(:idx AS TEXT)
                    LIMIT 1
                """),
                {"doc_id": document_id, "idx": str(chunk_index)},
            ).fetchone()

            if existing:
                results["skipped"] += 1
                continue

            if embedding is None:
                results["failed"] += 1
                continue

            # Build chunk metadata
            headings = chunk.meta.headings if hasattr(chunk, "meta") else []
            chunk_metadata = {
                "chunk_index": chunk_index,
                "total_chunks": len(chunks),
                "heading": " > ".join(headings) if headings else None,
                "doc_item_count": len(chunk.meta.doc_items) if hasattr(chunk, "meta") else 0,
                "token_count": count_tokens(chunk.text),
                "document_hash": document_hash,
                "chunk_hash": compute_chunk_hash(chunk.text),
                "ticker": document_metadata.get("ticker"),
                "filing_type": document_metadata.get("filing_type"),
                "filing_year": document_metadata.get("filing_year"),
                "filing_date": document_metadata.get("filing_date").isoformat()
                if document_metadata.get("filing_date")
                else None,
                "source_url": document_metadata.get("source_url"),
                "chunker": "HybridChunker",
                "chunker_version": "2.26.0",
                "max_tokens_configured": MAX_TOKENS_PER_CHUNK,
                "repeat_table_header": True,
                "merge_peers": True,
            }

            # Build insert values
            insert_values = {
                "id": str(uuid4()),
                "document_id": document_id,
                "text": chunk.text,
                "embedding": embedding,
                "chunk_metadata": json.dumps(chunk_metadata),
                "search_vector": chunk.text,
                "created_at": datetime.now(timezone.utc),
            }

            chunks_to_insert.append(insert_values)

            # Commit in batches of 50
            if len(chunks_to_insert) >= 50:
                _insert_batch(session, chunks_to_insert)
                results["inserted"] += len(chunks_to_insert)
                chunks_to_insert = []

        # Insert remaining
        if chunks_to_insert:
            _insert_batch(session, chunks_to_insert)
            results["inserted"] += len(chunks_to_insert)

        session.commit()

    except Exception as e:
        session.rollback()
        print(f"✗ Database insert failed: {e}")
        results["failed"] = len(chunks)
        results["inserted"] = 0

    finally:
        session.close()

    return results


def _insert_batch(session: Session, insert_values_list: list[dict]) -> None:
    """Insert batch of chunks using raw SQL."""
    for values in insert_values_list:
        session.execute(
            text("""
                INSERT INTO document_chunks
                (id, document_id, text, embedding, chunk_metadata, search_vector, created_at)
                VALUES (:id, :document_id, :text, CAST(:embedding AS vector),
                        CAST(:chunk_metadata AS jsonb), :search_vector, :created_at)
            """),
            values,
        )


# 13. Validation helper
def validate_embedding(embedding: list[float]) -> bool:
    """Validate embedding vector."""
    if not isinstance(embedding, list):
        return False
    if len(embedding) != EMBEDDING_DIMENSIONS:
        return False
    if not all(isinstance(x, (int, float)) for x in embedding):
        return False
    return True
