"""Format instructions shared by dataset generation and the fair-baseline evaluation condition (C1S).

The teacher produced the training answers under CHOSEN_STYLE. C1S gives the *untrained* base model the same
instruction at evaluation time, so a comparison against C2-C4 separates "the model learned the persona/format
from training" from "the base model was never told the format". Keep generation and evaluation in sync by
importing from here only.
"""
from __future__ import annotations

WORD_MIN, WORD_MAX = 70, 140

CHOSEN_STYLE = (f"\n\n[Reply in {WORD_MIN}-{WORD_MAX} words of plain conversational prose: no headings, no bullet or "
                "numbered lists, no markdown. Include at least one concrete number or step relevant to their "
                "situation and end with ONE sharp next action or ONE question.]")
REJECTED_STYLE = (f"\n\n[Reply in {WORD_MIN}-{WORD_MAX} words of plain prose: no headings, no bullet or numbered "
                  "lists, no markdown.]")


# Persona audience blurbs (kept here so training, generation and evaluation agree).
PERSONA_BLURB = {
    "chioma-base": "small-business owner", "market-queen": "market trader selling goods at a stall",
    "tech-founder": "founder of an early-stage tech startup", "trader": "importer/wholesale trader",
    "rural-hustler": "smallholder farmer or rural micro-entrepreneur", "creative": "freelance creative or artisan",
}


def minimal_system_prompt(persona_slug: str) -> str:
    """~30-token system prompt for the *prompt-free* setting: the fine-tuned model must supply the persona,
    voice and format itself. The full persona prompt is ~1.7k tokens on every request (cost + latency on 3G)."""
    kind = PERSONA_BLURB.get(persona_slug, "small-business owner")
    return f"You are Chioma, a business mentor for young African entrepreneurs. You are advising a {kind}."
