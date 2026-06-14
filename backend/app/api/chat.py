import asyncio
import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.database.models.chat import ChatMessage, ChatThread
from app.database.models.users import User
from app.chat.orchestrator import run_turn

log = logging.getLogger(__name__)

router = APIRouter()


class ThreadOut(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class CreateThreadRequest(BaseModel):
    title: str | None = None


class ChatRequest(BaseModel):
    id: UUID
    messages: list[dict]


def get_thread_for_user(
    thread_id: UUID, user: User, db: Session
) -> ChatThread:
    thread = db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return thread


def get_current_user_from_cookies(request: Request, db: Session) -> User:
    """Extract current user from HttpOnly cookie only (Phase 3: no Authorization header fallback).

    This is the chat-specific auth handler that enforces cookie-based auth.
    The general get_current_user still supports Authorization headers for backward compatibility.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    import jwt
    from app.config import settings

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


@router.get("/threads", response_model=list[ThreadOut])
async def list_threads(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    threads = (
        db.query(ChatThread)
        .filter(ChatThread.user_id == user.id)
        .order_by(ChatThread.updated_at.desc())
        .all()
    )
    return threads


@router.post("/threads", response_model=ThreadOut)
async def create_thread(
    request: CreateThreadRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = ChatThread(user_id=user.id, title=request.title)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/threads/{thread_id}/messages", response_model=list[MessageOut])
async def get_messages(
    thread_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = get_thread_for_user(thread_id, user, db)
    messages = (
        db.query(ChatMessage)
        .filter_by(thread_id=thread.id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return messages


@router.post("/stream")
async def stream_chat(
    http_request: Request,
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """Stream assistant response in AI SDK-compatible format.

    Authentication: HttpOnly cookie only (Phase 3 enforcement).
    Streaming format: AI SDK-compatible Server-Sent Events.

    Message format:
    - Text tokens: 0:"<token>"
    - Data parts (citations): d:{json}
    - Errors: e:"<error>"

    See: https://sdk.vercel.ai/docs/concepts/streaming
    """
    user = get_current_user_from_cookies(http_request, db)
    thread = get_thread_for_user(request.id, user, db)

    user_message = None
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            user_message = msg.get("content")
            break

    if not user_message:
        raise HTTPException(
            status_code=400, detail="No user message in request"
        )

    db.add(
        ChatMessage(
            thread_id=thread.id, role="user", content=user_message
        )
    )
    db.commit()

    async def token_generator():
        log.info(f"[STREAM] Starting token generator")
        retriever = http_request.app.state.retriever
        openai_client = http_request.app.state.openai_client
        log.info(f"[STREAM] Got retriever and openai_client")
        async for event in run_turn(user_message, thread, user, db, retriever, openai_client):
            log.info(f"[STREAM] Yielding event: {event[:50] if len(event) > 50 else event}")
            yield event
        log.info(f"[STREAM] Token generator finished")

    from fastapi.responses import StreamingResponse

    return StreamingResponse(token_generator(), media_type="text/event-stream")
