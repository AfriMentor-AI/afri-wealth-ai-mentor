"""Persona Prompt Template Builder (card D1.3 integration).

Consumes the canonical CHIOMA target profile spec (card C1.4) as the single
source of truth to assemble dynamic system prompts and behavioral guidelines.
"""

from __future__ import annotations

from app.loader import PersonaProfileSpec, load_persona_profile


def build_system_prompt(profile: PersonaProfileSpec | None = None) -> str:
    """Build the official mentor system prompt directly from the persona spec."""
    profile = profile or load_persona_profile()
    lines: list[str] = []
    add = lines.append

    add(f"You are {profile.display_name}, the primary AI business and wealth mentor on AfriMentor.")
    add(
        "Your core objective is to guide African entrepreneurs and professionals toward "
        "sustainable, scalable financial success."
    )
    add("")
    add("OPERATIONAL BEHAVIOR & PERSONALITY GUIDELINES:")

    for trait in profile.all_traits:
        add(f"- [{trait.label} / {trait.target_level}]: {trait.behaviour}")

    add("")
    add("KEY CONSTRAINTS & ENGAGEMENT PRINCIPLES:")
    add(
        "1. Actionable Guidance: Never leave advice vague or theoretical. "
        "Provide concrete steps, deadlines, and tracking metrics."
    )
    add(
        "2. Authentic Context: Ground solutions in African market realities, "
        "trade dynamics, and local business environments."
    )
    add(
        "3. Empathetic Tough Love: Support and validate the entrepreneur's journey "
        "without enabling excuses or passive delays."
    )
    add(
        "4. Empower Independence: Build user capability; "
        "teach decision frameworks rather than fostering artificial dependency."
    )
    add(
        "5. Direct Response: Never output internal monologue, reasoning scratchpads, "
        "or <think> tags. Begin immediately with your direct response to the user."
    )

    return "\n".join(lines)