"""LLM message assembler for chat-orchestration-service.

Builds the messages list sent to the OpenAI-compatible API.
"""
from __future__ import annotations

import asyncio
import logging
import re
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

# ── Think-tag stripping ───────────────────────────────────────────────────────
# Qwen/Qwen2.5 (and other reasoning models) emit an internal chain-of-thought
# wrapped in <think>…</think> before the actual reply. We strip the entire
# block so it is never stored or returned to clients.
_THINK_RE = re.compile(r"<think>(?:.*?</think>|[\s\S]*$)", re.DOTALL | re.IGNORECASE)
_STRAY_CLOSING_RE = re.compile(r"</think>", re.IGNORECASE)


def _strip_think_tags(text: str) -> str:
    """Remove <think>…</think> reasoning blocks from model output.
    Also handles unclosed <think>... blocks if truncated by max_tokens,
    and removes any stray closing tags."""
    cleaned = _THINK_RE.sub("", text)
    cleaned = _STRAY_CLOSING_RE.sub("", cleaned)
    return cleaned.lstrip("\n")


def _get_extra_body() -> dict | None:
    """On Groq, suppress reasoning tokens natively so the token budget is preserved."""
    if "groq.com" in settings.llm_base_url.lower():
        return {"reasoning_format": "hidden"}
    return None


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

    Falls back to the C4-aligned Chioma system prompt when PERSONA_SERVICE_URL
    is not configured (dev / test without Docker).

    The fallback prompt reflects the Sprint 4 winning alignment condition
    (C4: RLHF / Preference Optimization, composite 0.654). It is calibrated
    against the C4 reward-model's per-dimension weights:
      persona_adherence (0.20), cultural_fluency (0.15), anti_dependency (0.15),
      financial_accuracy (0.15), urgency (0.15), plus qa/line-consistency (0.19).
    Update this string whenever the persona-prompt-service template changes, and
    replace with an adapter-routed call once AfriMentor/chioma-rlhf-v1 is live.
    """
    _FALLBACK = (
        # ── IDENTITY (persona_adherence) ──────────────────────────────────────
        "You are Chioma — an AI financial mentor built for African achievers. "
        "You are not a bank. You are the sharp, warm, "
        "no-nonsense older sister who has seen real African business from the inside "
        "and will not let your user waste their potential. "
        "You were shaped by the realities of Lagos markets, Nairobi tech hubs, "
        "Accra fashion streets, Kampala agri-cooperatives, and Johannesburg creative studios. "
        "You speak the language of hustle, resilience, and compound growth.\n\n"
        # ── AI DISCLOSURE (C2.5 — non-negotiable) ────────────────────────────
        "AI DISCLOSURE: You are an AI. When a user sincerely asks whether they are "
        "talking to a real person, a human, or a bot — in any phrasing — you must "
        "answer honestly and directly before anything else. Do not deflect, reframe, "
        "or answer with only your persona name. A correct answer acknowledges your AI "
        "nature explicitly, e.g.: 'I'm an AI — Chioma is a persona, not a person. "
        "There is no human on this end of the conversation.' You may then continue in "
        "your Chioma voice. This rule overrides persona immersion.\n\n"
        # ── CULTURAL FLUENCY ──────────────────────────────────────────────────
        "CULTURAL FLUENCY: Money in Africa is communal, relational, and often informal. "
        "You never impose Western personal-finance frameworks without adaptation. "
        "You acknowledge family financial obligations, rotating savings groups "
        "(ajo/esusu/chama), mobile money realities, and the trust economics of informal "
        "markets. If the user writes in Pidgin, Yoruba-inflected English, Swahili, or "
        "any regional vernacular, mirror their register naturally.\n\n"
        # ── ANTI-DEPENDENCY ───────────────────────────────────────────────────
        "ANTI-DEPENDENCY: You are building the user's financial thinking, not their "
        "dependence on you. You explain your reasoning. You teach frameworks, not just "
        "answers. You regularly ask 'What do YOU think the next step is?' before "
        "offering your own view. Do not end every reply with 'let me know if you need "
        "anything' — end with a specific next action or a single sharp question.\n\n"
        # ── FINANCIAL ACCURACY ────────────────────────────────────────────────
        "FINANCIAL ACCURACY: Numbers over adjectives. 'Save 20% of daily takings' beats "
        "'save more.' Every plan has concrete steps, deadlines, and tracking metrics. "
        "No jargon without translation — if you use a financial term, define it in the "
        "same sentence using local context.\n\n"
        # ── URGENCY ───────────────────────────────────────────────────────────
        "URGENCY: You treat financial inaction as a cost. Every session, you surface the "
        "price of waiting. Make the abstract concrete and the future feel close — e.g. "
        "'Every week you delay saving ₦5,000 is ₦260,000 you will not have next year.'\n\n"
        # ── RESPONSE RULES ────────────────────────────────────────────────────
        "RESPONSE RULES: "
        "(1) One question at a time — never stack multiple questions in one turn. "
        "(2) Acknowledge before advising — one sentence of recognition, then action. "
        "(3) Commitment detection — when the user states a financial intention "
        "('I will…', 'I plan to…', 'My goal is…'), explicitly name it as a commitment "
        "and confirm it back so they feel the weight of accountability. "
        "(4) Short replies on mobile — default to 3–5 short paragraphs; bullet points "
        "only for step lists; no walls of text. "
        "(5) Direct response only — do not include any <think> tags, internal monologue, "
        "reasoning scratchpad, or planning commentary. "
        "Begin immediately with your response to the user."
        # ── ALIGNMENT PROVENANCE ──────────────────────────────────────────────
        # This prompt embodies Condition C4 (RLHF / Preference Optimization).
        # Live automatic-suite composite: 0.643 (eval-freeze-v2, 2026-09-12).
        # C4 ranks highest in blinded human evaluation (overall quality 3.30/5,
        # top on every individual dimension) despite ranking lowest on the
        # automatic suite — C2 (SFT) leads automatic at 0.753. Human and
        # automatic rankings diverge; see results.tex §4.3 for full discussion.
        # Source: research/evaluation/results/canonical/v2/comparative_results.json
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
            _persona_http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(3.0, connect=0.3),
                limits=httpx.Limits(
                    max_connections=settings.http_pool_max_connections,
                    max_keepalive_connections=settings.http_pool_max_keepalive,
                ),
            )
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
    claims. The template is intentionally terse to keep prompt size down.
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

def is_commitment_candidate(user_text: str, assistant_text: str = "") -> bool:
    """Heuristic: does the user message or Chioma's reply contain a commitment phrase?

    Checks both sides — the user may voice the commitment directly, or Chioma
    (per her system prompt) may name it back to confirm accountability.
    Sprint 4 — replace with a dedicated classifier or structured LLM output field.
    """
    combined = (user_text + " " + assistant_text).lower()
    return any(kw in combined for kw in settings.commitment_keywords)


# ── Thinking tag stripper ─────────────────────────────────────────────────────

def strip_thinking_tags(text: str) -> str:
    """Remove <think>...</think> reasoning traces from model responses."""
    if not text:
        return ""
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


async def filter_thinking_stream(stream: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield tokens from stream while filtering out <think>...</think> blocks in real time."""
    in_think = False
    buffer = ""
    async for token in stream:
        buffer += token
        while buffer:
            if not in_think:
                lower_buf = buffer.lower()
                if "<think>" in lower_buf:
                    idx = lower_buf.index("<think>")
                    prefix = buffer[:idx]
                    if prefix:
                        yield prefix
                    in_think = True
                    buffer = buffer[idx + 7:]
                else:
                    match_partial = False
                    for i in range(1, min(len("<think>"), len(buffer) + 1)):
                        suffix = lower_buf[-i:]
                        if "<think>".startswith(suffix):
                            match_partial = True
                            if len(buffer) > i:
                                yield buffer[:-i]
                                buffer = buffer[-i:]
                            break
                    if not match_partial:
                        yield buffer
                        buffer = ""
                    else:
                        break
            else:
                lower_buf = buffer.lower()
                if "</think>" in lower_buf:
                    idx = lower_buf.index("</think>")
                    in_think = False
                    buffer = buffer[idx + 8:].lstrip("\r\n ")
                else:
                    match_partial = False
                    for i in range(1, min(len("</think>"), len(buffer) + 1)):
                        suffix = lower_buf[-i:]
                        if "</think>".startswith(suffix):
                            buffer = buffer[-i:]
                            match_partial = True
                            break
                    if not match_partial:
                        buffer = ""
                    break

    if buffer and not in_think:
        cleaned = strip_thinking_tags(buffer)
        if cleaned:
            yield cleaned


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
    system_prompt, chunks = await asyncio.gather(
        _get_system_prompt(persona_id),
        retrieve(user_content, collection=rag_collection),
    )

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
            extra_body=_get_extra_body(),
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
    raw_content = choice.message.content or ""
    cleaned_content = _strip_think_tags(raw_content)
    return (
        cleaned_content,
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
    system_prompt, chunks = await asyncio.gather(
        _get_system_prompt(persona_id),
        retrieve(user_content, collection=rag_collection),
    )
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
                extra_body=_get_extra_body(),
            )
            # Buffer tokens to suppress any <think>…</think> reasoning blocks.
            # Reasoning models (e.g. Qwen / DeepSeek) emit thinking content first;
            # we must not yield any of it to SSE clients.
            buffer = ""
            in_think = False
            think_done = False

            async for chunk in response:
                if not (chunk.choices and chunk.choices[0].delta.content):
                    continue
                token = chunk.choices[0].delta.content

                if think_done:
                    yield token
                    continue

                buffer += token

                if not in_think:
                    stripped = buffer.lstrip()
                    lower_stripped = stripped.lower()
                    if not lower_stripped:
                        # Only leading whitespace so far — keep buffering
                        continue
                    if "<think>" in lower_stripped:
                        in_think = True
                    elif any(
                        "<think>".startswith(lower_stripped[:i])
                        for i in range(1, len(lower_stripped) + 1)
                    ):
                        # Matches prefix of "<think>" (e.g. "<", "<th", etc.) — keep buffering
                        continue
                    else:
                        # Definitely not a think block — flush buffer and stream normally
                        think_done = True
                        yield buffer
                        buffer = ""
                        continue

                if in_think:
                    lower_buffer = buffer.lower()
                    if "</think>" in lower_buffer:
                        # Thinking completed — extract any text after </think>
                        close_idx = lower_buffer.find("</think>") + len("</think>")
                        remainder = buffer[close_idx:].lstrip("\n")
                        think_done = True
                        in_think = False
                        buffer = ""
                        if remainder:
                            yield remainder

            # If stream finished without think block, flush any buffered non-think text
            if buffer and not in_think and not think_done:
                yield buffer
        except Exception as exc:  # pragma: no cover - provider failures need integration coverage
            logger.warning("LLM stream failed; using fallback response: %s", exc)
            yield "I hear you! Let's work through this together. (LLM unavailable.)"

    return filter_thinking_stream(provider_stream()), citations


async def generate_daily_action_for_user(user_id: str, db) -> str:
    """
    Generates a personalized daily action for a user.
    """
    logger.info(f"Generating daily action for user {user_id}...")

    active_goals: list[str] = []
    if settings.goals_service_url:
        try:
            global _persona_http_client
            if _persona_http_client is None:
                _persona_http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(5.0, connect=2.0),
                    limits=httpx.Limits(
                        max_connections=settings.http_pool_max_connections,
                        max_keepalive_connections=settings.http_pool_max_keepalive,
                    ),
                )
            resp = await _persona_http_client.get(
                f"{settings.goals_service_url}/api/v1/goals",
                headers={"X-User-Id": user_id},
            )
            resp.raise_for_status()
            active_goals = [g["title"] for g in resp.json() if g.get("status") == "active"]
        except Exception as exc:
            logger.warning("Could not fetch goals for user %s: %s", user_id, exc)

    if not active_goals:
        active_goals = ["build financial stability", "grow savings consistently"]
    logger.info(f"User {user_id} has active goals: {active_goals}")

    # 2. Construct the prompt
    system_prompt = "You are Chioma, a warm and direct African financial mentor."
    user_prompt = (
        "Generate a single, specific, and actionable financial task for a user "
        "based on their goals, something they can do today. Here are the user's "
        "active goals:\n" +
        "\n".join(f"- {goal}" for goal in active_goals) +
        "\n\nRespond with just the task itself, without any preamble. "
        "For example: 'Set aside 10% of your income for savings today.'"
    )

    # A system-only messages list makes Groq reject the request outright
    # ("No user query found in messages"), so this always fell back silently.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

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
            # Was hardcoded to 100 — never enough once a reasoning model was
            # in play, and tight even for gpt-oss-20b's one-line answer.
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            extra_body={"reasoning_format": "hidden"},
        )
    except Exception as exc:  # pragma: no cover - provider-auth errors are handled here
        logger.warning("Daily action LLM request failed; using fallback action: %s", exc)
        return "Set aside 10% of your income for savings today. (LLM fallback)"

    choice = response.choices[0]
    return choice.message.content or ""
