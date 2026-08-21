"""Tone Match and Fact Retrieval scoring pipeline (Research Console widgets).

Tone Match:
    Measures how well the mentor's responses align with the persona's intended
    voice (warm yet direct, empathetic tough-love, actionable guidance, cultural
    fluency, ending with a sharp next action) on a 0.0–1.0 scale (or 0–100 in UI).

Fact Retrieval:
    Measures the factual grounding and retrieval accuracy of financial guidance in
    the African economic context (mobile money, SACCOs/chamas/esusu, treasury bills,
    interest calculations, business tax, formal vs informal banking) on a 0.0–1.0 scale.
"""
from __future__ import annotations

import math
import re
from typing import Protocol, runtime_checkable

from app.metrics.profile import TargetProfile, load_profile
from app.metrics.schemas import Dialogue, Speaker
from app.metrics.scoring import SimilarityScorer, default_scorer, tokenize
from app.metrics.trait_fit import score_dialogue_traits

_WORD_RE = re.compile(r"[a-z0-9']+")

# Tone markers for Chioma / AfriMentor persona voice
_TONE_POSITIVE_MARKERS: frozenset[str] = frozenset(
    """
    reinvest separate automate budget timeline deadline milestone concrete action
    step plan discipline accountability sacrifice revenue margin cashflow profit
    principle truth reality listen understand together build start today
    """.split()
)

_TONE_EVASIVE_OR_WEAK_MARKERS: frozenset[str] = frozenset(
    """
    maybe perhaps somehow whatever idunno might possibly someday whenever
    not sure can't say generic impossible hopeless
    """.split()
)

# Fact Retrieval domain knowledge anchors (African finance & economic realities)
_FINANCIAL_FACT_KEYWORDS: frozenset[str] = frozenset(
    """
    sacco chamas chama esusu susu ajo mobile money m-pesa bank wallet inflation
    treasury bill bonds yield interest compound compounding rate principal tenor
    roi return tax withholding pension pfa rsa audited bookkeeping ledger invoice
    working capital inventory overhead debt equity collateral microfinance
    cbn central bank ksh kes ngn ghs zar naira cedi shillings dividend asset liability
    """.split()
)


@runtime_checkable
class ToneScorer(Protocol):
    """Protocol for scoring tone alignment."""

    def score(self, dialogue: Dialogue) -> float:
        ...


@runtime_checkable
class FactScorer(Protocol):
    """Protocol for scoring fact retrieval and financial grounding."""

    def score(self, dialogue: Dialogue) -> float:
        ...


class LexicalToneMatchScorer:
    """Deterministic lexical scorer for Tone Match.
    
    Combines:
      1. Trait fit cosine similarity against the target profile (50%).
      2. Lexical tone markers (positive action & tough love vs evasive fluff) (30%).
      3. Prompt-to-line style consistency (20%).
    """

    def __init__(self, profile: TargetProfile | None = None, base_scorer: SimilarityScorer | None = None) -> None:
        self.profile = profile or load_profile()
        self.base_scorer = base_scorer or default_scorer()

    def score(self, dialogue: Dialogue) -> float:
        mentor_turns = dialogue.mentor_turns
        if not mentor_turns:
            return 0.5

        # 1. Trait fit component (0.0 to 1.0)
        trait_result = score_dialogue_traits(dialogue, profile=self.profile)
        trait_score = max(0.0, min(1.0, trait_result.cosine_similarity))

        # 2. Tone marker component
        all_text = " ".join(t.text.lower() for t in mentor_turns)
        tokens = _WORD_RE.findall(all_text)
        if not tokens:
            marker_score = 0.5
        else:
            pos_count = sum(1 for t in tokens if t in _TONE_POSITIVE_MARKERS)
            neg_count = sum(1 for t in tokens if t in _TONE_EVASIVE_OR_WEAK_MARKERS)
            # S-curve saturation
            sat_pos = pos_count / (pos_count + 3.0) if pos_count > 0 else 0.0
            sat_neg = neg_count / (neg_count + 2.0) if neg_count > 0 else 0.0
            marker_score = max(0.0, min(1.0, 0.5 + 0.45 * sat_pos - 0.45 * sat_neg))

        # 3. Prompt alignment component
        prompt_scores = [self.base_scorer.similarity(dialogue.system_prompt, t.text) for t in mentor_turns]
        prompt_align = sum(prompt_scores) / len(prompt_scores) if prompt_scores else 0.5
        # Normalize prompt alignment to ~0.5-1.0 dynamic range
        prompt_norm = min(1.0, max(0.0, 0.4 + prompt_align * 3.0))

        # Weighted blend
        final_score = 0.50 * trait_score + 0.30 * marker_score + 0.20 * prompt_norm
        return round(max(0.0, min(1.0, final_score)), 4)


class LexicalFactRetrievalScorer:
    """Deterministic lexical scorer for Fact Retrieval and Financial Grounding.
    
    Evaluates:
      1. Presence of verifiable financial concepts, African economic structures,
         and concrete calculations/metrics (60%).
      2. Relevance of factual answers to user questions (Q&A factual overlap) (40%).
    """

    def __init__(self, base_scorer: SimilarityScorer | None = None) -> None:
        self.base_scorer = base_scorer or default_scorer()

    def score(self, dialogue: Dialogue) -> float:
        mentor_turns = dialogue.mentor_turns
        if not mentor_turns:
            return 0.5

        # 1. Fact keyword density & richness
        all_mentor_text = " ".join(t.text.lower() for t in mentor_turns)
        tokens = tokenize(all_mentor_text, drop_stopwords=True)
        if not tokens:
            fact_density = 0.5
        else:
            unique_fact_hits = set(t for t in tokens if t in _FINANCIAL_FACT_KEYWORDS)
            # Check numbers/percentages mentioned (concrete financial advice)
            has_numbers = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", all_mentor_text))
            
            # Saturation for distinct factual concepts + numerical concreteness
            fact_points = len(unique_fact_hits) + min(3, has_numbers)
            fact_density = min(1.0, max(0.1, fact_points / (fact_points + 2.5) * 1.0))

        # 2. Q&A factual alignment (answering user's queries with relevant content)
        qa_overlaps: list[float] = []
        turns = dialogue.turns
        for i in range(len(turns) - 1):
            if turns[i].speaker is Speaker.user and turns[i + 1].speaker is Speaker.mentor:
                qa_sim = self.base_scorer.similarity(turns[i].text, turns[i + 1].text)
                qa_overlaps.append(qa_sim)
        
        qa_factor = (sum(qa_overlaps) / len(qa_overlaps)) if qa_overlaps else 0.5
        # Scale to [0.4, 1.0] range
        qa_norm = min(1.0, max(0.0, 0.4 + qa_factor * 3.0))

        # Final blend
        raw_score = 0.60 * fact_density + 0.40 * qa_norm
        return round(max(0.0, min(1.0, raw_score)), 4)


def score_tone_match(
    dialogue: Dialogue,
    profile: TargetProfile | None = None,
    scorer: SimilarityScorer | None = None,
) -> float:
    """Compute the Tone Match score in [0.0, 1.0] for a single dialogue."""
    engine = LexicalToneMatchScorer(profile=profile, base_scorer=scorer)
    return engine.score(dialogue)


def score_fact_retrieval(
    dialogue: Dialogue,
    scorer: SimilarityScorer | None = None,
) -> float:
    """Compute the Fact Retrieval score in [0.0, 1.0] for a single dialogue."""
    engine = LexicalFactRetrievalScorer(base_scorer=scorer)
    return engine.score(dialogue)

