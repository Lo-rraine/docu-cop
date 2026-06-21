# Document Copilot: Complete System Architecture Walkthrough

**Author's Note:** This is a reverse-engineered architecture document from the codebase as of 2026-06-14. It traces the complete lifecycle from user authentication through document retrieval, LLM reasoning, citation validation, and persistence.

---

## 1. Document Lifecycle: From Upload to Answer

### 1.1 Phase 1: Document Ingestion (Implicit)

Documents are **pre-loaded** into the database. The system assumes SEC filings (10-K, 10-Q, 8-K) are already chunked, embedded, and stored. No upload endpoint exists in the current codebase—documents are populated externally (likely via a separate data pipeline).

**Inputs:**
- Raw SEC filing text (external)
- Metadata: ticker, filing_type (10-K/10-Q/8-K), filing_year, filing_date, URL

**Outputs:**
- Chunks stored in `document_chunks` table with embeddings, metadata, and full-text indexes

---

### 1.2 Phase 2: User Authentication & Session

**User Action:** User navigates to frontend and logs in.

#### Files Involved:
- **Frontend:** `frontend/src/pages/SignIn.tsx` → form submission
- **Backend:** `backend/app/main.py:64-118` → `POST /auth/register` and `POST /auth/login`
- **Auth module:** `backend/app/auth/password.py` → hash and verify
- **Models:** `backend/app/database/models/users.py` → `User` table

#### Classes & Functions:
```
User (SQLAlchemy model)
  ├─ id: UUID (primary key)
  ├─ email: String (unique, indexed)
  ├─ password_hash: String
  └─ created_at: DateTime

register(request: RegisterRequest, db: Session)
  ├─ Check email uniqueness
  ├─ Hash password via hash_password()
  ├─ Create User + commit
  └─ Generate JWT + set HttpOnly cookie "access_token"

login(request: LoginRequest, db: Session)
  ├─ Look up User by email
  ├─ Verify password via verify_password()
  ├─ Generate JWT + set HttpOnly cookie "access_token"
  └─ Return { success: True, email }
```

#### Database Tables Touched:
- `users` (insert/select)

#### Inputs/Outputs:
**Input:** `{ email: string, password: string }`
**Output:** JWT token set as HttpOnly cookie; client can now make authenticated requests

---

### 1.3 Phase 3: User Creates Chat Thread

**User Action:** Clicks "New Chat" in frontend.

#### Files Involved:
- **Frontend:** `frontend/src/components/Sidebar.tsx` → create thread button
- **Backend:** `backend/app/api/chat.py:129-139` → `POST /chat/threads`
- **Models:** `backend/app/database/models/chat.py` → `ChatThread` model

#### Classes & Functions:
```
ChatThread (SQLAlchemy model)
  ├─ id: UUID (primary key)
  ├─ user_id: UUID (FK → users.id, indexed)
  ├─ title: String (nullable, auto-set after first response)
  ├─ created_at: DateTime
  ├─ updated_at: DateTime
  └─ messages: relationship(ChatMessage)

create_thread(request: CreateThreadRequest, user: User, db: Session)
  ├─ Create ChatThread(user_id=user.id, title=request.title)
  ├─ db.add() + db.commit()
  └─ Return thread as ThreadOut
```

#### Database Tables Touched:
- `chat_threads` (insert)

#### Inputs/Outputs:
**Input:** `{ title?: string }`
**Output:** `{ id: UUID, title?: string, created_at, updated_at }`

---

### 1.4 Phase 4: User Sends Message & Streaming Begins

**User Action:** Types question, hits send.

#### Files Involved:
- **Frontend:**
  - `frontend/src/pages/Chat.tsx:71-150` → handleSendMessage()
  - `frontend/src/lib/chat.ts:26-97` → streamChat() generator
  - `frontend/src/components/chat/MessageList.tsx` → renders streamed tokens

- **Backend:**
  - `backend/app/api/chat.py:229-280` → `POST /chat/stream`
  - `backend/app/chat/orchestrator.py:48-177` → run_turn() async generator
  - `backend/app/chat/streaming.py` → SSE event formatters

#### HTTP Flow:
```
Frontend POST /chat/stream
├─ body: { id: thread_id, messages: [{ role, content }, ...] }
├─ credentials: 'include' (sends HttpOnly cookie)
└─ returns: EventStream (text/event-stream)

Backend receives request
├─ Extract token from request.cookies.get("access_token")
├─ Decode JWT via jwt.decode()
├─ Look up or auto-create User by email
├─ Fetch ChatThread by ID, verify ownership
├─ Extract last user message from messages array
├─ Save user message to chat_messages table
└─ Start async token_generator() loop
```

#### Classes & Functions:
```
ChatMessage (SQLAlchemy model)
  ├─ id: UUID
  ├─ thread_id: UUID (FK → chat_threads.id)
  ├─ role: String ('user' | 'assistant')
  ├─ content: Text
  ├─ created_at: DateTime
  └─ citations: relationship(MessageCitation)

get_current_user_from_cookies(request: Request, db: Session) → User
  ├─ Extract "access_token" from cookies
  ├─ Decode JWT, extract email
  ├─ Look up User by email
  └─ Auto-create if not exists (edge case)

stream_chat(http_request: Request, request: ChatRequest, db: Session)
  ├─ get_current_user_from_cookies()
  ├─ Save user message to db
  ├─ Create token_generator() → async iterator
  └─ Return StreamingResponse(token_generator(), media_type="text/event-stream")
```

#### Database Tables Touched:
- `users` (select or insert)
- `chat_messages` (insert)
- `chat_threads` (select)

#### Inputs/Outputs:
**Input:** `{ id: UUID, messages: [{ role, content }] }`
**Output:** SSE stream with AI SDK format
```
0:"token "
0:"string "
d:{"type":"status","message":"..."}
d:{"type":"citation","data":{...}}
e:"error message"
```

---

## 2. Request Journey: "What was Nvidia revenue in FY2025?"

### Step 1: Endpoint Called
**Endpoint:** `POST /chat/stream`
**Files:** `backend/app/api/chat.py:229-280`

Request body:
```json
{
  "id": "<thread-id>",
  "messages": [
    { "role": "user", "content": "What was Nvidia revenue in FY2025?" }
  ]
}
```

Response: HTTP 200, `Content-Type: text/event-stream`

---

### Step 2: Service Called — run_turn()
**Files:** `backend/app/chat/orchestrator.py:48-177`

Orchestrator initializes:
1. **Token logging:** Count tokens in user query (input)
2. **Create TurnRegistry:** Citation allowlist for validation
3. **Create DocumentAgentDeps:** Bundle of retriever, db, thread_id, user_id
4. **Create GroundingValidator:** For multi-stage citation validation

```python
async def run_turn(
    user_message: str,           # "What was Nvidia revenue in FY2025?"
    thread: ChatThread,
    user: User,
    db: Session,
    retriever: DocumentRetriever,
    openai_client: OpenAI,
) -> AsyncGenerator[str, None]:
    # Validation retry loop: up to MAX_RETRIES=2
    for attempt in range(MAX_RETRIES + 1):
        grounded, metadata = await run_document_agent(...)
        validation = validator.validate(grounded, registry)
        if validation.ok: break
```

---

### Step 3: Agent Executes — Tool Calls

**Files:**
- `backend/app/assistant/agent.py` → PydanticAI Agent with tools
- `backend/app/assistant/instructions.md` → System prompt

**Agent Definition:**
```python
agent = Agent(
    model_name='openai:gpt-4o',
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    instructions=<load from instructions.md>,
)

@agent.tool
def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    ticker: Optional[str] = None,
    filing_type: Optional[str] = None,
    year: Optional[int] = None,
    top_k: int = 3,
) -> str:
    """Hybrid search: semantic + full-text + RRF."""
    passages = ctx.deps.retriever.retrieve(query, ctx.deps.db, top_k=top_k)
    # Filter by optional constraints
    ctx.deps.registry.register_many(passages)  # Citation allowlist
    return formatted_passages
```

**Agent invokes:** `await run_document_agent(user_message, deps)` → yields `(grounded, metadata)`

**Agent's reasoning (per instructions.md):**
1. Parse user query: "Nvidia revenue FY2025"
2. Identify entities: ticker="NVDA", metric="revenue", period="FY2025"
3. Call `search_filings(query="revenue 2025", ticker="NVDA")` → retrieves relevant passages
4. Call `read_chunk()` or `read_surrounding_chunks()` for context
5. Assemble answer with inline `[1]`, `[2]` citation markers
6. Structure output as `GroundedAnswer`:
   ```python
   GroundedAnswer(
       answer="Nvidia's revenue in FY2025 was $60.9 billion [1], driven by...",
       citations=[
           Citation(citation_index=1, chunk_id=<uuid>, excerpt="...60.9 billion..."),
           Citation(citation_index=2, chunk_id=<uuid>, excerpt="...driven by..."),
       ],
       insufficient_evidence=False,
   )
   ```

---

### Step 4: SQL Queries Executed — Retrieval Pipeline

**Files:**
- `backend/app/retrieval/retriever.py` → DocumentRetriever.retrieve()
- `backend/app/retrieval/queries.py` → semantic_search(), fulltext_search()
- `backend/app/retrieval/fusion.py` → reciprocal_rank_fusion()

**Hybrid Retrieval Flow:**

#### 4a. Embed Query
```python
def _embed_query(self, query: str) -> list[float]:
    response = self.openai_client.embeddings.create(
        input=query,
        model=settings.openai_embedding_model,  # "text-embedding-3-small"
    )
    return response.data[0].embedding  # 1536-dim vector
```

**Files:** Uses OpenAI API directly
**SQL touched:** None yet (API call)
**Inputs:** `"What was Nvidia revenue in FY2025?"`
**Outputs:** `[0.001, -0.002, ..., 0.003]` (1536 floats)

#### 4b. Semantic Search (pgvector)
```python
def semantic_search(db: Session, query_embedding: list[float], top_k: int = 20):
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    query = text(f"""
        SELECT
            id::text AS chunk_id,
            document_id::text,
            text,
            chunk_metadata,
            (1 - (embedding <=> '{embedding_str}'::vector)) AS score
        FROM document_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> '{embedding_str}'::vector
        LIMIT :top_k
    """)
    return [ChunkRow(...) for row in db.execute(query, {"top_k": 20})]
```

**SQL:** Cosine similarity search via `<=>` operator on HNSW index
**Files:** `backend/app/retrieval/queries.py:18-59`
**Database Tables:** `document_chunks` (indexed on `embedding` via HNSW)
**Inputs:** 1536-dim vector, top_k=5 (default semantic_k)
**Outputs:** Top 5 chunks by cosine similarity, with `chunk_id`, `text`, `chunk_metadata`, `score`

#### 4c. Full-Text Search (Postgres tsvector)
```python
def fulltext_search(db: Session, query_text: str, top_k: int = 20):
    query = text("""
        SELECT
            id::text AS chunk_id,
            document_id::text,
            text,
            chunk_metadata,
            ts_rank(to_tsvector('english', search_vector), plainto_tsquery('english', :query)) AS score
        FROM document_chunks
        WHERE to_tsvector('english', search_vector) @@ plainto_tsquery('english', :query)
        ORDER BY ts_rank(...) DESC
        LIMIT :top_k
    """)
    return [ChunkRow(...) for row in db.execute(query, {"query": query_text, "top_k": 20})]
```

**SQL:** Full-text search via GIN index on `to_tsvector('english', search_vector)`
**Files:** `backend/app/retrieval/queries.py:62-103`
**Database Tables:** `document_chunks` (indexed on `search_vector` via GIN)
**Inputs:** "What was Nvidia revenue in FY2025?", top_k=5 (default fulltext_k)
**Outputs:** Top 5 chunks by ts_rank, with same metadata

#### 4d. Reciprocal Rank Fusion
```python
def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, item_id in enumerate(ranked_list, start=1):
            score = 1.0 / (k + rank)
            scores[item_id] = scores.get(item_id, 0) + score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

**Purpose:** Fuse semantic and full-text results. If a chunk ranks high in both, it gets a higher combined score.

**Formula:** `score = 1/(60 + rank_in_list)`

**Files:** `backend/app/retrieval/fusion.py:4-24`
**Inputs:** [[semantic_ids], [fulltext_ids]]
**Outputs:** [(chunk_id, rrf_score), ...] sorted by rrf_score DESC

#### 4e. Fetch Full Passages
```python
def _fetch_passages(self, db: Session, chunk_ids: list[str], is_neighbor: bool = False):
    query = text(f"""
        SELECT
            document_chunks.id::text,
            document_chunks.document_id::text,
            document_chunks.text,
            document_chunks.chunk_metadata,
            source_documents.ticker,
            source_documents.filing_type,
            source_documents.filing_year
        FROM document_chunks
        LEFT JOIN source_documents ON document_chunks.document_id = source_documents.id
        WHERE document_chunks.id::text IN ({','.join([f"'{cid}'" for cid in chunk_ids])})
    """)
    return [RetrievedPassage(...) for row in db.execute(query)]
```

**SQL:** JOIN `document_chunks` + `source_documents` to get full metadata
**Files:** `backend/app/retrieval/retriever.py:107-155`
**Database Tables:** `document_chunks`, `source_documents`
**Inputs:** Top 3 chunk IDs from RRF fusion
**Outputs:** `[RetrievedPassage(...), ...]` with full text, ticker, filing_type, filing_year, heading, chunk_index, rrf_score

#### 4f. Retrieve Summary
```python
retriever.retrieve(
    query="What was Nvidia revenue in FY2025?",
    db=db,
    top_k=3,
    neighbor_window=0,  # Default
) → list[RetrievedPassage]
```

**Result:** 3 most relevant passages, fused from semantic + full-text search, ready for agent consumption.

---

### Step 5: Prompt Assembled

**Files:** `backend/app/assistant/instructions.md` (system prompt)

The agent receives:
1. **System instructions** (~3000 tokens) → from instructions.md
2. **User query** (~20 tokens) → "What was Nvidia revenue in FY2025?"
3. **Retrieved passages** (~1500 tokens) → From Step 4, injected into context

**Token breakdown (logged):**
```
[AGENT] System instructions: 3142 tokens (18923 characters)
[TURN] User message: 12 tokens
[SEARCH_FILINGS] Returning 3 passages (1548 tokens)
[TURN] System instructions: 3142 tokens
```

---

### Step 6: Model Called — gpt-4o

**Files:** PydanticAI invokes OpenAI API
**Model:** `gpt-4o` (per `settings.openai_chat_model`)
**Cost:** ~0.0015 + 0.004 tokens (input + output)

**Agent's forward pass:**
1. LLM reads system instructions, user query, retrieved passages
2. LLM decides to call tool `search_filings()` with refined filters
3. LLM receives tool result, decides to call `read_chunk()` for additional context
4. LLM synthesizes answer with citations: `"...revenue was $60.9B [1]..."`
5. LLM returns `GroundedAnswer` object (forced via Pydantic output_type)

**Output schema (enforced):**
```python
class GroundedAnswer(BaseModel):
    answer: str  # "Nvidia's revenue in FY2025 was $60.9 billion [1]..."
    citations: list[Citation]  # [Citation(citation_index=1, chunk_id=<uuid>, excerpt=...)]
    insufficient_evidence: bool  # False
```

---

### Step 7: Citations Validated

**Files:** `backend/app/grounding/validator.py:33-106`

**Validator stages:**
1. **Content exists:** answer.answer.strip() is not empty ✓
2. **Consistency:** insufficient_evidence=False implies citations must exist ✓
3. **At least one citation:** If not insufficient_evidence, must have ≥1 citation ✓
4. **Citation indices:** Must be 1-based, unique, contiguous (e.g., [1, 2, 3], not [1, 3, 5]) ✓
5. **Markers match indices:** Every `[n]` in answer must match a citation with citation_index=n ✓
6. **All chunks in registry:** Every chunk_id must exist in TurnRegistry (citation allowlist) ✓

**If validation fails:**
- Log error
- Retry agent (up to MAX_RETRIES=2)
- If all retries exhaust, yield error event and return

**If validation succeeds:**
- Proceed to streaming

---

### Step 8: Response Streamed to Frontend

**Files:**
- Backend: `backend/app/chat/orchestrator.py:131-148`
- Frontend: `frontend/src/lib/chat.ts:26-97`

**Streaming format (AI SDK compatible):**

Backend emits:
```
0:"Nvidia's "
0:"revenue "
0:"in "
0:"FY2025 "
0:"was "
0:"$60.9 "
0:"billion "
0:"[1] "
d:{"type":"citation","data":{"citation_index":1,"chunk_id":"<uuid>","excerpt":"...60.9 billion...","ticker":"NVDA","filing_type":"10-K","filing_year":2025,"heading":"Consolidated Results of Operations"}}
```

**Event format:**
```python
def text_event(token: str) -> str:
    return f'0:{json.dumps(token)}\n'

def data_event(payload: dict) -> str:
    return f'd:{json.dumps(payload)}\n'

def citation_data_event(citation: Citation, passage: RetrievedPassage) -> str:
    return data_event({
        "type": "citation",
        "data": {
            "citation_index": citation.citation_index,
            "chunk_id": str(citation.chunk_id),
            "excerpt": citation.excerpt,
            "ticker": passage.ticker,
            "filing_type": passage.filing_type,
            "filing_year": passage.filing_year,
            "heading": passage.heading,
        }
    })
```

**Frontend parses stream:**
```typescript
for await (const event of generator) {
    if (event.type === 'text') {
        // Append to message.content
    } else if (event.type === 'data' && payload.type === 'citation') {
        // Add to message.citations array
    }
}
```

**User sees:**
- Words streaming in real-time
- Citations appear after answer completes
- Citation chips clickable, show source passage

---

### Step 9: Response Persisted

**Files:** `backend/app/chat/orchestrator.py:151-172`

**Database operations:**

```python
msg = ChatMessage(thread_id=thread.id, role="assistant", content=full_text)
db.add(msg)
db.flush()  # Get msg.id without committing yet

for citation in grounded.citations:
    passage = registry.get(str(citation.chunk_id))
    db.add(
        MessageCitation(
            message_id=msg.id,
            chunk_id=citation.chunk_id,
            section=passage.heading if passage else None,
        )
    )

# Auto-title thread from first assistant response
if not thread.title or thread.title == "New Chat":
    thread.title = generate_thread_title(full_text)
    log.info(f"[TURN] Auto-titled thread: {thread.title}")

thread.updated_at = datetime.utcnow()
db.commit()
```

**Tables touched:**
- `chat_messages` (insert) — stores full answer text
- `message_citations` (insert) — stores citation links
- `chat_threads` (update) — updates title and updated_at

**Final state:**
```
chat_threads
  id: <uuid>
  user_id: <uuid>
  title: "Nvidia FY2025 Revenue"  (auto-generated)
  created_at: 2026-06-14 10:00:00
  updated_at: 2026-06-14 10:05:00

chat_messages (user)
  id: <uuid>
  thread_id: <uuid>
  role: "user"
  content: "What was Nvidia revenue in FY2025?"
  created_at: 2026-06-14 10:05:00

chat_messages (assistant)
  id: <uuid>
  thread_id: <uuid>
  role: "assistant"
  content: "Nvidia's revenue in FY2025 was $60.9 billion [1], driven by..."
  created_at: 2026-06-14 10:05:01

message_citations
  id: <uuid>
  message_id: <uuid>  (assistant message)
  chunk_id: <uuid>  (document_chunks.id)
  section: "Consolidated Results of Operations"
  created_at: 2026-06-14 10:05:01
```

---

## 3. Sequence Diagram

```
User                Frontend              API                Retriever           Database           OpenAI
 |                     |                   |                     |                 |                 |
 |-- Login form ------>|                   |                     |                 |                 |
 |                     |--- POST /auth/login ---|                 |                 |                 |
 |                     |                   |--- Query User ------>|                 |                 |
 |                     |                   |<--- User found ------|                 |                 |
 |<-- JWT cookie ------|<--- JWT cookie ---|                     |                 |                 |
 |                     |                   |                     |                 |                 |
 |-- New Chat -------->|                   |                     |                 |                 |
 |                     |--- POST /chat/threads ---|                 |                 |                 |
 |                     |                   |-- Insert ChatThread --|                 |                 |
 |<-- Thread ID -------|<--- Thread ID ---|                     |                 |                 |
 |                     |                   |                     |                 |                 |
 |-- Query ----------->|                   |                     |                 |                 |
 |  (with ThreadID)    |--- POST /chat/stream (SSE) ---|         |                 |                 |
 |                     |                   |                     |                 |                 |
 |                     |                   |--- Auth check ------>|                 |                 |
 |                     |                   |<--- User verified ----|                 |                 |
 |                     |                   |                     |                 |                 |
 |                     |                   |--- Save User Message ---|                 |                 |
 |                     |                   |                     |                 |                 |
 |                     |                   |--- run_turn() ------>|                 |                 |
 |                     |                   |                     |                 |                 |
 |                     |                   |                     |--- Get Query Embedding ---|------->|
 |                     |                   |                     |<--- Embedding Returned ---|<-------|
 |                     |                   |                     |                 |                 |
 |                     |                   |                     |--- Semantic Search (pgvector) ---|
 |                     |                   |                     |<--- Top 5 chunks by similarity ---|
 |                     |                   |                     |                 |                 |
 |                     |                   |                     |--- Full-text Search ---|
 |                     |                   |                     |<--- Top 5 chunks by rank ---|
 |                     |                   |                     |                 |                 |
 |                     |                   |                     |--- RRF Fusion ---|
 |                     |                   |                     |<--- Top 3 fused chunks ---|
 |                     |                   |                     |                 |                 |
 |                     |                   |--- Invoke Agent with passages ---|------->|
 |                     |                   |                     |                 | (gpt-4o reasoning)
 |                     |                   |<--- GroundedAnswer ---|<-------|
 |                     |                   |                     |                 |                 |
 |                     |                   |--- Validate Citations ---|                 |                 |
 |                     |                   |<--- Valid ---|                 |                 |
 |                     |                   |                     |                 |                 |
 |                     |<--- SSE: 0:"token" ---|                 |                 |                 |
 |<-- Streaming -------|<--- SSE: d:{citation} ---|                 |                 |                 |
 |  response           |                   |                     |                 |                 |
 |                     |                   |--- Save Message + Citations ---|     |                 |
 |                     |                   |                     |                 |                 |
 |<--- Done -----------|<--- SSE: (done) ---|                 |                 |                 |
 |                     |                   |                     |                 |                 |
```

---

## 4. Database Map

### 4.1 Table: `users`

**Purpose:** Store registered users with email-based authentication.

```
Table: users
├─ id: UUID (primary key)
│  └─ Generated via uuid4()
├─ email: String(255) (unique, indexed)
│  └─ User's email, must be unique
├─ password_hash: String(255) (nullable)
│  └─ Bcrypt hash via hash_password()
│  └─ NULL if using Supabase Auth
└─ created_at: DateTime
   └─ Set at user creation

Indexes:
├─ PRIMARY KEY: id
└─ UNIQUE INDEX: email
```

**Relationships:**
- `chat_threads.user_id` → `users.id` (1:many)

**Row-Level Security (RLS):** Not enabled on users table (admin view all)

---

### 4.2 Table: `source_documents`

**Purpose:** Store metadata for SEC filings (documents).

```
Table: source_documents
├─ id: UUID (primary key)
├─ ticker: String(10) (indexed)
│  └─ Company ticker symbol (e.g., "NVDA", "AAPL")
├─ filing_type: String(20)
│  └─ SEC form type: "10-K", "10-Q", "8-K"
├─ filing_year: Integer
│  └─ Fiscal year (e.g., 2025)
├─ filing_date: DateTime
│  └─ Date filed with SEC
├─ url: String(512)
│  └─ Link to SEC filing (EDGAR)
└─ created_at: DateTime
   └─ When document was indexed

Indexes:
├─ PRIMARY KEY: id
└─ INDEX: ticker
```

**Relationships:**
- `document_chunks.document_id` → `source_documents.id` (1:many)

**How filled:** External data pipeline (not in current codebase)

---

### 4.3 Table: `document_chunks`

**Purpose:** Store embeddings and chunks of SEC filings, indexed for hybrid search.

```
Table: document_chunks
├─ id: UUID (primary key)
├─ document_id: UUID (FK → source_documents.id, indexed)
│  └─ Foreign key to parent filing
├─ text: Text
│  └─ Chunk content (e.g., ~500-word excerpt)
├─ embedding: Vector(1536)
│  └─ OpenAI text-embedding-3-small (1536 dimensions)
│  └─ Used for semantic (cosine) search via pgvector
├─ chunk_metadata: JSON (nullable)
│  └─ {"chunk_index": 0, "heading": "Business Summary", ...}
│  └─ chunk_index: position in document (for neighbor queries)
│  └─ heading: section header from document
├─ search_vector: Text
│  └─ Plain text copy of chunk (for full-text search)
└─ created_at: DateTime

Indexes:
├─ PRIMARY KEY: id
├─ INDEX: document_id (for lookups by document)
├─ HNSW INDEX: embedding (for cosine similarity via <=>)
│  └─ Used in: semantic_search()
└─ GIN INDEX: to_tsvector('english', search_vector)
   └─ Used in: fulltext_search()
```

**Relationships:**
- `document_chunks.document_id` → `source_documents.id` (many:1)
- `message_citations.chunk_id` → `document_chunks.id` (many:1)

**Row-Level Security (RLS):** Enabled, allows all authenticated users (shared corpus)

---

### 4.4 Table: `chat_threads`

**Purpose:** Store conversation threads per user.

```
Table: chat_threads
├─ id: UUID (primary key)
├─ user_id: UUID (FK → users.id, indexed)
│  └─ Owner of the thread
├─ title: String(255) (nullable)
│  └─ Auto-generated from first assistant response
│  └─ Or user-provided at creation
├─ created_at: DateTime
│  └─ When thread was created
└─ updated_at: DateTime
   └─ When last message added

Indexes:
├─ PRIMARY KEY: id
└─ INDEX: user_id (for list_threads query)
```

**Relationships:**
- `chat_threads.user_id` → `users.id` (many:1)
- `chat_messages.thread_id` → `chat_threads.id` (1:many)

**Row-Level Security (RLS):** Enabled
```sql
CREATE POLICY "Users see only their own chat threads"
ON chat_threads FOR SELECT
USING (auth.uid() = user_id)
```

---

### 4.5 Table: `chat_messages`

**Purpose:** Store individual messages (user + assistant) within a thread.

```
Table: chat_messages
├─ id: UUID (primary key)
├─ thread_id: UUID (FK → chat_threads.id, indexed)
│  └─ Parent thread
├─ role: String(20)
│  └─ "user" or "assistant"
├─ content: Text
│  └─ Full message text (up to 2M chars in Postgres)
│  └─ For user: query
│  └─ For assistant: answer with inline [1], [2] citation markers
└─ created_at: DateTime

Indexes:
├─ PRIMARY KEY: id
└─ INDEX: thread_id (for get_messages query)
```

**Relationships:**
- `chat_messages.thread_id` → `chat_threads.id` (many:1)
- `message_citations.message_id` → `chat_messages.id` (1:many)

**Row-Level Security (RLS):** Enabled
```sql
CREATE POLICY "Users see only messages in their own threads"
ON chat_messages FOR SELECT
USING (thread_id IN (
    SELECT id FROM chat_threads WHERE user_id = auth.uid()
))
```

---

### 4.6 Table: `message_citations`

**Purpose:** Link messages to source passages (many-to-many via document chunks).

```
Table: message_citations
├─ id: UUID (primary key)
├─ message_id: UUID (FK → chat_messages.id, indexed)
│  └─ Assistant message that made the claim
├─ chunk_id: UUID (FK → document_chunks.id)
│  └─ Source chunk that supports the claim
├─ page_number: Integer (nullable)
│  └─ Original page number in SEC filing (if available)
├─ section: String(255) (nullable)
│  └─ Section heading from chunk.chunk_metadata.heading
└─ created_at: DateTime

Indexes:
├─ PRIMARY KEY: id
└─ INDEX: message_id (for get_citations_by_message)
```

**Relationships:**
- `message_citations.message_id` → `chat_messages.id` (many:1)
- `message_citations.chunk_id` → `document_chunks.id` (many:1)

**Row-Level Security (RLS):** Enabled
```sql
CREATE POLICY "Users see only citations in their own threads"
ON message_citations FOR SELECT
USING (message_id IN (
    SELECT id FROM chat_messages
    WHERE thread_id IN (
        SELECT id FROM chat_threads WHERE user_id = auth.uid()
    )
))
```

---

## 5. RAG Architecture Map

### 5.1 Chunking (Pre-processing, external to this codebase)

Assumed complete before documents enter system:

```
Raw SEC Filing (10-K, 50 pages)
    ↓
[External Pipeline: Chunking]
    ├─ Split by semantic sections (Business, MD&A, Risk Factors, ...)
    └─ Target chunk size: ~500 words per chunk
    ↓
Chunks with metadata
    ├─ chunk_index: 0, 1, 2, ... (position in document)
    ├─ heading: "Item 1. Business"
    └─ text: "The Company operates in three segments..."
```

**Files:** Not in this codebase; assumed external.

---

### 5.2 Embedding Generation (Pre-processing)

For each chunk, generate OpenAI embedding:

```python
# Assumed external or in a separate data pipeline
embedding_model = "text-embedding-3-small"
chunk_text = "The Company operates in three segments..."

response = client.embeddings.create(
    input=chunk_text,
    model=embedding_model,
)
embedding = response.data[0].embedding  # 1536-dim vector
```

**Cost:** ~$0.02 per 1M tokens
**Stored:** `document_chunks.embedding` (vector column in Postgres)

---

### 5.3 Embedding Storage

```
INSERT INTO document_chunks (
    id, document_id, text, embedding, chunk_metadata, search_vector, created_at
) VALUES (
    '<uuid>', '<doc-uuid>', '<text>', '<1536-dim vector>', 
    '{"chunk_index": 0, "heading": "..."}', '<text>', '<datetime>'
)
```

**Index created (HNSW):**
```sql
CREATE INDEX ix_document_chunks_embedding_hnsw 
ON document_chunks USING hnsw (embedding vector_cosine_ops)
```

**Purpose:** Fast nearest-neighbor search via cosine distance

---

### 5.4 Similarity Search (At query time)

**User Query:** "What was Nvidia revenue in FY2025?"

**Step 1: Embed query**
```python
query_embedding = client.embeddings.create(
    input="What was Nvidia revenue in FY2025?",
    model="text-embedding-3-small",
).data[0].embedding  # 1536-dim
```

**Step 2: Cosine similarity search**
```sql
SELECT
    id::text AS chunk_id,
    document_id::text,
    text,
    chunk_metadata,
    (1 - (embedding <=> '<query_vector>'::vector)) AS score
FROM document_chunks
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '<query_vector>'::vector  -- HNSW index used
LIMIT 5  -- Top 5 by similarity
```

**Files:** `backend/app/retrieval/queries.py:18-59` (semantic_search)

**Result:** Top 5 chunks by cosine distance, e.g.:
```
[
  RetrievedPassage(chunk_id='...', text='...revenue of $60.9B...', ticker='NVDA', score=0.82),
  RetrievedPassage(chunk_id='...', text='...due to AI demand...', ticker='NVDA', score=0.78),
  ...
]
```

---

### 5.5 Full-Text Search (Hybrid, keyword-based)

**Purpose:** Catch queries with specific keywords (e.g., "revenue", "2025", "Nvidia")

```sql
SELECT
    id::text AS chunk_id,
    document_id::text,
    text,
    chunk_metadata,
    ts_rank(to_tsvector('english', search_vector), plainto_tsquery('english', :query)) AS score
FROM document_chunks
WHERE to_tsvector('english', search_vector) @@ plainto_tsquery('english', :query)
ORDER BY ts_rank(...) DESC
LIMIT 5
```

**Files:** `backend/app/retrieval/queries.py:62-103` (fulltext_search)

**Index (GIN):**
```sql
CREATE INDEX ix_document_chunks_search_vector_gin 
ON document_chunks USING gin (to_tsvector('english', search_vector))
```

**Query parsing:** `plainto_tsquery` is **safe** for user input (doesn't parse operators)

**Result:** Top 5 chunks matching keywords

---

### 5.6 Fusion (Reciprocal Rank Fusion)

**Purpose:** Combine semantic + full-text rankings into single list

```python
semantic_ids = ['chunk_uuid_1', 'chunk_uuid_2', 'chunk_uuid_3', 'chunk_uuid_4', 'chunk_uuid_5']
fulltext_ids = ['chunk_uuid_2', 'chunk_uuid_6', 'chunk_uuid_1', 'chunk_uuid_7', 'chunk_uuid_3']

fused = reciprocal_rank_fusion([semantic_ids, fulltext_ids])
# Output (example):
# [
#   ('chunk_uuid_1', 0.0278),  # Ranked 1 in semantic, 3 in fulltext
#   ('chunk_uuid_2', 0.0270),  # Ranked 2 in semantic, 1 in fulltext
#   ('chunk_uuid_3', 0.0233),  # Ranked 3 in semantic, 5 in fulltext
#   ...
# ]
```

**Formula:** `score = sum(1 / (60 + rank))` for each list

**Files:** `backend/app/retrieval/fusion.py:4-24` (reciprocal_rank_fusion)

**Result:** Top 3 chunks from fused ranking

---

### 5.7 Context Selection

**Retriever.retrieve() flow:**

```python
def retrieve(self, query: str, db: Session, top_k: int = 3, neighbor_window: int = 0):
    # 1. Embed query
    embedding = self._embed_query(query)
    
    # 2. Run semantic + fulltext searches
    semantic_results = semantic_search(db, embedding, top_k=self.semantic_k)  # 5
    fulltext_results = fulltext_search(db, query, top_k=self.fulltext_k)  # 5
    
    # 3. Fuse rankings
    semantic_ids = [r.chunk_id for r in semantic_results]
    fulltext_ids = [r.chunk_id for r in fulltext_results]
    fused = reciprocal_rank_fusion([semantic_ids, fulltext_ids])
    
    # 4. Take top_k from fused
    top_chunk_ids = [chunk_id for chunk_id, _ in fused[:top_k]]  # Top 3
    
    # 5. Fetch full passage objects with metadata
    passages = self._fetch_passages(db, top_chunk_ids, is_neighbor=False)
    
    # 6. Optional: expand with neighboring chunks (for context)
    if neighbor_window > 0:
        neighbors = self._expand_neighbors(db, passages, neighbor_window)
        passages.extend(neighbors)
    
    # 7. Sort by RRF score
    sorted_passages = sorted(passages, key=lambda p: p.rrf_score, reverse=True)
    
    return sorted_passages
```

**Files:** `backend/app/retrieval/retriever.py:49-97` (retrieve)

**Inputs:** User query, top_k (default 3)
**Outputs:** Ranked list of RetrievedPassage objects

---

### 5.8 Prompt Construction

**Files:** `backend/app/assistant/agent.py` + `backend/app/assistant/instructions.md`

**Prompt structure:**

```
SYSTEM (from instructions.md):
  "You are a financial analyst AI assistant. You help users understand SEC filings..."
  [3000 tokens of detailed instructions]

USER:
  "What was Nvidia revenue in FY2025?"

ASSISTANT (from search_filings tool):
  [1] {ticker} {filing_type} {filing_year}
      Section: {heading}
      Chunk ID: {chunk_id}
      Text: {chunk text, ~500 words}
  
  [2] {ticker} {filing_type} {filing_year}
      Section: {heading}
      Chunk ID: {chunk_id}
      Text: {chunk text, ~500 words}
  
  [3] {ticker} {filing_type} {filing_year}
      Section: {heading}
      Chunk ID: {chunk_id}
      Text: {chunk text, ~500 words}
```

**Token accounting:**
```
System instructions: ~3000 tokens
User query: ~12 tokens
Retrieved passages: ~1500 tokens
─────────────────
Total input: ~4500 tokens (varies based on passage length)
```

---

### 5.9 Grounding Validation

**Files:** `backend/app/grounding/validator.py:33-106` (GroundingValidator.validate)

**Validation stages:**

1. **Answer content exists**
   - Check: `answer.answer.strip()` is not empty
   - Fail: Return error "Answer text is empty"

2. **Insufficient evidence consistency**
   - Rule: If `insufficient_evidence=True`, then `citations=[]`
   - Rule: If `insufficient_evidence=False`, then `citations` must be non-empty
   - Fail: "insufficient_evidence=True but citations exist" or vice versa

3. **Citation indices validity**
   - Check: All indices are 1-based (≥1)
   - Check: Indices are unique and contiguous (e.g., [1, 2, 3], not [1, 3, 5])
   - Fail: Return error with expected vs. actual

4. **Citation markers match**
   - Extract all `[n]` patterns from answer text
   - Verify: Every citation_index has a corresponding `[n]` marker
   - Fail: "Marker [5] in answer but only 3 citations provided"

5. **All chunks in registry**
   - Check: Every citation.chunk_id exists in TurnRegistry
   - Fail: "Citation chunk not in allowlist (wasn't retrieved)"

**Result:** `ValidationResult(ok: bool, errors: list[str])`

**Retry logic:** If validation fails, retry agent up to MAX_RETRIES=2 times (total 3 attempts)

---

### 5.10 Citation Generation (Streaming)

**Files:** `backend/app/chat/orchestrator.py:144-148` + `backend/app/chat/streaming.py:24-37`

For each citation in `grounded.citations`:

```python
for citation in grounded.citations:
    passage = registry.get(str(citation.chunk_id))
    if passage:
        yield citation_data_event(citation, passage)

def citation_data_event(citation: Citation, passage: RetrievedPassage) -> str:
    return data_event({
        "type": "citation",
        "data": {
            "citation_index": citation.citation_index,
            "chunk_id": str(citation.chunk_id),
            "excerpt": citation.excerpt,  # Max 125 chars
            "ticker": passage.ticker,
            "filing_type": passage.filing_type,
            "filing_year": passage.filing_year,
            "heading": passage.heading,
        }
    })
```

**Format:** AI SDK-compatible SSE (Server-Sent Events)
```
d:{"type":"citation","data":{"citation_index":1,"chunk_id":"...","excerpt":"...","ticker":"NVDA",...}}
```

**Frontend receives:** Citation object, renders as clickable chip with metadata

---

## 6. RAG Architecture Summary (Visual)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER QUERY                                          │
│                "What was Nvidia revenue in FY2025?"                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Query Embedding (OpenAI)    │
                    │  text-embedding-3-small       │
                    │  1536-dim vector              │
                    └───────────────────────────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    ▼                                ▼
        ┌──────────────────────┐        ┌──────────────────────┐
        │ Semantic Search      │        │ Full-Text Search     │
        │ (pgvector HNSW)      │        │ (Postgres GIN)       │
        │ Top 5 by cosine      │        │ Top 5 by ts_rank     │
        │ similarity           │        │                      │
        │                      │        │                      │
        │ Results:             │        │ Results:             │
        │ chunk_1: 0.82        │        │ chunk_2: rank 0.75   │
        │ chunk_2: 0.78        │        │ chunk_1: rank 0.70   │
        │ chunk_3: 0.75        │        │ chunk_6: rank 0.65   │
        │ chunk_4: 0.72        │        │ chunk_7: rank 0.60   │
        │ chunk_5: 0.70        │        │ chunk_3: rank 0.55   │
        └──────────────────────┘        └──────────────────────┘
                    │                                │
                    └───────────────┬────────────────┘
                                    ▼
                ┌──────────────────────────────────────┐
                │    Reciprocal Rank Fusion (RRF)     │
                │  Combine two ranked lists            │
                │  Formula: score = Σ(1/(60 + rank))  │
                │                                      │
                │  Fused Ranking:                      │
                │  1. chunk_1 (0.0278)                │
                │  2. chunk_2 (0.0270)                │
                │  3. chunk_3 (0.0233)                │
                │  4. chunk_6 (0.0210)                │
                │  5. chunk_7 (0.0196)                │
                └──────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  Take Top-K (K=3)             │
                    │  chunk_1, chunk_2, chunk_3    │
                    │                               │
                    │  Fetch full metadata:         │
                    │  - ticker, filing_type, year  │
                    │  - section heading            │
                    │  - chunk_index (for context)  │
                    └───────────────────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────┐
                │  Context Selection Complete          │
                │  RetrievedPassage[] ready for agent  │
                └──────────────────────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │  Prompt Assembly    │
                        │                     │
                        │ System prompt       │
                        │ + User query        │
                        │ + Retrieved chunks  │
                        │                     │
                        │ Total: ~4500 tokens │
                        └─────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │   LLM (gpt-4o)      │
                        │                     │
                        │ - Tool calls        │
                        │ - Reasoning         │
                        │ - Output validation │
                        └─────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │   GroundedAnswer    │
                        │                     │
                        │ answer: "..."       │
                        │ citations: [...]    │
                        │ insufficient_ev: bool
                        └─────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  Grounding Validation         │
                    │  6-stage validator            │
                    │  - Content checks             │
                    │  - Citation consistency       │
                    │  - Index validity             │
                    │  - Marker matching            │
                    │  - Registry allowlist         │
                    │                               │
                    │  Result: VALID ✓              │
                    └───────────────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │   Stream Response   │
                        │                     │
                        │ 0:"token"           │
                        │ 0:"by"              │
                        │ 0:"token"           │
                        │ d:{citation}        │
                        └─────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │   Persist to DB     │
                        │                     │
                        │ chat_messages       │
                        │ message_citations   │
                        │ chat_threads        │
                        └─────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │  User sees answer   │
                        │  with citations     │
                        └─────────────────────┘
```

---

## 7. Identified Gaps & What to Inspect Next

### Gap 1: Document Ingestion Pipeline

**Current state:** Documents are assumed to be pre-loaded. No upload endpoint in `/documents` beyond chunk context retrieval.

**What's missing:**
- How are raw SEC filings downloaded?
- How are they chunked into ~500-word pieces?
- How are embeddings generated and stored?
- What's the orchestration for batch indexing?

**Where to inspect next:**
- `backend/app/api/documents.py` — only has `GET /documents/chunks/{chunk_id}/context`
- External data pipeline (likely separate codebase or script)
- Check `data/` directory for any ingestion scripts

---

### Gap 2: Agent Tool Invocation Details

**Current state:** Agent.tool decorators define tools, but the actual invocation logic is handled by PydanticAI framework.

**What's unclear:**
- How does the agent decide which tool to call?
- What's the exact format of tool_choice in the LLM request?
- Are there any tool call retries or error handling within agent execution?
- How does the agent know when to stop calling tools?

**Where to inspect next:**
- `backend/app/assistant/agent.py:31-250+` — Complete agent definition with all tools
- `backend/app/assistant/instructions.md` — Agent system prompt (likely guides tool use)
- PydanticAI documentation for Agent execution model

---

### Gap 3: Neighboring Chunks & Context Windows

**Current state:** `retrieve()` has `neighbor_window` parameter (default 0), but it's not used in normal chat.

**What's unclear:**
- When would neighbor_window > 0 be set?
- How are neighbors selected (chunk_index ± window)?
- What's the max neighbor expansion? Token budget?

**Where to inspect next:**
- `backend/app/retrieval/retriever.py:157-195` (_expand_neighbors)
- Agent's `read_surrounding_chunks()` tool uses neighbors explicitly

---

### Gap 4: Insufficient Evidence Handling

**Current state:** Agent can return `insufficient_evidence=True`, triggering a specific response stream.

**What's missing:**
- What's the exact wording of "insufficient evidence" response?
- Does the agent receive explicit instructions to set this flag?
- Are there metrics on how often this occurs?

**Where to inspect next:**
- `backend/app/assistant/instructions.md` — should define when to set flag
- `backend/app/chat/orchestrator.py:136-139` — handles insufficient_evidence case

---

### Gap 5: Retry Logic & Validation Failures

**Current state:** If validation fails, agent is retried up to MAX_RETRIES=2.

**What's unclear:**
- What causes repeated validation failures (beyond citation issues)?
- Is there a logging/metrics dashboard tracking retry rates?
- What if all retries are exhausted?

**Where to inspect next:**
- `backend/app/chat/orchestrator.py:94-126` — retry loop
- `backend/app/grounding/validator.py` — validation logic
- Application logs for error patterns

---

### Gap 6: RLS (Row-Level Security) Enforcement

**Current state:** RLS policies are defined but implemented at DB level, not app level.

**What's unclear:**
- Is RLS actually enabled in production?
- How are RLS policies tested?
- What's the fallback if RLS fails (e.g., Supabase service role key leaked)?

**Where to inspect next:**
- `backend/alembic/versions/001_initial_schema.py:113-148` — RLS policy definitions
- Supabase project settings for RLS enforcement
- `backend/app/database/supabase.py` — DB connection setup

---

### Gap 7: Citation Extraction from LLM Output

**Current state:** Agent.output_type=GroundedAnswer enforces Pydantic validation.

**What's unclear:**
- If LLM outputs malformed JSON, how is it handled?
- Are there retry attempts with reformatted prompts?
- What percentage of LLM calls fail output validation?

**Where to inspect next:**
- PydanticAI documentation for output validation retry behavior
- `backend/app/assistant/outputs.py` — GroundedAnswer schema
- Application error logs

---

### Gap 8: Token Counting & Budget

**Current state:** Token counting is logged but no hard limit enforced.

**What's missing:**
- Is there a per-request token budget?
- What happens if query + passages + response exceeds context window?
- How does truncation work (if at all)?

**Where to inspect next:**
- `backend/app/utils/tokens.py` — count_tokens() function
- `backend/app/chat/orchestrator.py:74-81` — token logging
- No hard limit visible in current code

---

### Gap 9: Embedding Freshness & Updates

**Current state:** Embeddings are static once generated.

**What's missing:**
- How often are embeddings regenerated?
- If a filing is updated, are old chunks deleted?
- Is there soft-delete or versioning?

**Where to inspect next:**
- `backend/app/api/documents.py` — no update/delete endpoints visible
- Migration files for any document lifecycle management
- External data pipeline for document updates

---

### Gap 10: Frontend Citation Interaction

**Current state:** Frontend renders citations as clickable chips.

**What's unclear:**
- What happens when user clicks a citation?
- Is the full chunk displayed? Context?
- Can user navigate to source SEC filing?

**Where to inspect next:**
- `frontend/src/components/chat/CitationChip.tsx` — citation rendering
- `frontend/src/components/chat/SourcePassageSheet.tsx` — citation detail view
- `backend/app/api/documents.py:34-110` — chunk context endpoint

---

## 8. Explain This System to a Technical Interviewer (5-Minute Version)

---

**"Document Copilot" is a financial AI assistant that helps users understand SEC filings through a retrieval-augmented generation (RAG) system.**

**Architecture overview:**

1. **Authentication**: Users register/login with email + password. Sessions are managed via JWT stored in HttpOnly cookies. Each user owns chat threads isolated via row-level security in Postgres.

2. **Document Storage**: SEC filings (10-K, 10-Q, 8-K) are pre-processed externally: chunked into ~500-word segments, embedded using OpenAI's text-embedding-3-small (1536 dims), and stored in Postgres with pgvector. We maintain two search indices: HNSW for semantic similarity and GIN for full-text search.

3. **Hybrid Retrieval**: When a user asks a question, we perform **dual search**: 
   - Embed the query and run cosine similarity search via pgvector
   - Run full-text search using Postgres tsvector for keyword matching
   - Fuse the two ranked lists using Reciprocal Rank Fusion (RRF) with formula `score = 1/(60 + rank)`
   - Return top 3 chunks

4. **LLM Reasoning**: We use a PydanticAI agent with gpt-4o. The agent:
   - Receives system instructions + user query + retrieved passages (~4500 tokens total)
   - Has access to tools: `search_filings()`, `read_chunk()`, `read_surrounding_chunks()`
   - Generates an answer with inline `[n]` citation markers
   - Returns structured output (GroundedAnswer with citations)

5. **Citation Validation**: Before streaming, we run a **6-stage validator**:
   - Content exists
   - Citation indices are 1-based, unique, contiguous
   - Every citation marker `[n]` matches a citation object
   - All chunk IDs exist in a registry (citation allowlist from retrieval)
   - If validation fails, retry agent up to 2 times
   - If all retries exhaust, return error

6. **Streaming & Persistence**:
   - Stream response as AI SDK-compatible SSE: `0:"token"` for text, `d:{...}` for data (citations)
   - Frontend consumes stream, renders tokens + citations in real-time
   - Once response completes, persist assistant message + citations to `chat_messages` and `message_citations` tables

**Why this architecture?**
- **Hybrid search** handles both semantic (understanding intent) and keyword (specific metrics) queries
- **Validation** enforces groundedness—every claim must cite a source
- **Streaming** gives users immediate feedback while generation completes
- **RLS** isolates user data at the DB layer
- **SSE format** enables real-time token streaming with citation metadata

**Trade-offs:**
- We don't use semantic caching (yet), so identical questions re-embed + re-retrieve
- No document versioning—updates require re-indexing the corpus
- Citation allowlist is turn-scoped (not persistent), preventing off-registry citations but limiting agent flexibility
- Validation retries can be slow if agent outputs malformed JSON repeatedly

**Key metrics to monitor:**
- Validation failure rate (% of agent outputs that fail 6-stage check)
- Retrieval latency (embedding + search + fusion)
- Agent tool call count (how many tools per turn?)
- Citation-to-answer ratio (is agent citing everything?)

---

## 9. Files Cross-Reference Index

### Backend

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app, auth endpoints, CORS, startup hooks |
| `backend/app/config.py` | Settings from environment (Supabase, OpenAI, JWT secret) |
| `backend/app/api/chat.py` | Chat endpoints: list threads, create thread, stream response, get detail |
| `backend/app/api/documents.py` | Chunk context endpoint (prev/next neighbors) |
| `backend/app/auth/password.py` | Password hashing (bcrypt) and verification |
| `backend/app/auth/schemas.py` | Pydantic models for auth requests |
| `backend/app/auth/dependencies.py` | Auth dependency for DI (get_current_user) |
| `backend/app/database/__init__.py` | DB session creation, connection pool |
| `backend/app/database/supabase.py` | Supabase-specific DB setup |
| `backend/app/database/models/*.py` | SQLAlchemy ORM models (User, ChatThread, DocumentChunk, etc.) |
| `backend/app/database/documents.py` | Query helpers (fetch_chunk_by_id, fetch_neighboring_chunks) |
| `backend/app/chat/orchestrator.py` | run_turn(): agent orchestration, validation, streaming, persistence |
| `backend/app/chat/streaming.py` | SSE event formatters (text_event, data_event, citation_data_event) |
| `backend/app/assistant/agent.py` | PydanticAI Agent definition + tools (search_filings, read_chunk, etc.) |
| `backend/app/assistant/instructions.md` | System prompt for agent (tells it how to reason) |
| `backend/app/assistant/outputs.py` | Pydantic models for agent output (GroundedAnswer, Citation) |
| `backend/app/assistant/deps.py` | Dependencies for agent tools (DocumentAgentDeps, TurnRegistry) |
| `backend/app/assistant/progress.py` | Status/progress callbacks |
| `backend/app/retrieval/retriever.py` | DocumentRetriever: orchestrates hybrid search |
| `backend/app/retrieval/queries.py` | Raw SQL: semantic_search, fulltext_search |
| `backend/app/retrieval/fusion.py` | Reciprocal Rank Fusion (RRF) implementation |
| `backend/app/grounding/validator.py` | GroundingValidator: 6-stage citation validation |
| `backend/app/utils/tokens.py` | Token counting (via tiktoken) |
| `backend/alembic/env.py` | Alembic configuration |
| `backend/alembic/versions/001_initial_schema.py` | Create tables, indexes, RLS policies |
| `backend/alembic/versions/002_add_password_column.py` | Add password_hash column to users |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/src/pages/Chat.tsx` | Main chat page: message list, input, streaming logic |
| `frontend/src/pages/SignIn.tsx` | Login/register form |
| `frontend/src/lib/chat.ts` | streamChat(): fetch SSE, parse AI SDK events |
| `frontend/src/lib/api.ts` | API client: getThread, listThreads, createThread |
| `frontend/src/lib/auth.ts` | Auth helpers (token validation, logout) |
| `frontend/src/lib/auth-context.tsx` | React context for authenticated user state |
| `frontend/src/components/Sidebar.tsx` | Thread list, new chat button, thread navigation |
| `frontend/src/components/ProtectedRoute.tsx` | Route guard for authenticated pages |
| `frontend/src/components/chat/MessageList.tsx` | Renders user + assistant messages |
| `frontend/src/components/chat/MessageBubble.tsx` | Individual message bubble |
| `frontend/src/components/chat/AssistantMessage.tsx` | Assistant message with markdown rendering |
| `frontend/src/components/chat/CitationMarker.tsx` | `[n]` citation marker in text |
| `frontend/src/components/chat/CitationChip.tsx` | Clickable citation chip (ticker, filing type) |
| `frontend/src/components/chat/SourcePassageSheet.tsx` | Detail view: full chunk + context (prev/next) |
| `frontend/src/components/chat/ChatInput.tsx` | Text input, send button, cancel |
| `frontend/src/components/chat/ProcessingProgress.tsx` | Spinner + "typing..." indicator |
| `frontend/src/components/chat/PipelineStatus.tsx` | Pipeline status messages (e.g., "searching..." ) |
| `frontend/src/App.tsx` | Root React component, router setup |
| `frontend/src/main.tsx` | App entry point, React DOM render |

---

## 10. Quick Reference: Key Classes & Data Structures

### Backend Models

```python
# User
User(id: UUID, email: str, password_hash: str?, created_at: datetime)

# Documents
SourceDocument(id: UUID, ticker: str, filing_type: str, filing_year: int, filing_date: datetime, url: str, created_at: datetime)
DocumentChunk(id: UUID, document_id: UUID, text: str, embedding: Vector(1536), chunk_metadata: JSON?, search_vector: str, created_at: datetime)

# Chat
ChatThread(id: UUID, user_id: UUID, title: str?, created_at: datetime, updated_at: datetime)
ChatMessage(id: UUID, thread_id: UUID, role: str, content: str, created_at: datetime)
MessageCitation(id: UUID, message_id: UUID, chunk_id: UUID, page_number: int?, section: str?, created_at: datetime)

# Agent Output
Citation(citation_index: int, chunk_id: UUID, excerpt: str)
GroundedAnswer(answer: str, citations: list[Citation], insufficient_evidence: bool)

# Retrieval
RetrievedPassage(chunk_id: str, document_id: str, text: str, ticker: str, filing_type: str, filing_year: int, heading: str?, chunk_index: int, rrf_score: float, is_neighbor: bool)
```

### Key Functions

```python
# Auth
hash_password(password: str) → str
verify_password(password: str, hash: str) → bool
get_current_user(request: Request, db: Session) → User

# Chat
run_turn(user_message: str, thread: ChatThread, user: User, db: Session, retriever: DocumentRetriever, openai_client: OpenAI) → AsyncGenerator[str, None]

# Retrieval
DocumentRetriever.retrieve(query: str, db: Session, top_k: int = 3, neighbor_window: int = 0) → list[RetrievedPassage]
semantic_search(db: Session, query_embedding: list[float], top_k: int = 20) → list[ChunkRow]
fulltext_search(db: Session, query_text: str, top_k: int = 20) → list[ChunkRow]
reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) → list[tuple[str, float]]

# Validation
GroundingValidator.validate(answer: GroundedAnswer, registry: TurnRegistry) → ValidationResult

# SSE Streaming
text_event(token: str) → str
data_event(payload: dict) → str
citation_data_event(citation: Citation, passage: RetrievedPassage) → str
```

---

## 11. Summary

This system is a **production-ready RAG pipeline** for financial document analysis. It:

✅ **Authenticates users** with email/password + JWT cookies
✅ **Stores documents** with embeddings in Postgres + pgvector
✅ **Retrieves relevant passages** via hybrid (semantic + keyword) search
✅ **Reasons with an LLM** using tool-calling to refine searches
✅ **Validates citations** to ensure claims are grounded in source material
✅ **Streams responses** in real-time with AI SDK-compatible SSE
✅ **Persists conversations** with citations for audit trail
✅ **Isolates user data** via RLS at the database layer

The architecture balances **speed** (streaming tokens immediately), **accuracy** (multi-stage citation validation), and **auditability** (persistent citations linking answers to source passages).

---

**End of System Architecture Walkthrough**
