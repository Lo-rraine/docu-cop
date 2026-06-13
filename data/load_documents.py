# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "python-dotenv",
#     "sqlalchemy",
#     "psycopg2-binary",
# ]
# ///
"""One-off script to load converted markdown documents into the database."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load .env from backend directory
backend_env = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(backend_env)

MARKDOWN_DIR = Path(__file__).resolve().parent / "markdown"
CONVERSION_MANIFEST = MARKDOWN_DIR / "conversion_manifest.json"


def get_db_engine():
    """Create a database engine from environment variables."""
    import os

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")

    return create_engine(db_url, echo=False)


def load_manifest() -> dict:
    """Load the conversion manifest to get filing metadata."""
    if not CONVERSION_MANIFEST.exists():
        raise FileNotFoundError(f"Manifest not found: {CONVERSION_MANIFEST}")
    return json.loads(CONVERSION_MANIFEST.read_text(encoding="utf-8"))


def extract_ticker_and_info(filepath: Path, manifest_data: list) -> tuple[str, str, int, datetime]:
    """Extract ticker and filing info from filepath and manifest."""
    relative_path = filepath.relative_to(MARKDOWN_DIR)
    year_str = relative_path.parts[0]
    filename = filepath.stem

    for filing in manifest_data:
        filing_path = filing["local_path"].replace("\\", "/")
        if filename in filing_path and year_str in filing_path:
            return (
                filing["ticker"].upper(),
                filing["form"],
                int(year_str),
                datetime.fromisoformat(filing["filing_date"].replace("Z", "+00:00")),
            )

    raise ValueError(f"Could not find manifest entry for {relative_path}")


def insert_document(engine, ticker: str, filing_type: str, filing_year: int, filing_date: datetime, url: str) -> str:
    """Insert a source document and return its ID."""
    doc_id = str(uuid4())

    query = text("""
        INSERT INTO source_documents (id, ticker, filing_type, filing_year, filing_date, url, created_at)
        VALUES (:id, :ticker, :filing_type, :filing_year, :filing_date, :url, :created_at)
    """)

    with engine.connect() as conn:
        conn.execute(
            query,
            {
                "id": doc_id,
                "ticker": ticker,
                "filing_type": filing_type,
                "filing_year": filing_year,
                "filing_date": filing_date,
                "url": url,
                "created_at": datetime.now(timezone.utc),
            },
        )
        conn.commit()

    return doc_id


def load_documents_to_db() -> dict:
    """Load all markdown documents into the database."""
    manifest = load_manifest()
    original_manifest = manifest["original_manifest"]
    filing_data = {f["local_path"].split("\\")[1]: f for f in original_manifest["filings"]}

    engine = get_db_engine()

    markdown_files = sorted(MARKDOWN_DIR.glob("*/*.md"))
    loaded_count = 0
    failed_count = 0
    loaded_docs = []

    print(f"Found {len(markdown_files)} markdown files to load...")

    for md_file in markdown_files:
        try:
            year = md_file.parent.name
            filename = md_file.stem

            filing_key = f"{filename}.htm"
            if filing_key not in filing_data:
                print(f"  SKIP: {md_file.relative_to(MARKDOWN_DIR)} - no manifest entry")
                continue

            filing = filing_data[filing_key]
            ticker = filing["ticker"].upper()
            filing_type = filing["form"]
            filing_year = int(year)
            filing_date = datetime.fromisoformat(filing["filing_date"])
            url = filing["source_url"]

            doc_id = insert_document(engine, ticker, filing_type, filing_year, filing_date, url)
            loaded_docs.append({
                "id": doc_id,
                "ticker": ticker,
                "filing_type": filing_type,
                "filing_year": filing_year,
                "path": str(md_file.relative_to(MARKDOWN_DIR)),
            })
            loaded_count += 1
            print(f"  [OK] {ticker} {filing_type} {filing_year} -> {doc_id}")
        except Exception as e:
            failed_count += 1
            print(f"  [FAIL] {md_file.relative_to(MARKDOWN_DIR)} - {e}")

    print(f"\nLoaded {loaded_count} documents into source_documents table")
    if failed_count:
        print(f"Failed: {failed_count}")

    return {
        "loaded_count": loaded_count,
        "failed_count": failed_count,
        "documents": loaded_docs,
    }


if __name__ == "__main__":
    result = load_documents_to_db()
    print(f"\nResult: {result['loaded_count']} loaded, {result['failed_count']} failed")
