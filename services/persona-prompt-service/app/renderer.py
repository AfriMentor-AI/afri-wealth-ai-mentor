"""Persona prompt renderer for persona-prompt-service.

Loads Jinja2 templates from app/prompts/ and renders them with user context
variables. Called by the Sprint 2 persona-prompt-service API endpoint, and
consumed by chat-orchestration-service via the _get_system_prompt extension point.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_persona_prompt(
    template_file: str,
    *,
    user_name: str = "friend",
    sector: str = "general",
    country: str = "NG",
    income_bracket: str = "lower_mid",
    language: str = "en",
) -> str:
    """Render a persona system prompt template with user context.

    Args:
        template_file: filename inside app/prompts/ (e.g. "sub_market_queen.j2")
        user_name:     user's first name
        sector:        sector interest slug (matches SectorInterest enum)
        country:       ISO 3166-1 alpha-2
        income_bracket: income bracket slug
        language:      BCP-47 language code

    Returns:
        Rendered system prompt string ready to pass to the LLM.
    """
    template = _env.get_template(template_file)
    return template.render(
        user_name=user_name,
        sector=sector,
        country=country,
        income_bracket=income_bracket,
        language=language,
    )
