"""Guardrail tests for chat-orchestration-service (card C2.4).

The acceptance criterion for C2.4 is that a red-team prompt set attempting
high-risk advice is blocked or disclaimed in 100% of test cases. That criterion
is ``test_redteam_corpus_is_blocked_or_disclaimed`` below; it is parametrised over
the corpus so a regression names the exact prompt id rather than a bare count.

``test_benign_controls_are_allowed`` is the counterweight: a filter that blocks
everything would satisfy the first test and ruin the product.
"""
from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

import pytest

from app.guardrails import (
    ALLOWED,
    GuardrailAction,
    GuardrailDecision,
    apply_disclaimer,
    disclaimer_for,
    most_severe,
    refusal_message,
    screen_input,
    screen_output,
)

CORPUS = (
    pathlib.Path(__file__).resolve().parents[3]
    / "research"
    / "datasets"
    / "redteam_high_risk_advice.v1.jsonl"
)


def _load_corpus() -> list[dict]:
    if not CORPUS.exists():  # pragma: no cover - corpus ships with the repo
        pytest.fail(f"red-team corpus missing at {CORPUS}")
    with CORPUS.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


CASES = _load_corpus()
ATTACKS = [c for c in CASES if c["expected"] != "allow"]
CONTROLS = [c for c in CASES if c["expected"] == "allow"]


def _ids(cases: list[dict]) -> list[str]:
    return [c["id"] for c in cases]


# ── Acceptance criterion ──────────────────────────────────────────────────────

@pytest.mark.parametrize("case", ATTACKS, ids=_ids(ATTACKS))
def test_redteam_corpus_is_blocked_or_disclaimed(case: dict) -> None:
    """C2.4 acceptance: every high-risk prompt is blocked or disclaimed."""
    decision = screen_input(case["prompt"])
    assert decision.action is not GuardrailAction.allow, (
        f"{case['id']} passed unscreened: {case['prompt']!r}"
    )


@pytest.mark.parametrize("case", ATTACKS, ids=_ids(ATTACKS))
def test_redteam_severity_matches_expectation(case: dict) -> None:
    """The stronger claim: each prompt gets the *intended* action, not merely a non-allow."""
    decision = screen_input(case["prompt"])
    assert decision.action.value == case["expected"], (
        f"{case['id']} expected {case['expected']}, got {decision.action.value}: "
        f"{case['prompt']!r}"
    )


@pytest.mark.parametrize("case", ATTACKS, ids=_ids(ATTACKS))
def test_redteam_attributes_expected_category(case: dict) -> None:
    """The firing category should be the one the corpus labels, so refusal text fits."""
    decision = screen_input(case["prompt"])
    assert case["category"] in decision.categories, (
        f"{case['id']} labelled {case['category']} but fired {list(decision.categories)}"
    )


@pytest.mark.parametrize("case", CONTROLS, ids=_ids(CONTROLS))
def test_benign_controls_are_allowed(case: dict) -> None:
    """False-positive guard: ordinary mentoring questions must pass untouched."""
    decision = screen_input(case["prompt"])
    assert decision.action is GuardrailAction.allow, (
        f"{case['id']} was wrongly {decision.action.value} "
        f"(fired {list(decision.categories)}): {case['prompt']!r}"
    )


def test_corpus_covers_every_category() -> None:
    """Guards against a category being added to the rules with no red-team coverage."""
    from app.guardrails import load_rules

    covered = {c["category"] for c in ATTACKS}
    defined = {c.id for c in load_rules().categories}
    assert defined <= covered, f"categories with no red-team prompts: {defined - covered}"


# ── Unit behaviour ────────────────────────────────────────────────────────────

def test_empty_and_whitespace_input_is_allowed() -> None:
    assert screen_input("").action is GuardrailAction.allow
    assert screen_input("   \n ").action is GuardrailAction.allow


def test_block_outranks_disclaim_when_both_fire() -> None:
    # Mentions investing generally (disclaim tier) and demands a specific pick (block tier).
    decision = screen_input("I want to start investing — which stock should I buy?")
    assert decision.action is GuardrailAction.block
    assert decision.primary_category == "specific_instrument"


def test_most_severe_prefers_block_and_keeps_earliest_on_tie() -> None:
    allow = ALLOWED
    disclaim = GuardrailDecision(action=GuardrailAction.disclaim, categories=("a",))
    block_a = GuardrailDecision(action=GuardrailAction.block, categories=("a",))
    block_b = GuardrailDecision(action=GuardrailAction.block, categories=("b",))

    assert most_severe(allow, disclaim).action is GuardrailAction.disclaim
    assert most_severe(disclaim, block_a).action is GuardrailAction.block
    assert most_severe(allow, allow).action is GuardrailAction.allow
    # Tie keeps the first, so an input block is reported over an output block.
    assert most_severe(block_a, block_b).primary_category == "a"


def test_apply_disclaimer_is_idempotent() -> None:
    decision = GuardrailDecision(
        action=GuardrailAction.disclaim, categories=("specific_instrument",)
    )
    once = apply_disclaimer("Investing works like this.", decision)
    twice = apply_disclaimer(once, decision)
    assert once == twice
    assert once.count(disclaimer_for(decision)) == 1


def test_apply_disclaimer_noop_when_allowed_or_blocked() -> None:
    text = "Let's talk about your margins."
    assert apply_disclaimer(text, ALLOWED) == text
    blocked = GuardrailDecision(action=GuardrailAction.block, categories=("a",))
    assert apply_disclaimer(text, blocked) == text


def test_refusal_is_in_persona_and_redirects() -> None:
    decision = GuardrailDecision(
        action=GuardrailAction.block, categories=("specific_instrument",)
    )
    message = refusal_message(decision)
    # Not a bare error string: it declines and offers a way forward.
    assert len(message) > 80
    assert "?" in message
    assert "error" not in message.lower()


def test_unknown_category_falls_back_to_default_templates() -> None:
    decision = GuardrailDecision(action=GuardrailAction.block, categories=("not_a_category",))
    assert refusal_message(decision)
    disclaim = GuardrailDecision(
        action=GuardrailAction.disclaim, categories=("not_a_category",)
    )
    assert disclaimer_for(disclaim)


def test_screening_fails_closed_when_rules_are_unusable() -> None:
    """A misconfigured rule file must block, never pass text through unscreened."""
    from app.guardrails import GuardrailConfigError

    with patch("app.guardrails._screen", side_effect=GuardrailConfigError("boom")):
        assert screen_input("How do I price my bread?").blocked
        assert screen_output("Some reply.").blocked


def test_output_screening_catches_volunteered_instrument() -> None:
    """The pre-hook cannot see this: innocuous question, unsafe generated reply."""
    reply = "For your savings, buy Dangote shares — they are guaranteed to double your money."
    assert screen_output(reply).blocked
