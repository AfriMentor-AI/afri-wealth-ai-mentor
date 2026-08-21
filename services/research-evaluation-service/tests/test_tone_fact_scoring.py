"""Tests for Tone Match and Fact Retrieval scoring pipeline."""
from __future__ import annotations

from app.metrics.schemas import Dialogue, Speaker, Turn
from app.metrics.tone_fact_scoring import (
    score_fact_retrieval,
    score_tone_match,
)

SYSTEM_PROMPT = (
    "You are Chioma, an AI business and wealth mentor. Give concrete, actionable "
    "guidance grounded in African market realities. Practise empathetic tough love."
)


def make_test_dialogue(
    mentor_reply: str,
    user_query: str = "How do I save money and manage loans in Kenya?",
) -> Dialogue:
    return Dialogue(
        dialogue_id="test-tone-fact-001",
        system_prompt=SYSTEM_PROMPT,
        persona_id="chioma",
        turns=[
            Turn(speaker=Speaker.user, text=user_query),
            Turn(speaker=Speaker.mentor, text=mentor_reply),
        ],
    )


def test_tone_match_high_on_actionable_tough_love_reply():
    """Actionable, tough-love, culturally grounded response scores high on Tone Match."""
    dialogue = make_test_dialogue(
        "Listen to me carefully: hope is not a strategy. "
        "Separate your personal account from business cashflow today. "
        "Reinvest 30% of your profit, automate your savings transfer to a SACCO, "
        "and set a strict budget deadline for Friday."
    )
    score = score_tone_match(dialogue)
    assert 0.65 <= score <= 1.0


def test_tone_match_lower_on_vague_evasive_reply():
    """An evasive, weak response scores lower on Tone Match."""
    dialogue = make_test_dialogue(
        "Maybe someday you might try to save, but idunno, whatever happens happens. "
        "Generic advice says it is impossible."
    )
    score = score_tone_match(dialogue)
    assert score < 0.65


def test_fact_retrieval_high_on_concrete_economic_terms():
    """Reply with African financial terms, interest numbers, and SACCO/chama concepts."""
    dialogue = make_test_dialogue(
        "To hedge against inflation in Kenya, put your emergency fund in a SACCO "
        "earning 10% dividend or treasury bills with a 91-day tenor. "
        "Use M-Pesa business wallet for tracking invoices and audited cashflow.",
        user_query="Where should I put my savings against inflation?",
    )
    score = score_fact_retrieval(dialogue)
    assert 0.70 <= score <= 1.0


def test_fact_retrieval_lower_on_generic_non_financial_reply():
    """A reply with no financial terms or grounding scores lower."""
    dialogue = make_test_dialogue(
        "Just be happy and think good thoughts and things will be fine.",
        user_query="What is the interest rate on treasury bills?",
    )
    score = score_fact_retrieval(dialogue)
    assert score < 0.60


def test_empty_dialogue_fallback():
    """Dialogues without mentor turns return safe defaults."""
    empty_dialogue = Dialogue(
        dialogue_id="test-empty",
        system_prompt=SYSTEM_PROMPT,
        persona_id="chioma",
        turns=[Turn(speaker=Speaker.user, text="Hello?")],
    )
    assert score_tone_match(empty_dialogue) == 0.5
    assert score_fact_retrieval(empty_dialogue) == 0.5

