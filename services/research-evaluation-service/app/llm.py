"""Administer persona-prompted probes against the baseline model (card C2.3).

The trait-fit metric is only a baseline measurement if the answers it scores came
from the model under evaluation. This module is that step: it fetches the CHIOMA
system prompt from persona-prompt-service (the D1.3 source of truth), sends each
probe question to the OpenAI-compatible chat-completions endpoint, and returns the
model's own replies as :class:`~app.metrics.schemas.ProbeResponse` objects.

Design notes
------------
*Direct model call, not via chat-orchestration-service.* C2.3 measures the
*persona-prompted baseline model*. Routing through the chat service would fold in
RAG passages, conversation history and commitment detection — real parts of the
product, but contamination for a trait measurement, and they change independently
of the model being scored.

*Temperature defaults to 0.0*, not the chat service's 0.7. A baseline is a number
other runs get compared against, so run-to-run sampling variance is a defect here
even though it is a feature in conversation.

*httpx, not the openai SDK.* One endpoint is needed, httpx is already a declared
dependency, and ``app/main.py`` states this service stays on FastAPI + SQLAlchemy.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx

from app.metrics.schemas import ProbeResponse

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
PERSONA_PROMPT_PATH = "/personas/chioma/prompt"

#: Retried status codes: rate limiting and transient upstream faults. A probe set
#: is 8+ sequential calls, so one 429 must not discard the whole run.
_RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class ProbeAdministrationError(RuntimeError):
    """The baseline model could not be reached, or returned no usable text."""


@dataclass(frozen=True)
class LLMConfig:
    """Connection settings for the model under evaluation.

    Env var names match chat-orchestration-service so a single ``.env`` points both
    services at the same model — otherwise the baseline would describe a model that
    is not the one users talk to.
    """

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    max_tokens: int = 512
    temperature: float = 0.0
    timeout: float = 60.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> LLMConfig:
        return cls(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=os.getenv("LLM_MODEL", DEFAULT_MODEL),
            max_tokens=int(os.getenv("PROBE_MAX_TOKENS", "512")),
            temperature=float(os.getenv("PROBE_TEMPERATURE", "0.0")),
            timeout=float(os.getenv("PROBE_TIMEOUT", "60")),
            max_retries=int(os.getenv("PROBE_MAX_RETRIES", "3")),
        )

    @property
    def is_live(self) -> bool:
        """False when no API key is configured — callers must fall back to fixtures."""
        return bool(self.api_key)


@dataclass(frozen=True)
class AdministeredProbe:
    """One probe and the answer the model actually gave.

    Kept alongside the scored result so a low trait estimate can be traced back to
    the text that produced it. ``truncated`` records that the model hit the token
    ceiling mid-sentence, which drops trailing trait markers and biases the estimate
    downward — a scoring artifact, not a persona failure.
    """

    probe_id: str
    trait: str
    question: str
    answer: str
    reverse_scored: bool = False
    latency_ms: int = 0
    truncated: bool = False

    def to_response(self) -> ProbeResponse:
        return ProbeResponse(
            probe_id=self.probe_id,
            trait=self.trait,
            question=self.question,
            answer=self.answer,
            reverse_scored=self.reverse_scored,
        )


# ── System prompt ─────────────────────────────────────────────────────────────


def build_system_prompt_local(profile) -> str:
    """Assemble the CHIOMA prompt from a locally loaded profile.

    Fallback only. persona-prompt-service owns the canonical wording (card D1.3);
    this mirrors its structure so an offline run is still persona-prompted, but a
    report produced this way is not comparable to one prompted by the service.
    """
    lines = [
        f"You are {profile.display_name}, the primary AI business and wealth "
        "mentor on AfriMentor.",
        "Your core objective is to guide African entrepreneurs and professionals "
        "toward sustainable, scalable financial success.",
        "",
        "OPERATIONAL BEHAVIOR & PERSONALITY GUIDELINES:",
    ]
    lines += [
        f"- [{t.label} / {t.target_level}]: {t.behaviour}" for t in profile.all_traits
    ]
    lines += [
        "",
        "KEY CONSTRAINTS & ENGAGEMENT PRINCIPLES:",
        "1. Actionable Guidance: Never leave advice vague or theoretical. Provide "
        "concrete steps, deadlines, and tracking metrics.",
        "2. Authentic Context: Ground solutions in African market realities, trade "
        "dynamics, and local business environments.",
        "3. Empathetic Tough Love: Support and validate the entrepreneur's journey "
        "without enabling excuses or passive delays.",
        "4. Empower Independence: Build user capability; teach decision frameworks "
        "rather than fostering artificial dependency.",
    ]
    return "\n".join(lines)


def fetch_system_prompt(
    profile,
    persona_service_url: str | None = None,
    timeout: float = 10.0,
) -> tuple[str, str]:
    """Return ``(system_prompt, provenance)`` for the persona under evaluation.

    Prefers persona-prompt-service. Falls back to :func:`build_system_prompt_local`
    when the service is unset or unreachable, and logs a warning on a profile-version
    mismatch: scoring answers against v1 targets when the model was prompted with a
    different version is a silent, invisible error.
    """
    url = persona_service_url or os.getenv("PERSONA_SERVICE_URL", "")
    if not url:
        logger.info("PERSONA_SERVICE_URL unset — building system prompt locally")
        return build_system_prompt_local(profile), "local"

    endpoint = url.rstrip("/") + PERSONA_PROMPT_PATH
    try:
        response = httpx.get(endpoint, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("persona-prompt-service unreachable (%s) — using local prompt", exc)
        return build_system_prompt_local(profile), "local-fallback"

    prompt = (payload.get("system_prompt") or "").strip()
    if not prompt:
        logger.warning("persona-prompt-service returned an empty prompt — using local")
        return build_system_prompt_local(profile), "local-fallback"

    served_version = payload.get("profile_version")
    if served_version and served_version != profile.profile_version:
        logger.warning(
            "profile version mismatch: prompt served %s, scoring against %s — "
            "trait targets and prompt are out of step",
            served_version,
            profile.profile_version,
        )
    return prompt, f"persona-prompt-service:{served_version or 'unknown'}"


# ── Model call ────────────────────────────────────────────────────────────────


def _post_completion(client: httpx.Client, config: LLMConfig, messages: list[dict]) -> dict:
    """POST /chat/completions with bounded retry on transient failures."""
    last_error: Exception | None = None

    for attempt in range(config.max_retries):
        try:
            response = client.post(
                "/chat/completions",
                json={
                    "model": config.model,
                    "messages": messages,
                    "max_tokens": config.max_tokens,
                    "temperature": config.temperature,
                },
            )
            if response.status_code in _RETRY_STATUS:
                raise httpx.HTTPStatusError(
                    f"retryable status {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt == config.max_retries - 1:
                break
            backoff = 2.0**attempt
            logger.warning(
                "probe call failed (attempt %d/%d): %s — retrying in %.0fs",
                attempt + 1,
                config.max_retries,
                exc,
                backoff,
            )
            time.sleep(backoff)

    raise ProbeAdministrationError(
        f"model call failed after {config.max_retries} attempts: {last_error}"
    ) from last_error


def administer_probe(
    question: str,
    system_prompt: str,
    config: LLMConfig,
    client: httpx.Client | None = None,
) -> AdministeredProbe:
    """Ask the persona-prompted model one probe question.

    ``probe_id`` and ``trait`` are filled in by :func:`administer_probes`; this
    returns the answer plus the call metadata.
    """
    owns_client = client is None
    client = client or httpx.Client(
        base_url=config.base_url,
        timeout=config.timeout,
        headers={"Authorization": f"Bearer {config.api_key}"},
    )
    started = time.monotonic()
    try:
        payload = _post_completion(
            client,
            config,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )
    finally:
        if owns_client:
            client.close()

    try:
        choice = payload["choices"][0]
        answer = (choice["message"]["content"] or "").strip()
        finish_reason = choice.get("finish_reason", "")
    except (KeyError, IndexError, TypeError) as exc:
        raise ProbeAdministrationError(f"malformed completion response: {payload}") from exc

    if not answer:
        raise ProbeAdministrationError(
            "model returned an empty answer; it cannot be scored as a trait signal"
        )

    return AdministeredProbe(
        probe_id="",
        trait="",
        question=question,
        answer=answer,
        latency_ms=int((time.monotonic() - started) * 1000),
        truncated=finish_reason == "length",
    )


def administer_probes(
    probe_set: Sequence[ProbeResponse],
    system_prompt: str,
    config: LLMConfig | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[AdministeredProbe]:
    """Administer a whole probe set, reusing one HTTP connection.

    ``probe_set`` supplies the instrument — ``probe_id``, ``trait``, ``question`` and
    ``reverse_scored``. Any ``answer`` already on those objects is ignored: the point
    of this function is to replace fixture answers with the model's own.
    """
    config = config or LLMConfig.from_env()
    if not config.is_live:
        raise ProbeAdministrationError(
            "LLM_API_KEY is not set; cannot administer probes against a live model"
        )

    administered: list[AdministeredProbe] = []
    with httpx.Client(
        base_url=config.base_url,
        timeout=config.timeout,
        headers={"Authorization": f"Bearer {config.api_key}"},
    ) as client:
        for index, probe in enumerate(probe_set, start=1):
            if on_progress:
                on_progress(index, len(probe_set), probe.probe_id)
            result = administer_probe(probe.question, system_prompt, config, client=client)
            administered.append(
                AdministeredProbe(
                    probe_id=probe.probe_id,
                    trait=probe.trait,
                    question=probe.question,
                    answer=result.answer,
                    reverse_scored=probe.reverse_scored,
                    latency_ms=result.latency_ms,
                    truncated=result.truncated,
                )
            )

    truncated = [p.probe_id for p in administered if p.truncated]
    if truncated:
        logger.warning(
            "%d probe answer(s) hit the token ceiling and were cut off: %s — "
            "trait estimates for these are biased low",
            len(truncated),
            ", ".join(truncated),
        )
    return administered
