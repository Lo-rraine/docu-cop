"""Token counting utilities for monitoring prompt size."""

import logging
import tiktoken

log = logging.getLogger(__name__)

# Cache encoding for efficiency
_encoding = None

def get_encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.encoding_for_model("gpt-4o")
    return _encoding

def count_tokens(text: str) -> int:
    """Count tokens in a string."""
    if not text:
        return 0
    encoding = get_encoding()
    return len(encoding.encode(text))

def log_token_breakdown(
    system_prompt: str = "",
    retrieved_passages: str = "",
    conversation_history: str = "",
    user_message: str = "",
) -> None:
    """Log detailed token breakdown before model call."""
    system_tokens = count_tokens(system_prompt)
    retrieved_tokens = count_tokens(retrieved_passages)
    history_tokens = count_tokens(conversation_history)
    user_tokens = count_tokens(user_message)
    total = system_tokens + retrieved_tokens + history_tokens + user_tokens

    log.info(f"""
[TOKEN BREAKDOWN]
  System prompt:          {system_tokens:6d} tokens
  Retrieved passages:     {retrieved_tokens:6d} tokens
  Conversation history:   {history_tokens:6d} tokens
  User message:           {user_tokens:6d} tokens
  ────────────────────────────────
  TOTAL:                  {total:6d} tokens
""")

    if total > 10000:
        log.warning(f"[TOKEN WARNING] Total prompt is {total} tokens (should be <5000)")
