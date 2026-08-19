"""Chat router — /api/v1/chat/sessions and /api/v1/chat/sessions/{id}/messages."""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user
from ..events import emit_commitment_created, emit_commitment_tag_suggested
from ..guardrails import (
    ALLOWED,
    GuardrailAction,
    apply_disclaimer,
    most_severe,
    refusal_message,
    screen_input,
    screen_output,
)
from ..llm import chat_completion, is_commitment_candidate, stream_chat_completion
from ..models import Conversation, Message
from ..schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    MessageCreate,
    MessageResponse,
    PersonaBindRequest,
    TagItRequest,
    TagItResponse,
)

logger = logging.getLogger(__name__)

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


@router.get("/sessions", response_model=list[ConversationSummary])
def list_sessions(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationSummary]:
    """Multi-mentor conversation list — one row per session the user has ever
    started (with any persona), newest activity first. Powers the desktop/
    mobile conversation-list UI; each conversation may be with a different
    persona (Conversation.persona_id already supports this — no schema
    change needed, a user was never restricted to one concurrent session)."""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    summaries: list[ConversationSummary] = []
    for conv in convs:
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.sequence.desc())
            .first()
        )
        summaries.append(
            ConversationSummary(
                id=conv.id,
                persona_id=conv.persona_id,
                last_message_preview=last_message.content[:140] if last_message else None,
                last_message_at=last_message.created_at if last_message else None,
                updated_at=conv.updated_at,
            )
        )
    return summaries


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
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    """Bind a persona to an existing session (called by persona-prompt-service on 'Select Mentor').

    Card O3.5: this used to skip the ownership check on the theory that it's an
    internal service-to-service call — but persona-prompt-service's
    `POST /personas/{id}/select` (the only caller) is itself reachable through the
    gateway's protected `/api/v1/personas` prefix with a caller-supplied
    `session_id`, so without this check any authenticated user could rebind
    another user's chat session to an arbitrary persona.
    """
    conv = db.get(Conversation, session_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    conv.persona_id = body.persona_id
    db.commit()
    db.refresh(conv)
    return conv


# ── Messages ──────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/messages/stream")
async def stream_message(
    session_id: str,
    body: MessageCreate,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream model tokens as SSE and persist the completed assistant turn.

    The existing JSON endpoint remains available for non-streaming clients. SSE
    keeps time-to-first-token independent of the model's total completion time.
    """
    conv = db.get(Conversation, session_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if conv.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")

    next_seq = len(conv.messages)
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=body.content,
        sequence=next_seq,
    )
    db.add(user_msg)
    db.flush()
    guardrails_on = get_settings().guardrails_enabled
    input_decision = screen_input(body.content) if guardrails_on else ALLOWED

    async def events():
        if input_decision.blocked:
            reply_text = refusal_message(input_decision)
            citations: list[dict] = []
            prompt_tokens = completion_tokens = 0
            decision = input_decision
            candidate = False
            yield f"event: token\ndata: {json.dumps({'text': reply_text})}\n\n"
        else:
            stream, citations = await stream_chat_completion(
                history=conv.messages,
                user_content=body.content,
                persona_id=conv.persona_id,
                rag_collection=conv.rag_collection,
            )
            parts: list[str] = []
            async for token in stream:
                parts.append(token)
                partial_decision = screen_output("".join(parts)) if guardrails_on else ALLOWED
                if partial_decision.blocked:
                    break
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"

            reply_text = "".join(parts)
            output_decision = screen_output(reply_text) if guardrails_on else ALLOWED
            if output_decision.blocked:
                reply_text = refusal_message(output_decision)
                citations = []
            else:
                reply_text = apply_disclaimer(reply_text, output_decision)
            decision = most_severe(input_decision, output_decision)
            if decision.action is GuardrailAction.disclaim:
                reply_text = apply_disclaimer(reply_text, decision)
            candidate = is_commitment_candidate(body.content) and not decision.blocked
            prompt_tokens = completion_tokens = 0

        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=reply_text,
            sequence=next_seq + 1,
            is_commitment_candidate=int(candidate),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            citations=citations,
            guardrail_action=decision.action.value if guardrails_on else None,
            guardrail_categories=list(decision.categories),
        )
        db.add(assistant_msg)
        conv.total_prompt_tokens += prompt_tokens
        conv.total_completion_tokens += completion_tokens
        db.commit()
        db.refresh(assistant_msg)
        if candidate:
            emit_commitment_tag_suggested(
                conversation_id=conv.id,
                message_id=assistant_msg.id,
                user_id=user_id,
                content=reply_text,
            )
        yield "event: complete\ndata: " + json.dumps({
            "id": assistant_msg.id,
            "content": reply_text,
            "citations": citations,
            "guardrail_action": decision.action.value if guardrails_on else None,
        }) + "\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

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

    guardrails_on = get_settings().guardrails_enabled

    # Pre-hook (card C2.4): screen the user's message before anything expensive.
    # A block here means the query never reaches the RAG corpus or the LLM, which
    # is what "blocks retrieval of high-risk advice" requires — cheaper than
    # generating a reply and discarding it, and it leaves no unsafe text to leak.
    input_decision = screen_input(body.content) if guardrails_on else ALLOWED

    if input_decision.blocked:
        logger.warning(
            "guardrail blocked user input: conversation=%s categories=%s",
            conv.id,
            list(input_decision.categories),
        )
        reply_text = refusal_message(input_decision)
        prompt_tokens = completion_tokens = 0
        citations: list = []
        decision = input_decision
        # A refused turn must never become a tracked goal, even if the user
        # phrased it as a commitment ("I will put my savings into crypto").
        candidate = False
    else:
        # Call LLM (with RAG retrieval)
        reply_text, prompt_tokens, completion_tokens, citations = await chat_completion(
            history=conv.messages,
            user_content=body.content,
            persona_id=conv.persona_id,
            rag_collection=conv.rag_collection,
        )

        # Post-hook: screen the reply. Catches the model volunteering a specific
        # instrument in answer to an innocuous question — invisible to the pre-hook.
        output_decision = screen_output(reply_text) if guardrails_on else ALLOWED
        if output_decision.blocked:
            logger.warning(
                "guardrail blocked model output: conversation=%s categories=%s",
                conv.id,
                list(output_decision.categories),
            )
            reply_text = refusal_message(output_decision)
            citations = []
        else:
            reply_text = apply_disclaimer(reply_text, output_decision)

        # Input severity is considered too: a disclaim-tier input (general
        # investment talk) still earns a disclaimer when the reply itself reads clean.
        decision = most_severe(input_decision, output_decision)
        if decision.action is GuardrailAction.disclaim:
            reply_text = apply_disclaimer(reply_text, decision)

        # Detect commitment from the user message — the commitment is expressed
        # by the user, not the assistant. Chioma echoes it in third person which
        # never matches user-voiced keywords. Sprint 4 replaces this with a
        # structured LLM output field.
        candidate = is_commitment_candidate(body.content) and not decision.blocked

    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=reply_text,
        sequence=next_seq + 1,
        is_commitment_candidate=int(candidate),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        citations=citations,
        guardrail_action=decision.action.value if guardrails_on else None,
        guardrail_categories=list(decision.categories),
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


# ── Tag It (D2.3) ───────────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/messages/{message_id}/tag",
    response_model=TagItResponse,
    status_code=status.HTTP_201_CREATED,
)
def tag_commitment(
    session_id: str,
    message_id: str,
    body: TagItRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagItResponse:
    """Confirm 'Yes, Tag It' — persists the commitment to goals-milestones-service
    and emits commitment.created.

    The frontend calls this when the user taps 'Yes, Tag It' on a commitment
    suggestion in chat. body.goal_id is the active goal from the Goal Milestone
    Path screen.
    """
    conv = db.get(Conversation, session_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msg = db.get(Message, message_id)
    if not msg or msg.conversation_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if not msg.is_commitment_candidate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message is not a commitment candidate",
        )

    cfg = get_settings()
    url = f"{cfg.goals_service_url}/api/v1/goals/{body.goal_id}/commitments"
    try:
        resp = httpx.post(
            url,
            json={
                "user_id": user_id,
                "conversation_id": session_id,
                "message_id": message_id,
                "content": msg.content,
            },
            timeout=5.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Goals service error: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Goals service unreachable: {exc}",
        ) from exc

    commitment = resp.json()
    emit_commitment_created(
        commitment_id=commitment["id"],
        goal_id=body.goal_id,
        user_id=user_id,
        conversation_id=session_id,
        message_id=message_id,
        content_preview=msg.content,
    )

    return TagItResponse(
        commitment_id=commitment["id"],
        goal_id=body.goal_id,
        message_id=message_id,
    )
