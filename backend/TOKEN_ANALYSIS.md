# Token Usage Analysis & Optimization Plan

## Issue
Simple query "hello test" consuming ~13,000 tokens, hitting OpenAI rate limit (30K TPM).

## Investigation Steps Added

### 1. Token Counting Utilities
- Created `app/utils/tokens.py` with token counting for GPT-4o
- Added logging of token breakdown at each pipeline step

### 2. Logging Integration Points
- **Startup**: System instruction token count logged when agent loads
- **User message**: User input token count logged
- **Retrieval**: Per-passage token count + total retrieved tokens logged
- **Search tool**: Formatted result token count logged
- **Orchestrator**: Overall turn execution with token visibility

### 3. Hypothesized Token Consumers

#### A. System Instructions (~500-1000 tokens)
- Core rules, citation discipline, constraints
- Response format examples
- Tools documentation
- Corpus metadata

#### B. Retrieved Passages (~5000-10000 tokens)
**Most likely culprit:**
- Retrieving top 10 semantic + top 10 fulltext = 20 base chunks
- Adding neighbors: `neighbor_window=1` per chunk = 2 additional chunks each
- Worst case: 10 × 3 passages = 30 passages
- If avg passage = 300-500 tokens: 9,000-15,000 tokens

#### C. Conversation History (~0 tokens)
- First turn, so no history yet

#### D. User Message (~5 tokens)
- "hello test" = negligible

## Root Cause: Excessive Retrieval Context

**Issue**: `retrieve()` is fetching ~20-30 chunks per query to provide context.

Current defaults:
```python
def retrieve(
    query: str,
    db: Session,
    top_k: int = 10,           # Top results to return
    neighbor_window: int = 1,  # Additional neighbors ±1 per result
):
```

**Math**: 10 results × 3 chunks/result (center + ±1 neighbor) = 30 chunks

## Recommendations

### Immediate: Reduce Retrieved Context
1. **Reduce `top_k` from 10 → 3-5**
   - Target: Top 3-5 most relevant chunks
   - Impact: 70-90% token reduction

2. **Disable neighbor expansion for RAG**
   - Set `neighbor_window=0` by default
   - Rationale: The retriever already returns full passages; neighbors are redundant context
   - Impact: 60-70% token reduction

3. **Limit passage length in search results**
   - Truncate passages to first 200-300 characters
   - Include metadata (source, year) for citation
   - Full text only loaded on explicit `read_chunk()` call

### Short-term: Optimize Prompt Design
1. **Reduce system instructions**
   - Move examples to a separate "few-shot" section that's only included for ambiguous queries
   - Keep core rules, remove redundancy

2. **Remove duplicate information from formatted results**
   - Current: `[i] ticker filing_type year \n Section: X \n Chunk ID: Y \n Text: Z`
   - Optimized: `[i] {ticker} {year} {filing_type}: {text}` (single line)

### Long-term: Architecture
1. **Implement context-aware retrieval**
   - Return snippet (200 chars) in tool output
   - Use `read_chunk()` for full text if needed
   - Reduces bloat while preserving citation capability

2. **Add query complexity detection**
   - Simple queries (one fact): retrieve 1-2 chunks
   - Complex queries (multi-fact): retrieve 5-10 chunks
   - Prediction queries: no retrieval + insufficient_evidence flag

3. **Implement token budgets**
   - Reserve 1,000 tokens for response
   - Reserve 500 tokens for system prompt
   - Use remaining 10,500 for retrieved context (for 30K TPM limit)
   - Dynamically truncate passages if over budget

## Recommended First Action

**Change default parameters:**

```python
# In retriever.retrieve()
def retrieve(
    self,
    query: str,
    db: Session,
    top_k: int = 3,             # Reduced from 10
    neighbor_window: int = 0,   # Disabled (was 1)
) -> list[RetrievedPassage]:
```

**Expected impact**: 13,000 tokens → ~2,000-3,000 tokens (80% reduction)

## Verification
After logging is enabled, run "hello test" query and check logs:
- `[AGENT] System instructions: X tokens`
- `[RETRIEVAL] Retrieved N passages (X tokens total)`
- `[SEARCH_FILINGS] Returning N passages (X tokens)`
- `[TURN] User message: X tokens`

**Total should be: instructions + retrieval + user < 3,000 tokens**
