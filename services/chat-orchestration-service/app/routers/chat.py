"""Chat router — /api/v1/chat/sessions and /api/v1/chat/sessions/{id}/messages."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..events import emit_commitment_tag_suggested
from ..llm import chat_completion, is_commitment_candidate
from ..models import Conversation, Message
from ..schemas import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    PersonaBindRequest,
)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    body: ConversationCreate,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conv = Conversation(
        user_id=user_id,
        persona_id=body.persona_id,
        rag_collection=body.rag_collection,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/sessions/{session_id}", response_model=ConversationResponse)
def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conv = db.get(Conversation, session_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return conv


@router.patch("/sessions/{session_id}/persona", response_model=ConversationResponse)
def bind_persona(
    session_id: str,
    body: PersonaBindRequest,
    db: Session = Depends(get_db),
) -> Conversation:
    """Bind a persona to an existing session (called by persona-prompt-service on 'Select Mentor').

    No user-auth header required — this is an internal service-to-service call
    routed inside the private network (ADR-0001 §D5).
    """
    conv = db.get(Conversation, session_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    conv.persona_id = body.persona_id
    db.commit()
    db.refresh(conv)
    return conv


# ── Messages ──────────────────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: str,
    body: MessageCreate,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    conv = db.get(Conversation, session_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if conv.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")

    # Persist the user turn
    next_seq = len(conv.messages)
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=body.content,
        sequence=next_seq,
    )
    db.add(user_msg)
    db.flush()

    # Call LLM (with RAG retrieval)
    reply_text, prompt_tokens, completion_tokens, citations = await chat_completion(
        history=conv.messages,
        user_content=body.content,
        persona_id=conv.persona_id,
        rag_collection=conv.rag_collection,
    )

    # Detect commitment from the user message — the commitment is expressed
    # by the user, not the assistant. Chioma echoes it in third person which
    # never matches user-voiced keywords. Sprint 4 replaces this with a
    # structured LLM output field.
    candidate = is_commitment_candidate(body.content)
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=reply_text,
        sequence=next_seq + 1,
        is_commitment_candidate=int(candidate),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        citations=citations,
    )
    db.add(assistant_msg)

    # Update conversation token totals
    conv.total_prompt_tokens += prompt_tokens
    conv.total_completion_tokens += completion_tokens

    db.commit()
    db.refresh(assistant_msg)

    # Emit domain event if the reply is a commitment candidate
    if candidate:
        emit_commitment_tag_suggested(
            conversation_id=conv.id,
            message_id=assistant_msg.id,
            user_id=user_id,
            content=reply_text,
        )

    return assistant_msg


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    conv = db.get(Conversation, session_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return conv.messages
