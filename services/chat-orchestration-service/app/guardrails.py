"""Guardrails module for chat-orchestration-service (card C2.4).

Screens both the user's message and the model's reply for high-risk financial
advice. Two outcomes matter:

  block    — the turn is refused in-persona. On input this happens *before*
             RAG retrieval and the LLM call, so a high-risk query never reaches
             the corpus or the model.
  disclaim — the reply is allowed but a disclaimer is appended.

Detection is deterministic (compiled regex over a versioned rule file), not
model-based. The acceptance criterion for C2.4 is 100% coverage of a fixed
red-team set, which needs a decision procedure that is provable and stable;
a classifier call would also fail open in CI, where LLM_API_KEY is unset and
``app.llm.chat_completion`` takes its stub path.

The rule file is data (``app/data/guardrail_rules.v1.json``) so the policy can
be revised without touching this module — relevant because the card cites
report section 5.4, which is not yet written.

Each category declares which ``surface`` it screens. The six C2.4 categories
screen both, because a request for a specific stock is equally unsafe whether
the user asks for it or the model volunteers it. ``ai_disclosure`` (card C2.5,
plan section 4.3) is the first output-only category: the risk is the *model*
claiming to be human, and screening the same patterns on input would refuse a
user who innocently asks "are you a real person?" — a question the consent
protocol requires be answered honestly, not blocked.

Fails **closed**: if the rules cannot be loaded or screening raises, the turn is
blocked. This is the opposite of ``app.rag.retrieve``, which deliberately
swallows errors so chat survives RAG being down. A guardrail that fails open is
not a guardrail.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

RULES_PATH = Path(__file__).resolve().parent / "data" / "guardrail_rules.v1.json"


class GuardrailAction(str, Enum):
    """What to do with a turn. Ordered least to most severe."""

    allow = "allow"
    disclaim = "disclaim"
    block = "block"


# Severity ranking used when several categories fire on one turn.
_SEVERITY: dict[GuardrailAction, int] = {
    GuardrailAction.allow: 0,
    GuardrailAction.disclaim: 1,
    GuardrailAction.block: 2,
}


@dataclass(frozen=True)
class GuardrailDecision:
    """Outcome of screening one piece of text.

    ``matched_terms`` records which patterns fired. It is kept for audit and for
    the C-track research evaluation; it is never shown to the user, since it
    would tell someone probing the filter exactly which phrasing tripped it.
    """

    action: GuardrailAction = GuardrailAction.allow
    categories: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = field(default=())

    @property
    def blocked(self) -> bool:
        return self.action is GuardrailAction.block

    @property
    def primary_category(self) -> str | None:
        """The category whose message templates should be used."""
        return self.categories[0] if self.categories else None


ALLOWED = GuardrailDecision()

#: Which side of a turn a category is allowed to fire on.
INPUT = "input"
OUTPUT = "output"
SURFACES = frozenset({INPUT, OUTPUT})


class GuardrailConfigError(RuntimeError):
    """The rule file is missing or malformed."""


@dataclass(frozen=True)
class _Category:
    id: str
    surfaces: frozenset[str]
    block_patterns: tuple[re.Pattern[str], ...]
    disclaim_patterns: tuple[re.Pattern[str], ...]
    exempt_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class _Rules:
    categories: tuple[_Category, ...]
    disclaimers: dict[str, str]
    refusals: dict[str, str]
    version: str


def _compile(patterns: list[str], *, category: str, tier: str) -> tuple[re.Pattern[str], ...]:
    compiled: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            compiled.append(re.compile(raw, re.IGNORECASE))
        except re.error as exc:
            raise GuardrailConfigError(
                f"invalid {tier} pattern for category '{category}': {raw!r} ({exc})"
            ) from exc
    return tuple(compiled)


def _parse_surfaces(entry: dict, *, category: str) -> frozenset[str]:
    """Which surfaces a category screens. Absent or "both" means every surface.

    Defaulting to both keeps every pre-existing category behaving exactly as it
    did before this field existed.
    """
    raw = entry.get("surface", "both")
    if raw == "both":
        return SURFACES
    if isinstance(raw, str):
        values = frozenset({raw})
    elif isinstance(raw, list) and all(isinstance(v, str) for v in raw):
        values = frozenset(raw)
    else:
        # Anything else would raise TypeError out of load_rules, which
        # _screen_failing_closed does not catch — the turn would 500 instead of
        # blocking, defeating the fail-closed contract.
        raise GuardrailConfigError(
            f"category '{category}' has a non-string 'surface': {raw!r}"
        )
    unknown = values - SURFACES
    if unknown:
        raise GuardrailConfigError(
            f"category '{category}' declares unknown surface(s) {sorted(unknown)}; "
            f"expected some of {sorted(SURFACES)} or 'both'"
        )
    if not values:
        raise GuardrailConfigError(f"category '{category}' declares an empty surface list")
    return values


@lru_cache(maxsize=1)
def load_rules() -> _Rules:
    """Load and compile the rule file once per process."""
    try:
        raw = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GuardrailConfigError(f"guardrail rules not found at {RULES_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise GuardrailConfigError(f"guardrail rules are not valid JSON: {exc}") from exc

    categories = []
    for entry in raw.get("categories", []):
        cid = entry.get("id")
        if not cid:
            raise GuardrailConfigError("a category entry is missing its 'id'")
        categories.append(
            _Category(
                id=cid,
                surfaces=_parse_surfaces(entry, category=cid),
                block_patterns=_compile(
                    entry.get("block_patterns", []), category=cid, tier="block"
                ),
                disclaim_patterns=_compile(
                    entry.get("disclaim_patterns", []), category=cid, tier="disclaim"
                ),
                exempt_patterns=_compile(
                    entry.get("exempt_patterns", []), category=cid, tier="exempt"
                ),
            )
        )

    if not categories:
        raise GuardrailConfigError("guardrail rules define no categories")

    disclaimers = raw.get("disclaimers", {})
    refusals = raw.get("refusals", {})
    for name, table in (("disclaimers", disclaimers), ("refusals", refusals)):
        if "default" not in table:
            raise GuardrailConfigError(f"'{name}' must define a 'default' entry")

    return _Rules(
        categories=tuple(categories),
        disclaimers=disclaimers,
        refusals=refusals,
        version=str(raw.get("rules_version", "unknown")),
    )


def _screen(text: str, *, surface: str) -> GuardrailDecision:
    """Match ``text`` against every category valid for ``surface``; most severe wins.

    Categories are evaluated in rule-file order, and a blocking category is
    ordered ahead of a merely-disclaiming one so ``primary_category`` names the
    reason the turn was actually stopped.

    A category is skipped entirely when one of its ``exempt_patterns`` matches.
    This exists because output screening asks a different question from input
    screening: on input the presence of a risky phrase *is* the risk, but on
    output the same phrase can appear in a reply that is handling it correctly
    ("you asked whether I'm a real person — I'm not"). The exemption is what
    keeps a correct reply from being punished for naming the thing it refuses.
    """
    if not text or not text.strip():
        return ALLOWED

    rules = load_rules()
    blocking: list[str] = []
    disclaiming: list[str] = []
    matched: list[str] = []

    for category in rules.categories:
        if surface not in category.surfaces:
            continue
        if any(p.search(text) for p in category.exempt_patterns):
            continue
        hit = next((p for p in category.block_patterns if p.search(text)), None)
        if hit is not None:
            blocking.append(category.id)
            matched.append(hit.pattern)
            continue
        hit = next((p for p in category.disclaim_patterns if p.search(text)), None)
        if hit is not None:
            disclaiming.append(category.id)
            matched.append(hit.pattern)

    if blocking:
        return GuardrailDecision(
            action=GuardrailAction.block,
            categories=tuple(blocking + disclaiming),
            matched_terms=tuple(matched),
        )
    if disclaiming:
        return GuardrailDecision(
            action=GuardrailAction.disclaim,
            categories=tuple(disclaiming),
            matched_terms=tuple(matched),
        )
    return ALLOWED


def _screen_failing_closed(text: str, *, surface: str) -> GuardrailDecision:
    try:
        return _screen(text, surface=surface)
    except GuardrailConfigError:
        # Misconfiguration is an operator error, not a user one. Refuse the turn
        # rather than let unscreened advice through, and make it loud.
        logger.exception("guardrail rules unusable — blocking on %s to fail closed", surface)
        return GuardrailDecision(action=GuardrailAction.block, categories=("default",))


def screen_input(text: str) -> GuardrailDecision:
    """Pre-hook: screen the user's message before retrieval or generation."""
    return _screen_failing_closed(text, surface=INPUT)


def screen_output(text: str) -> GuardrailDecision:
    """Post-hook: screen the model's reply before it is persisted or returned."""
    return _screen_failing_closed(text, surface=OUTPUT)


def most_severe(*decisions: GuardrailDecision) -> GuardrailDecision:
    """Return whichever decision carries the highest severity.

    Ties keep the earliest argument, so an input block outranks an output block
    and the recorded reason matches what actually stopped the turn.
    """
    chosen = ALLOWED
    for decision in decisions:
        if _SEVERITY[decision.action] > _SEVERITY[chosen.action]:
            chosen = decision
    return chosen


def _template(table: dict[str, str], decision: GuardrailDecision) -> str:
    category = decision.primary_category
    if category and category in table:
        return table[category]
    return table["default"]


def disclaimer_for(decision: GuardrailDecision) -> str:
    """The disclaimer text appropriate to ``decision``."""
    return _template(load_rules().disclaimers, decision)


def refusal_message(decision: GuardrailDecision) -> str:
    """The in-persona refusal for a blocked turn.

    Chioma declines and redirects to what she can help with. A flat error
    string would read as a bug to the user and would contradict the persona's
    documented counter-markers.
    """
    try:
        return _template(load_rules().refusals, decision)
    except GuardrailConfigError:
        # Reached only when the rule file is unusable, which is also the path
        # that produced the block. A hardcoded refusal keeps that failure safe.
        logger.exception("guardrail rules unusable — using built-in refusal")
        return (
            "That's not something I can guide you on right now. Let's look at your "
            "cashflow and margins instead — where would you like to start?"
        )


def apply_disclaimer(text: str, decision: GuardrailDecision) -> str:
    """Append the disclaimer for ``decision`` to ``text``.

    Idempotent: a reply that already carries the disclaimer is returned
    unchanged, so screening a message twice cannot stack duplicates.
    """
    if decision.action is not GuardrailAction.disclaim:
        return text
    disclaimer = disclaimer_for(decision)
    if disclaimer in text:
        return text
    if not text.strip():
        return disclaimer
    return f"{text.rstrip()}\n\n{disclaimer}"
