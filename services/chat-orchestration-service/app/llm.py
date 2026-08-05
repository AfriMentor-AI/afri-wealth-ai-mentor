"""LLM message assembler for chat-orchestration-service.

Builds the messages list sent to the OpenAI-compatible API.

Extension points (marked with TODO Sprint tags) are where persona-prompt-service
and rag-corpus-service will be plugged in during Sprints 2–3.
"""
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from .config import get_settings
from .models import Message

logger = logging.getLogger(__name__)
settings = get_settings()

_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key or "no-key",
            base_url=settings.llm_base_url,
        )
    return _client


# ── Extension point stubs ─────────────────────────────────────────────────────

def _get_system_prompt(persona_id: str | None) -> str:
    """TODO Sprint 2 — call persona-prompt-service to fetch the rendered system prompt.

    Until then, return a generic mentor prompt so the service is functional.
    """
    return (
        "You are Chioma, a warm and direct African financial mentor. "
        "You give practical, actionable advice grounded in African business realities. "
        "When a user expresses a clear financial commitment or goal, acknowledge it "
        "explicitly so they feel accountable."
    )


def _get_rag_context(rag_collection: str | None, query: str) -> str:
    """TODO Sprint 3 — call rag-corpus-service to retrieve relevant passages.

    Returns an empty string until the RAG service is integrated.
    """
    return ""


# ── Commitment detection ──────────────────────────────────────────────────────

def is_commitment_candidate(text: str) -> bool:
    """Heuristic: does the assistant reply contain a user-voiced commitment phrase?

    Sprint 4 — replace with a dedicated classifier or structured LLM output field.
    """
    lower = text.lower()
    return any(kw in lower for kw in settings.commitment_keywords)


# ── Message assembly & LLM call ───────────────────────────────────────────────

async def chat_completion(
    *,
    history: list[Message],
    user_content: str,
    persona_id: str | None,
    rag_collection: str | None,
) -> tuple[str, int, int]:
    """Assemble context and call the LLM.

    Returns (reply_text, prompt_tokens, completion_tokens).
    Falls back to a stub reply when LLM_API_KEY is not configured.
    """
    system_prompt = _get_system_prompt(persona_id)
    rag_context = _get_rag_context(rag_collection, user_content)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if rag_context:
        messages.append({
            "role": "system",
            "content": f"Relevant knowledge:\n{rag_context}",
        })

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_content})

    if not settings.llm_api_key:
        logger.debug("LLM_API_KEY not set — returning stub reply")
        stub = (
            "I hear you! Let's work through this together. "
            "(LLM stub — set LLM_API_KEY to enable real responses.)"
        )
        return stub, len(messages) * 10, 20  # fake token counts

    client = get_llm_client()
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )
    choice = response.choices[0]
    usage = response.usage
    return (
        choice.message.content or "",
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
    )
