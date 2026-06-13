import asyncio
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.database.models.chat import ChatMessage, ChatThread
from app.database.models.users import User

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
    thread_id: UUID
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
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = get_thread_for_user(request.thread_id, user, db)

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
        stub = "This is a stubbed assistant reply."
        full_text = []
        for word in stub.split():
            chunk = word + " "
            full_text.append(chunk)
            yield f"data: {chunk}\n\n"
            await asyncio.sleep(0.05)

        full_response = "".join(full_text).strip()
        db.add(
            ChatMessage(
                thread_id=thread.id,
                role="assistant",
                content=full_response,
            )
        )
        thread.updated_at = datetime.utcnow()
        db.commit()

    from fastapi.responses import StreamingResponse

    return StreamingResponse(token_generator(), media_type="text/event-stream")
