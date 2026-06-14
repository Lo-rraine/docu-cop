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
"""Phase 4D: Full corpus ingestion for all markdown documents."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import ingest
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import create_engine

# Fix Windows console encoding using reconfigure instead of manual wrapping
sys.stdout.reconfigure(encoding="utf-8")

# Load .env
backend_env = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(backend_env)

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Phase 4D: Ingest all markdown documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N documents (default: all)",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip hash-based idempotency check",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested (no DB writes)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print chunk details",
    )
    return parser.parse_args()


def print_header(title: str) -> None:
    """Print section header."""
    print(f"\n[{title}]")


def print_ok(msg: str) -> None:
    """Print success message."""
    print(f"  ✓ {msg}")


def print_err(msg: str) -> None:
    """Print error message."""
    print(f"  ✗ {msg}")


def print_info(msg: str) -> None:
    """Print info message."""
    print(f"  {msg}")


def ingest_document(
    document_id: str,
    markdown_path: Path,
    doc_metadata: dict,
    db_engine,
    openai_client: OpenAI,
    skip_check: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Ingest a single document.

    Args:
        document_id: source_documents.id UUID
        markdown_path: Path to markdown file
        doc_metadata: Parsed document metadata from manifest
        db_engine: Database engine
        openai_client: OpenAI client
        skip_check: Skip idempotency check
        dry_run: Don't write to database
        verbose: Print detailed output

    Returns:
        {
            "action": "skipped" | "ingested" | "failed",
            "reason": str,
            "chunks_inserted": int,
            "chunks_skipped": int,
            "chunks_failed": int,
            "total_chunks": int,
            "total_tokens": int,
            "cost": float,
        }
    """
    result = {
        "action": "failed",
        "reason": "",
        "chunks_inserted": 0,
        "chunks_skipped": 0,
        "chunks_failed": 0,
        "total_chunks": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }

    try:
        # 1. Load markdown
        markdown_content = ingest.load_and_parse_markdown(markdown_path)
        document_hash = ingest.compute_document_hash(markdown_content)

        # 2. Check idempotency
        if not skip_check and not dry_run:
            if ingest.check_document_exists(document_id, document_hash, db_engine):
                result["action"] = "skipped"
                result["reason"] = f"Already ingested (hash={document_hash[:8]}...)"
                return result

        # 3. Chunk markdown directly (financial-document-aware)
        chunks = ingest.chunk_financial_markdown(markdown_content, max_tokens=ingest.MAX_TOKENS_PER_CHUNK)
        result["total_chunks"] = len(chunks)

        if len(chunks) == 0:
            result["action"] = "failed"
            result["reason"] = "No chunks produced"
            return result

        # 6. Count total tokens
        total_tokens = sum(ingest.count_tokens(chunk.text) for chunk in chunks)
        result["total_tokens"] = total_tokens

        # 7. Calculate cost (OpenAI charges per 1M input tokens)
        # Average 4 chars per token; text-embedding-3-small = $0.02 per 1M tokens
        cost = (total_tokens / 1_000_000) * 0.02
        result["cost"] = cost

        if verbose:
            print_info(f"Total tokens: {total_tokens}")
            print_info(f"Estimated cost: ${cost:.6f}")

        # 8. Generate embeddings
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = ingest.batch_generate_embeddings(chunk_texts, openai_client)

        # 9. Insert to database (or skip for dry-run)
        if dry_run:
            result["action"] = "skipped"
            result["reason"] = "Dry-run mode (no DB writes)"
            result["chunks_inserted"] = len([e for e in embeddings if e is not None])
        else:
            insert_result = ingest.insert_chunks_to_db(
                db_engine,
                document_id,
                doc_metadata,
                chunks,
                embeddings,
                document_hash,
            )
            result["chunks_inserted"] = insert_result["inserted"]
            result["chunks_skipped"] = insert_result["skipped"]
            result["chunks_failed"] = insert_result["failed"]

            if insert_result["inserted"] == 0 and insert_result["failed"] == 0:
                result["action"] = "skipped"
                result["reason"] = "All chunks already existed"
            elif insert_result["failed"] > 0:
                result["action"] = "partial"
                result["reason"] = f"{insert_result['failed']} chunks failed to insert"
            else:
                result["action"] = "ingested"
                result["reason"] = f"{insert_result['inserted']} chunks inserted"

    except Exception as e:
        result["action"] = "failed"
        result["reason"] = str(e)
        if verbose:
            import traceback
            traceback.print_exc()

    return result


def format_result(doc_id: str, doc_metadata: dict, result: dict) -> str:
    """Format document result for display."""
    ticker = doc_metadata.get("ticker", "?")
    year = doc_metadata.get("filing_year", "?")
    action = result["action"]

    if action == "ingested":
        return (
            f"[OK] {ticker}-{year}: {result['chunks_inserted']} chunks, "
            f"{result['total_tokens']}K tokens, ${result['cost']:.4f}"
        )
    elif action == "skipped":
        return f"[SKIP] {ticker}-{year}: {result['reason']}"
    elif action == "partial":
        return (
            f"[PARTIAL] {ticker}-{year}: {result['chunks_inserted']} inserted, "
            f"{result['chunks_failed']} failed"
        )
    else:
        return f"[FAIL] {ticker}-{year}: {result['reason']}"


def main():
    """Run full corpus ingestion."""
    args = parse_args()

    print("=" * 80)
    print("Phase 4D: Full Corpus Ingestion")
    print("=" * 80)
    print()

    # ========================================================================
    # SETUP
    # ========================================================================
    if not DATABASE_URL:
        print_err("DATABASE_URL not set in .env")
        return 1

    if not OPENAI_API_KEY:
        print_err("OPENAI_API_KEY not set in .env")
        return 1

    try:
        db_engine = create_engine(DATABASE_URL, echo=False)
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print_err(f"Setup failed: {e}")
        return 1

    # ========================================================================
    # LOAD MANIFEST & FILES
    # ========================================================================
    try:
        manifest = ingest.load_manifest()
        markdown_files = ingest.load_markdown_files()
    except Exception as e:
        print_err(f"Failed to load manifest or markdown files: {e}")
        return 1

    if args.limit:
        markdown_files = markdown_files[: args.limit]

    print(f"Documents to ingest: {len(markdown_files)}")
    print(f"Dry-run mode: {args.dry_run}")
    print(f"Skip idempotency check: {args.skip_check}")
    print()

    # ========================================================================
    # INGEST LOOP
    # ========================================================================
    start_time = time.time()
    results_by_action = {"ingested": [], "skipped": [], "partial": [], "failed": []}
    total_cost = 0.0

    for i, (filename, markdown_path) in enumerate(markdown_files, 1):
        try:
            doc_metadata = ingest.parse_document_metadata(filename, manifest)
            # Look up source_documents.id UUID by source_url
            document_id = ingest.get_source_document_id(doc_metadata["source_url"], db_engine)
        except Exception as e:
            print_err(f"{filename}: {e}")
            results_by_action["failed"].append((filename, {"reason": str(e)}))
            continue

        result = ingest_document(
            document_id,
            markdown_path,
            doc_metadata,
            db_engine,
            openai_client,
            skip_check=args.skip_check,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        # Track result
        action = result["action"]
        if action not in results_by_action:
            action = "failed"
        results_by_action[action].append((filename, result))
        total_cost += result["cost"]

        # Print formatted result
        print(format_result(filename, doc_metadata, result))

        # Rate limiting between documents
        if i < len(markdown_files):
            time.sleep(0.1)

    elapsed_time = time.time() - start_time

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_chunks = sum(
        result.get("chunks_inserted", 0)
        for _, result in results_by_action["ingested"] + results_by_action["partial"]
    )
    total_tokens = sum(
        result.get("total_tokens", 0)
        for _, result in results_by_action["ingested"] + results_by_action["partial"]
    )

    print()
    print(f"Documents processed: {len(markdown_files)}")
    print(f"  Ingested: {len(results_by_action['ingested'])}")
    print(f"  Skipped: {len(results_by_action['skipped'])}")
    print(f"  Partial: {len(results_by_action['partial'])}")
    print(f"  Failed: {len(results_by_action['failed'])}")
    print()
    print(f"Total chunks inserted: {total_chunks}")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Time elapsed: {elapsed_time:.1f}s")
    print()

    if results_by_action["failed"]:
        print("Failed documents:")
        for filename, result in results_by_action["failed"]:
            print(f"  - {filename}: {result['reason']}")
        print()

    print("=" * 80)

    if results_by_action["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
