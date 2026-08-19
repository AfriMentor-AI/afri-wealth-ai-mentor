"""LLM message assembler for chat-orchestration-service.

Builds the messages list sent to the OpenAI-compatible API.
"""
from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator

import httpx
from openai import AsyncOpenAI

from .config import get_settings
from .models import Message
from .rag import RagResult, retrieve

logger = logging.getLogger(__name__)
settings = get_settings()

_client: AsyncOpenAI | None = None
_persona_http_client: httpx.AsyncClient | None = None
_prompt_cache: dict[tuple[str, str], tuple[float, str]] = {}


def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key or "no-key",
            base_url=settings.llm_base_url,
        )
    return _client


# ── System prompt ─────────────────────────────────────────────────────────────

async def _get_system_prompt(persona_id: str | None) -> str:
    """Fetch the rendered system prompt from persona-prompt-service.

    Falls back to the hardcoded Chioma base prompt when PERSONA_SERVICE_URL
    is not configured (dev / test without Docker).
    """
    _FALLBACK = (
        "You are Chioma, a warm and direct African financial mentor. "
        "You give practical, actionable advice grounded in African business realities. "
        "When a user expresses a clear financial commitment or goal, acknowledge it "
        "explicitly so they feel accountable."
    )
    if not settings.persona_service_url or not persona_id:
        return _FALLBACK
    cache_key = (settings.persona_service_url, persona_id)
    cached = _prompt_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < settings.cache_ttl_seconds:
        return cached[1]
    try:
        global _persona_http_client
        if _persona_http_client is None:
            _persona_http_client = httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=0.3))
        resp = await _persona_http_client.get(
            f"{settings.persona_service_url}/api/v1/personas/{persona_id}/prompt",
        )
        resp.raise_for_status()
        prompt = resp.json()["system_prompt"]
        if len(_prompt_cache) >= settings.cache_max_entries:
            _prompt_cache.pop(next(iter(_prompt_cache)))
        _prompt_cache[cache_key] = (time.monotonic(), prompt)
        return prompt
    except Exception:
        logger.warning("persona-prompt-service unavailable — using fallback prompt")
        return _FALLBACK


# ── RAG context injection ─────────────────────────────────────────────────────

def _build_rag_system_message(chunks: list[RagResult]) -> str:
    """Format retrieved chunks into the context-injection system message.

    Each chunk is prefixed with its source label so the LLM can attribute
    claims. The template is intentionally terse to stay within the 512-token
    LLM_MAX_TOKENS budget.
    """
    lines = ["Use the following knowledge to inform your response:"]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] ({chunk.source_label}) {chunk.content}")
    return "\n".join(lines)


def _deduplicate_labels(chunks: list[RagResult]) -> list[str]:
    """Return unique source labels in retrieval-rank order."""
    seen: set[str] = set()
    labels: list[str] = []
    for chunk in chunks:
        if chunk.source_label not in seen:
            seen.add(chunk.source_label)
            labels.append(chunk.source_label)
    return labels


# ── Commitment detection ──────────────────────────────────────────────────────

def is_commitment_candidate(text: str) -> bool:
    """Heuristic: does the text contain a user-voiced commitment phrase?

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
) -> tuple[str, int, int, list[dict]]:
    """Assemble context and call the LLM.

    Returns (reply_text, prompt_tokens, completion_tokens, citations).
    ``citations`` is a list of {"label": str} dicts ready for the source-pill
    renderer; it is empty when no RAG chunks were retrieved.
    Falls back to a stub reply when LLM_API_KEY is not configured.
    """
    system_prompt = await _get_system_prompt(persona_id)
    chunks = await retrieve(user_content, collection=rag_collection)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if chunks:
        messages.append({
            "role": "system",
            "content": _build_rag_system_message(chunks),
        })

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_content})

    citations = [{"label": label} for label in _deduplicate_labels(chunks)]

    if not settings.llm_api_key:
        logger.debug("LLM_API_KEY not set — returning stub reply")
        stub = (
            "I hear you! Let's work through this together. "
            "(LLM stub — set LLM_API_KEY to enable real responses.)"
        )
        return stub, len(messages) * 10, 20, citations

    client = get_llm_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
    except Exception as exc:  # pragma: no cover - exercised via integration tests with bad creds
        logger.warning("LLM request failed; falling back to stub reply: %s", exc)
        return (
            "I hear you! Let's work through this together. "
            "(LLM unavailable — using safe fallback response.)",
            len(messages) * 10,
            20,
            citations,
        )

    choice = response.choices[0]
    usage = response.usage
    return (
        choice.message.content or "",
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
        citations,
    )


async def stream_chat_completion(
    *,
    history: list[Message],
    user_content: str,
    persona_id: str | None,
    rag_collection: str | None,
) -> tuple[AsyncIterator[str], list[dict]]:
    """Prepare a provider token stream and return it with its RAG citations."""
    system_prompt = await _get_system_prompt(persona_id)
    chunks = await retrieve(user_content, collection=rag_collection)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if chunks:
        messages.append({"role": "system", "content": _build_rag_system_message(chunks)})
    messages.extend({"role": msg.role, "content": msg.content} for msg in history)
    messages.append({"role": "user", "content": user_content})
    citations = [{"label": label} for label in _deduplicate_labels(chunks)]

    async def fallback() -> AsyncIterator[str]:
        yield (
            "I hear you! Let's work through this together. "
            "(LLM stub — set LLM_API_KEY to enable real responses.)"
        )

    if not settings.llm_api_key or not settings.llm_streaming_enabled:
        return fallback(), citations

    client = get_llm_client()

    async def provider_stream() -> AsyncIterator[str]:
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                stream=True,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:  # pragma: no cover - provider failures need integration coverage
            logger.warning("LLM stream failed; using fallback response: %s", exc)
            yield "I hear you! Let's work through this together. (LLM unavailable.)"

    return provider_stream(), citations


async def generate_daily_action_for_user(user_id: str, db) -> str:
    """
    Generates a personalized daily action for a user.
    """
    logger.info(f"Generating daily action for user {user_id}...")

    # TODO: Replace this placeholder with an actual HTTP request to the goals-milestones-service
    # 1. Fetch user's active goals from the goals-milestones-service
    #    (This is a placeholder, actual implementation will make an HTTP request)
    active_goals = ["Save money for a new car", "Invest in the stock market"]
    logger.info(f"User {user_id} has active goals: {active_goals}")

    # 2. Construct the prompt
    prompt = (
        "You are Chioma, a warm and direct African financial mentor. "
        "Your task is to generate a single, specific, and actionable financial task "
        "for a user based on their goals. "
        "The task should be something they can do today. "
        "Here are the user's active goals:\n"
        "\n".join(f"- {goal}" for goal in active_goals) +
        "\n\n"
        "Generate a single, specific, and actionable financial task for the user."
        "The response should be just the task itself, without any preamble."
        "For example: 'Set aside 10% of your income for savings today.'"
    )

    messages = [{"role": "system", "content": prompt}]

    # 3. Call the LLM
    if not settings.llm_api_key:
        logger.debug("LLM_API_KEY not set — returning stub reply")
        stub = "Set aside 10% of your income for savings today. (LLM stub)"
        return stub

    client = get_llm_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=100,
            temperature=settings.llm_temperature,
        )
    except Exception as exc:  # pragma: no cover - provider-auth errors are handled here
        logger.warning("Daily action LLM request failed; using fallback action: %s", exc)
        return "Set aside 10% of your income for savings today. (LLM fallback)"

    choice = response.choices[0]
    return choice.message.content or ""

