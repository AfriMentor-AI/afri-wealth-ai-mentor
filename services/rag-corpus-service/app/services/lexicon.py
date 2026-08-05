"""African English / local expression lexicon for query normalization.

The Tier-1 corpus is transcribed speech from African entrepreneurs, so it is
dense with Pidgin, Nigerian/Ghanaian/Kenyan English and informal business
vocabulary ("hustle", "esusu", "japa"). Learners query in the same register.
Neither BM25 nor a cross-encoder trained on standard English web text bridges
that gap on its own, so query terms are expanded with standard-English
equivalents before scoring.

Expansion is additive — the original query is always preserved, so a term that
happens to appear literally in the corpus still matches.
"""
from __future__ import annotations

import re

# Local expression -> standard English equivalents.
# Keys are matched case-insensitively on whole-word boundaries.
EXPRESSION_LEXICON: dict[str, list[str]] = {
    # ── Money, saving, informal finance ──────────────────────────────────────
    "esusu": ["rotating savings", "savings group", "contribution"],
    "ajo": ["rotating savings", "savings group", "contribution"],
    "susu": ["rotating savings", "savings group", "contribution"],
    "chama": ["savings group", "investment group", "cooperative"],
    "harambee": ["community fundraising", "collective contribution"],
    "naira": ["money", "currency", "cash"],
    "cedi": ["money", "currency", "cash"],
    "shilling": ["money", "currency", "cash"],
    "kobo": ["small money", "cash"],
    "chop money": ["housekeeping money", "spending money"],
    "soft life": ["comfortable lifestyle", "spending", "luxury"],
    "black tax": ["family financial support", "dependants", "obligation"],
    # ── Work, business, hustle ───────────────────────────────────────────────
    "hustle": ["business", "work", "side business", "enterprise"],
    "hustling": ["working", "running a business", "trading"],
    "side hustle": ["side business", "secondary income", "extra income"],
    "grind": ["hard work", "persistence", "effort"],
    "japa": ["emigrate", "relocate abroad", "leave the country"],
    "oga": ["boss", "employer", "master"],
    "madam": ["boss", "employer", "proprietor"],
    "boss lady": ["female entrepreneur", "businesswoman"],
    "market woman": ["female trader", "retailer", "vendor"],
    "trader": ["merchant", "seller", "retailer"],
    "middleman": ["distributor", "reseller", "intermediary"],
    "tokunbo": ["second hand", "used goods", "imported used"],
    "okrika": ["second hand clothing", "used clothes"],
    "bend down select": ["second hand market", "used clothes market"],
    # ── Struggle, resilience ─────────────────────────────────────────────────
    "wahala": ["trouble", "problem", "difficulty", "challenge"],
    "palava": ["trouble", "dispute", "problem"],
    "suffer head": ["hardship", "struggle", "difficulty"],
    "no be small thing": ["difficult", "significant", "serious"],
    "e no easy": ["difficult", "hard", "challenging"],
    "shine your eye": ["be alert", "be careful", "be vigilant"],
    "sabi": ["know", "understand", "skilled"],
    "waka": ["walk", "travel", "move around"],
    "carry go": ["continue", "proceed", "persist"],
    # ── Trade, transport, logistics ──────────────────────────────────────────
    "danfo": ["minibus", "public transport"],
    "keke": ["tricycle", "transport", "napep"],
    "okada": ["motorcycle taxi", "transport"],
    "mama put": ["food vendor", "roadside restaurant"],
    "kiosk": ["small shop", "retail stall"],
    "shop": ["store", "retail outlet"],
    "goods": ["stock", "inventory", "merchandise"],
    "wares": ["stock", "inventory", "merchandise"],
    "mpesa": ["mobile money", "mobile payment", "digital payment"],
    "momo": ["mobile money", "mobile payment", "digital payment"],
    "pos": ["point of sale", "payment terminal", "agent banking"],
}

# Longest-first so multi-word keys ("side hustle") win over their parts.
_SORTED_KEYS = sorted(EXPRESSION_LEXICON, key=len, reverse=True)
_LEXICON_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SORTED_KEYS) + r")\b",
    re.IGNORECASE,
)


def find_expressions(text: str) -> list[str]:
    """Return the lexicon keys present in ``text``, in order, without repeats."""
    seen: list[str] = []
    for match in _LEXICON_RE.finditer(text or ""):
        key = match.group(0).lower()
        if key not in seen:
            seen.append(key)
    return seen


def expand_query(query: str) -> str:
    """Append standard-English equivalents for any local expressions found.

    Returns the query unchanged when nothing matches, so the common case costs
    one regex scan and no allocation.
    """
    found = find_expressions(query)
    if not found:
        return query
    expansions: list[str] = []
    for key in found:
        for term in EXPRESSION_LEXICON[key]:
            if term not in expansions:
                expansions.append(term)
    return query + " " + " ".join(expansions)
