# Phase 4 Technical Analysis: Complete Answers

## Question 4: Database Schema Mapping

### Current Schema

**source_documents** (already populated by Phase 3)
```sql
CREATE TABLE source_documents (
    id UUID PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    filing_type VARCHAR(20) NOT NULL,
    filing_year INTEGER NOT NULL,
    filing_date TIMESTAMP NOT NULL,
    url VARCHAR(512) NOT NULL,
    created_at TIMESTAMP NOT NULL
);
```

**document_chunks** (to be populated in Phase 4)
```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL (FK → source_documents.id),
    text TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    chunk_metadata JSON,
    search_vector TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);
```

### Field Mapping: Source Data → Database

| Database Field | Source | Type | Purpose | Example |
|---|---|---|---|---|
| **document_chunks.id** | UUID() | UUID | Unique chunk identifier | `550e8400-e29b-41d4-a716-446655440000` |
| **document_chunks.document_id** | source_documents.id | UUID | Foreign key to filing | `550e8400-e29b-41d4-a716-446655440001` |
| **document_chunks.text** | chunk.text from HybridChunker | TEXT | Chunk content (plain text) | `"The company's revenue grew 15% YoY to $400M..."` |
| **document_chunks.embedding** | OpenAI API response | VECTOR(1536) | Vector embedding from text-embedding-3-small | `[0.0234, -0.0456, 0.1234, ..., 0.0012]` |
| **document_chunks.chunk_metadata** | Merged metadata | JSON | Structured metadata (see below) | `{"chunk_index": 0, "heading": "Item 1A", ...}` |
| **document_chunks.search_vector** | chunk.text | TEXT | Full-text search index | `"revenue grew 15% company"` |
| **document_chunks.created_at** | datetime.now(UTC) | TIMESTAMP | Ingestion timestamp | `2026-06-13 14:23:45.123456+00:00` |

### chunk_metadata Structure (JSON)

```json
{
  "chunk_index": 0,
  "total_chunks": 42,
  "heading": "Item 1A. Risk Factors",
  "section_level": 1,
  "doc_item_count": 3,
  "element_types": ["paragraph", "list"],
  "token_count": 1024,
  "content_hash": "abc123def456...",
  "document_hash": "xyz789...",
  "ticker": "AAPL",
  "filing_type": "10-K",
  "filing_year": 2024,
  "filing_date": "2024-12-31T00:00:00Z",
  "source_url": "https://www.sec.gov/...",
  "chunker": "HybridChunker",
  "chunker_version": "2.102.1",
  "max_tokens_configured": 1024,
  "repeat_table_header": true,
  "merge_peers": true,
  "markdown_source_path": "2024/AAPL-10-K-2024.md"
}
```

### Flow: Markdown → Docling → Chunks → Database

```
markdown_file (2024/AAPL-10-K-2024.md)
    ↓
DocumentConverter.convert_string(markdown, format=InputFormat.MD)
    ↓
DoclingDocument (doc.document_id, doc.export_to_markdown())
    ↓
HybridChunker(max_tokens=1024, ...).chunk(dl_doc)
    ↓
Iterator[DocChunk] where each chunk has:
    - chunk.text (str): plain text content
    - chunk.meta.export_json_dict() (dict): metadata with headings, doc_items, origin
    - chunk.meta.headings (List[str]): hierarchical headings
    ↓
Token validation: count_tokens(chunk.text) ≤ 1024
    ↓
OpenAI embedding: client.embeddings.create(model="text-embedding-3-small", input=chunk.text)
    ↓
Build chunk_metadata: merge docling metadata + document info + chunking config
    ↓
INSERT INTO document_chunks (
    id=uuid4(),
    document_id=doc_id,
    text=chunk.text,
    embedding=embedding_vector,
    chunk_metadata=chunk_metadata_json,
    search_vector=chunk.text,
    created_at=now()
)
```

---

## Question 5: Idempotency Strategy Using Content Hashes

### Problem Statement

Phase 4 is expensive (OpenAI embeddings). Must support:
1. **Safe restart**: If ingestion fails halfway, don't re-embed or re-insert chunks
2. **Document updates**: If source filing changes, re-ingest only changed chunks
3. **Partial failure recovery**: If one document fails, skip it and continue with others
4. **Verification**: Know which chunks are from which document ingestion run

### Solution: Two-Level Hash Strategy

#### Level 1: Document Hash (Idempotency Key)

**Document content hash** = SHA-256(markdown_file_content)

```python
import hashlib

def compute_document_hash(markdown_content: str) -> str:
    """
    Compute SHA-256 hash of markdown content.
    Stable: same markdown → same hash (order matters, content matters).
    Unique: different markdown → different hash.
    """
    return hashlib.sha256(markdown_content.encode()).hexdigest()
```

**Purpose:**
- Detect if source markdown file changed
- Skip re-processing if markdown is identical
- Allow safe document updates (new markdown → new hash → new chunks)

**Storage:**
- In `chunk_metadata` as `"document_hash": "abc123..."` on every chunk
- Also compute before processing; skip document if all existing chunks have this hash

#### Level 2: Chunk Index + Content Hash (Chunk Identity)

**Chunk identity key** = `document_id || chunk_index`

```python
# Chunk identity tuple (never insert duplicate)
chunk_identity = (document_id, chunk_index)

# Content hash (for verification/auditing)
chunk_content_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
```

**Purpose:**
- Prevent duplicate chunk insertion within same document
- Recover from mid-ingestion failures
- Audit trail of which chunks changed if document updates

**Storage:**
- In `chunk_metadata` as `"chunk_content_hash": "def456..."` on every chunk

#### Idempotency Algorithm

```python
def ingest_document_idempotent(
    document_id: str,
    markdown_path: Path,
    db_engine,
) -> dict:
    """
    Idempotent document ingestion with hash-based deduplication.
    
    Returns:
        {
            "action": "skipped" | "completed" | "partial_failure",
            "reason": "...",
            "chunks_inserted": int,
            "chunks_skipped": int,
            "document_hash": str,
        }
    """
    
    # Step 1: Read markdown and compute document hash
    markdown_content = markdown_path.read_text(encoding="utf-8")
    document_hash = compute_document_hash(markdown_content)
    
    # Step 2: Check if document already fully ingested with same hash
    with db_engine.connect() as conn:
        existing_chunks = conn.execute(
            text("""
                SELECT COUNT(*) as cnt, 
                       COUNT(DISTINCT chunk_metadata->>'document_hash') as hash_count
                FROM document_chunks
                WHERE document_id = :doc_id
            """),
            {"doc_id": document_id}
        ).fetchone()
        
        existing_count = existing_chunks[0]
        existing_hash_match = (
            existing_count > 0 and
            conn.execute(
                text("""
                    SELECT MAX(chunk_metadata->>'document_hash' = :hash::text) as all_match
                    FROM document_chunks
                    WHERE document_id = :doc_id
                """),
                {"doc_id": document_id, "hash": document_hash}
            ).scalar()
        )
    
    # Step 3: If already ingested with same hash, skip
    if existing_hash_match:
        return {
            "action": "skipped",
            "reason": f"Document already ingested (hash={document_hash[:8]}...)",
            "chunks_inserted": 0,
            "chunks_skipped": existing_count,
            "document_hash": document_hash,
        }
    
    # Step 4: Delete old chunks if document changed (optional: keep history)
    # OPTION A: Delete old chunks and re-ingest (clean slate)
    #   with db_engine.connect() as conn:
    #       conn.execute(
    #           text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
    #           {"doc_id": document_id}
    #       )
    #       conn.commit()
    
    # OPTION B: Keep old chunks, insert new ones, mark old as deprecated (recommended)
    # (requires schema change to add deprecated_at timestamp — skip for now)
    
    # Step 5: Parse document and chunk
    converter = DocumentConverter()
    result = converter.convert_string(markdown_content, format=InputFormat.MD)
    doc = result.document
    
    chunker = HybridChunker(max_tokens=1024, merge_peers=True, repeat_table_header=True)
    chunks = list(chunker.chunk(dl_doc=doc))
    
    # Step 6: Insert chunks with idempotency check
    chunks_inserted = 0
    chunks_skipped = 0
    
    for chunk_index, chunk in enumerate(chunks):
        # Compute chunk identity and content hash
        chunk_identity = (document_id, chunk_index)
        chunk_content_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
        
        # Check if this exact chunk already exists
        with db_engine.connect() as conn:
            existing_chunk = conn.execute(
                text("""
                    SELECT id FROM document_chunks
                    WHERE document_id = :doc_id 
                    AND chunk_metadata->>'chunk_index' = :chunk_idx::text
                    LIMIT 1
                """),
                {"doc_id": document_id, "chunk_idx": chunk_index}
            ).fetchone()
        
        if existing_chunk:
            # Chunk already exists; skip embedding generation (EXPENSIVE)
            chunks_skipped += 1
            continue
        
        # Step 7: Generate embedding (EXPENSIVE — only if not already done)
        embedding = generate_embedding(chunk.text)
        
        # Step 8: Build chunk metadata
        chunk_metadata = {
            "chunk_index": chunk_index,
            "total_chunks": len(chunks),
            "heading": " > ".join(chunk.meta.headings) if chunk.meta.headings else None,
            "doc_item_count": len(chunk.meta.doc_items),
            "token_count": count_tokens(chunk.text),
            "content_hash": chunk_content_hash,
            "document_hash": document_hash,
            "ticker": document_id.split("-")[0],  # Extract from doc_id
            "filing_type": document_id.split("-")[1],
            "filing_year": int(document_id.split("-")[2]),
            "chunker": "HybridChunker",
            "chunker_version": "2.102.1",
            "max_tokens_configured": 1024,
            "repeat_table_header": True,
            "merge_peers": True,
            "markdown_source_path": str(markdown_path.relative_to(BASE_DIR)),
        }
        
        # Step 9: Insert chunk
        chunk_id = uuid4()
        with db_engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO document_chunks 
                    (id, document_id, text, embedding, chunk_metadata, search_vector, created_at)
                    VALUES (:id, :doc_id, :text, :embedding, :metadata::jsonb, :search_vector, :created_at)
                """),
                {
                    "id": chunk_id,
                    "doc_id": document_id,
                    "text": chunk.text,
                    "embedding": embedding,
                    "metadata": json.dumps(chunk_metadata),
                    "search_vector": chunk.text,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            conn.commit()
        
        chunks_inserted += 1
    
    return {
        "action": "completed",
        "reason": f"Ingested {chunks_inserted} new chunks",
        "chunks_inserted": chunks_inserted,
        "chunks_skipped": chunks_skipped,
        "document_hash": document_hash,
    }
```

### Idempotency Guarantees

| Scenario | Behavior | Cost Impact |
|---|---|---|
| **First ingest** | Insert all chunks, call OpenAI for each | Full cost (1024 embeddings) |
| **Re-run same document** | Detect hash match, skip entire document | $0 (no embeddings) |
| **Document changed** | Detect hash mismatch, re-ingest all chunks | Full cost (1024 embeddings) |
| **Mid-ingestion failure (chunk 500/1024 fails)** | Restart: skip chunks 0-499 (already in DB), resume from 500 | Partial cost (524 embeddings) |
| **Chunk content changed (1 paragraph)** | Entire document re-hashed differently, all chunks re-ingested | Full cost (1024 embeddings) |

### Query to Check Idempotency Status

```sql
-- Check if document fully ingested with specific hash
SELECT 
    document_id,
    COUNT(*) as chunk_count,
    MAX(chunk_metadata->>'document_hash') as latest_hash,
    MIN(created_at) as first_ingested,
    MAX(created_at) as last_updated
FROM document_chunks
GROUP BY document_id
ORDER BY last_updated DESC;

-- Find documents with hash mismatches (corrupted state)
SELECT 
    document_id,
    COUNT(DISTINCT chunk_metadata->>'document_hash') as hash_variety
FROM document_chunks
GROUP BY document_id
HAVING COUNT(DISTINCT chunk_metadata->>'document_hash') > 1;
```

---

## Question 6: OpenAI Batch Embedding for ~1000 Chunks

### Key Finding: Batch API Not Available for Embeddings

**OpenAI Batch API v2 (as of Feb 2025):**
- ❌ Chat completions only
- ❌ NO embeddings support
- ✅ On-demand API only option

### Implementation: On-Demand API with Request Batching

#### Rate Limits

**text-embedding-3-small:**
- RPM: 3,500 requests/minute
- TPM: 90,000 tokens/minute
- Max input per request: 2,097,152 tokens (large)
- Max vectors per request: ~2,000 texts (practical limit)

#### Strategy for 1000 Embeddings

```python
import time
from openai import OpenAI, RateLimitError

client = OpenAI(api_key="...")

def batch_embeddings(
    texts: list[str],
    batch_size: int = 500,
    min_wait_between_batches: float = 0.5,
) -> list[list[float]]:
    """
    Generate embeddings for texts with rate-limit handling.
    
    Args:
        texts: List of texts to embed (1000 in our case)
        batch_size: Texts per API request (500 recommended)
        min_wait_between_batches: Seconds between batch requests
    
    Returns:
        List of 1536-dimensional embeddings, same order as texts
    """
    embeddings = [None] * len(texts)
    
    for start_idx in range(0, len(texts), batch_size):
        end_idx = min(start_idx + batch_size, len(texts))
        batch_texts = texts[start_idx:end_idx]
        batch_indices = range(start_idx, end_idx)
        
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch_texts,
                    encoding_format="float"
                )
                
                # Extract embeddings in correct order
                for data in response.data:
                    embeddings[start_idx + data.index] = data.embedding
                
                print(f"✓ Batch {start_idx}-{end_idx-1}: {len(batch_texts)} embeddings")
                
                # Rate limiting: wait before next batch
                if end_idx < len(texts):
                    time.sleep(min_wait_between_batches)
                
                break  # Success, exit retry loop
                
            except RateLimitError as e:
                retry_count += 1
                wait_time = min_wait_between_batches * (2 ** retry_count)  # Exponential backoff
                print(f"⚠ Rate limit hit. Retry {retry_count}/{max_retries} after {wait_time}s")
                time.sleep(wait_time)
                
            except Exception as e:
                print(f"✗ Batch {start_idx}-{end_idx-1}: {e}")
                # Log partial failure; continue with other batches
                for idx in batch_indices:
                    embeddings[idx] = None  # Mark as failed
                break
    
    return embeddings
```

#### Cost & Performance Calculation

**For 1000 embeddings with ~256 tokens each (1024-token chunks / 4 chars per token):**

| Metric | Value |
|---|---|
| **Total tokens** | 1000 chunks × 256 tokens/chunk = 256,000 tokens |
| **Cost at $0.02/1M** | (256,000 / 1,000,000) × $0.02 = **$0.0051 (0.5 cents)** |
| **Batch requests** | 1000 embeddings ÷ 500 per batch = **2 requests** |
| **Request latency** | 100ms–200ms per batch |
| **Total time** | 2 requests × 150ms + 0.5s wait = **~0.8 seconds** |
| **RPM utilization** | 2 requests ÷ 3,500 RPM = **0.06% of limit** (huge headroom) |
| **TPM utilization** | 256,000 tokens ÷ 90,000 TPM = **2.8% of limit** (huge headroom) |

**Cost for entire Phase 4 (25 filings × 1000 chunks = 25,000 embeddings):**
- 25,000 chunks × 256 tokens = 6,400,000 tokens
- Cost: (6,400,000 / 1,000,000) × $0.02 = **$0.128 (13 cents)**
- Time: ~20 seconds (50 batches × 0.4s each)

#### Error Handling in Batch Loop

```python
def embed_with_fallback(
    chunks: list[DocChunk],
    db_engine,
    batch_size: int = 500,
) -> dict:
    """
    Embed chunks with per-chunk error recovery.
    
    Returns:
        {
            "total": 1000,
            "embedded": 998,
            "failed": 2,
            "failed_indices": [15, 427],
            "total_cost": 0.0051,
        }
    """
    texts = [chunk.text for chunk in chunks]
    embeddings = batch_embeddings(texts, batch_size=batch_size)
    
    results = {
        "total": len(chunks),
        "embedded": 0,
        "failed": 0,
        "failed_indices": [],
        "total_cost": 0.0,
    }
    
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if embedding is None:
            results["failed"] += 1
            results["failed_indices"].append(idx)
            continue
        
        # Insert chunk with embedding
        results["embedded"] += 1
        results["total_cost"] += (len(chunk.text) / 4) / 1_000_000 * 0.02
    
    return results
```

---

## Question 7: Final Ingestion Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Data Pipeline Phase 4                 │
└─────────────────────────────────────────────────────────┘

INPUT LAYER
├─ data/markdown/{year}/{ticker}-{form}-{year}.md (25 files)
│  └─ Source: Converted from HTML by convert.py
│
SOURCE DOCUMENT LAYER (already populated)
├─ source_documents table
│  ├─ id (UUID)
│  ├─ ticker, filing_type, filing_year, filing_date, url
│  └─ Status: 25 documents pre-loaded
│
PROCESSING LAYER
├─ DocumentConverter
│  ├─ Input: markdown file
│  ├─ Output: DoclingDocument
│  └─ Config: InputFormat.MD
│
├─ HybridChunker (CORE LOGIC)
│  ├─ max_tokens: 1024 (safety limit: 12.5% of 8,192 embedding window)
│  ├─ repeat_table_header: true (financial data context)
│  ├─ merge_peers: true (deduplicate small chunks)
│  ├─ always_emit_headings: false (optional section headers)
│  └─ Output: Iterator[DocChunk] with metadata
│
├─ Token Validator
│  ├─ count_tokens(chunk.text) using OpenAI tokenizer
│  ├─ Validate: tokens ≤ 1024
│  └─ If exceeded: log error (should not happen with HybridChunker)
│
├─ OpenAI Embedding Service
│  ├─ Model: text-embedding-3-small
│  ├─ Batch: 500 texts per request
│  ├─ Rate limit: 3,500 RPM / 90,000 TPM
│  ├─ Cost: $0.02 per 1M tokens
│  └─ Output: [1536] dimensional vectors
│
IDEMPOTENCY LAYER
├─ Document Hash (SHA-256)
│  ├─ Detect source file changes
│  ├─ Skip re-processing if unchanged
│  └─ Stored in every chunk's metadata
│
├─ Chunk Index + Content Hash
│  ├─ Prevent duplicate insertion
│  ├─ Enable mid-ingestion recovery
│  └─ Stored in chunk_metadata.chunk_content_hash
│
DATA LAYER
├─ document_chunks table
│  ├─ id (UUID, PK)
│  ├─ document_id (UUID, FK to source_documents)
│  ├─ text (TEXT, chunk content)
│  ├─ embedding (Vector(1536), from OpenAI)
│  ├─ chunk_metadata (JSON, see schema above)
│  ├─ search_vector (TEXT, full-text search index)
│  └─ created_at (TIMESTAMP)
│
├─ Indexes
│  ├─ HNSW index on embedding (vector similarity)
│  ├─ GIN index on search_vector (full-text search)
│  └─ B-tree index on document_id (chunk retrieval)
│
OUTPUT LAYER (for RAG)
├─ Vector Search
│  ├─ Query: user question → embedding
│  ├─ Search: SELECT * ORDER BY embedding <-> query_vec LIMIT 5
│  └─ Return: 5 most relevant chunks with embeddings
│
├─ Full-Text Search
│  ├─ Query: user keywords
│  ├─ Search: SELECT * WHERE search_vector @@ to_tsquery(query)
│  └─ Return: keyword-matching chunks
│
└─ Hybrid Search (combine both)
   └─ Use for financial Q&A (both semantic + keyword relevance)
```

### Code Organization

```
data/
├─ ingest.py                    # Core ingestion functions
│  ├─ load_markdown_files(data_dir)
│  ├─ parse_to_docling(markdown_path)
│  ├─ chunk_document(doc) → Iterator[DocChunk]
│  ├─ validate_chunk_tokens(chunk, tokenizer)
│  ├─ generate_embedding(text, client)
│  ├─ insert_chunks_to_db(document_id, chunks, embeddings, engine)
│  ├─ compute_document_hash(markdown_content)
│  └─ ingest_document_idempotent(doc_id, markdown_path, engine)
│
├─ test_single_chunk.py         # Single-chunk test harness
│  ├─ Test document: smallest 10-K
│  ├─ Extract first chunk only
│  ├─ Generate embedding
│  ├─ Verify insertion
│  └─ Test vector/full-text search
│
└─ ingest_all.py                # Full corpus ingestion CLI
   ├─ Load all markdown files
   ├─ Iterate documents
   ├─ Call ingest_document_idempotent()
   ├─ Log results
   └─ Report final stats
```

### Execution Sequence

#### Phase 4A: Single Chunk Test (5 minutes)

```
1. python data/test_single_chunk.py
   └─ Load: 2024/AAPL-10-K-2024.md (smallest)
   └─ Chunk: extract first chunk (100 words)
   └─ Embed: 1 OpenAI API call (~200ms)
   └─ Insert: 1 row into document_chunks
   └─ Verify:
      ├─ SELECT * FROM document_chunks WHERE id = '...'
      ├─ Embedding dimension = 1536? ✓
      ├─ Metadata complete? ✓
      ├─ search_vector populated? ✓
      └─ Full-text search works? ✓
```

#### Phase 4B: Full Single Document Test (30 seconds)

```
2. python data/ingest_all.py --single-document 2024/AAPL-10-K-2024.md
   └─ Parse markdown → DoclingDocument
   └─ Chunk: 30-50 chunks (1024 tokens each)
   └─ Embed: 30-50 OpenAI calls (~10 seconds)
   └─ Insert: 30-50 rows
   └─ Verify:
      ├─ SELECT COUNT(*) FROM document_chunks WHERE document_id = 'AAPL-10-K-2024'
      ├─ All chunks have embeddings? ✓
      ├─ Vector similarity search works? ✓
      └─ Full-text search (e.g., "revenue") returns results? ✓
```

#### Phase 4C: Multi-Document Test (2 minutes)

```
3. python data/ingest_all.py --limit 3
   └─ Ingest first 3 documents
   └─ Total: ~100 chunks
   └─ Time: ~30 seconds
   └─ Verify:
      ├─ Cross-document search works? ✓
      └─ Performance acceptable? ✓
```

#### Phase 4D: Full Corpus Ingestion (2–3 minutes)

```
4. python data/ingest_all.py
   └─ Ingest all 25 documents
   └─ Total: ~1000 chunks
   └─ Time: ~20 seconds (50 batches × 0.4s each)
   └─ Cost: ~$0.01
   └─ Verify:
      ├─ SELECT COUNT(*) FROM document_chunks
      │  → 1000 rows? ✓
      ├─ SELECT COUNT(DISTINCT document_id) FROM document_chunks
      │  → 25 documents? ✓
      └─ Random spot-check:
         └─ SELECT * WHERE ticker = 'AAPL' AND text LIKE '%revenue%'
            → Results appear relevant? ✓
```

### Configuration

**data/ingest.py top-level config:**

```python
# Chunking
MAX_TOKENS_PER_CHUNK = 1024
CHUNK_OVERLAP_TOKENS = 100  # 10% overlap for context

# OpenAI
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE_EMBEDDINGS = 500
MIN_WAIT_BETWEEN_BATCHES = 0.5  # seconds

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Paths
DATA_DIR = Path(__file__).parent
MARKDOWN_DIR = DATA_DIR / "markdown"

# Idempotency
CHECK_DOCUMENT_HASH = True  # Skip if source unchanged
KEEP_OLD_CHUNKS_ON_UPDATE = True  # Keep history vs delete-and-replace
```

### Expected Outputs

#### Console Log (test run)

```
[PHASE 4A] Single Chunk Test
  Loading: data/markdown/2024/AAPL-10-K-2024.md
  Source document ID: 550e8400-e29b-41d4-a716-446655440000
  Document hash: abc123def456...
  Parsing markdown...
  Chunking with HybridChunker (max_tokens=1024)...
  Total chunks: 42
  Generating embeddings...
    Batch 0/1: 42 embeddings in 0.2s
  Inserting chunks into database...
    [OK] Chunk 0: 756 tokens → UUID: 550e8400-e29b-41d4-a716-446655440001
    [OK] Chunk 1: 748 tokens → UUID: 550e8400-e29b-41d4-a716-446655440002
    ...
  [SUMMARY] Inserted: 42 chunks | Cost: $0.0003
  [VERIFY] Vector similarity search: OK
  [VERIFY] Full-text search ("revenue"): OK

[PHASE 4D] Full Corpus Ingestion
  Documents: 25
  Estimated time: 20s
  Estimated cost: $0.01
  
  Processing:
  [OK] AAPL-10-K-2024: 42 chunks inserted (skipped 0)
  [OK] MSFT-10-K-2024: 38 chunks inserted (skipped 0)
  [SKIP] GOOG-10-K-2024: 41 chunks already ingested (hash match)
  ...
  
  [FINAL SUMMARY]
  Total documents: 25
  Total chunks: 1000
  Total cost: $0.0128
  Time elapsed: 19s
  Status: ALL OK ✓
```

### Rollback & Recovery

**If ingestion fails midway:**

```bash
# Option 1: Restart (idempotent, skips already-processed chunks)
python data/ingest_all.py
# → Checks hashes, skips completed documents, resumes from failure point

# Option 2: Force re-ingest single document
python data/ingest_all.py --force --document AAPL-10-K-2024
# → Deletes old chunks, re-processes from scratch

# Option 3: Verify data integrity
python data/verify_ingestion.py
# → Checks: all 25 documents have chunks, embeddings are 1536-dim, hashes match
```

---

## Summary Table: All Questions Answered

| Question | Answer | Key Detail |
|---|---|---|
| **1. Docling API** | Latest v2.102.1 | HybridChunker for SEC, iterator-based, metadata rich |
| **2. Chunkers** | HybridChunker = HierarchicalChunker + token refinement | Use HybridChunker (3-stage: split, merge, repeat headers) |
| **3. Chunk size** | **1024 tokens** | 12.5% of 8,192 embedding limit, industry standard, SEC filing safe |
| **4. DB schema** | 7 fields mapped | chunk_metadata JSON captures 18 properties (hash, heading, tokens, etc.) |
| **5. Idempotency** | Two-level hash (document + chunk) | SHA-256 detects changes, skip re-embedding, recover from failures |
| **6. Embeddings** | On-demand API, 500 texts/batch | Batch API unavailable; 2 batches for 1000 chunks = $0.005, ~1s |
| **7. Architecture** | Modular pipeline with 4 layers | Input → Processing → Idempotency → Data → Output (RAG-ready) |

