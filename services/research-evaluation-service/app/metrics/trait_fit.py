"""Trait-level fit: estimate a trait vector and compare it to CHIOMA's target.

Two entry points:

* :func:`score_dialogue_traits` — estimate traits from the mentor's turns in a
  conversation. Used for toy dialogues in v0 and for sampled real sessions in C3.2.
* :func:`score_probe_traits` — estimate traits from BFI/TRAIT-style probe
  responses. This is the form card C2.3 administers against the baseline model.

Both produce a :class:`~app.metrics.schemas.TraitFitResult` whose headline number
is the cosine similarity between the observed and target trait vectors.
"""

from __future__ import annotations

from collections import defaultdict

from app.metrics.profile import TargetProfile, TraitTarget, load_profile
from app.metrics.schemas import Dialogue, ProbeResponse, TraitFitResult, TraitScore
from app.metrics.scoring import cosine_dense, tokenize

#: A trait's estimate is pulled toward this value when there is no lexical
#: evidence either way, rather than collapsing to 0 and faking a large deficit.
NEUTRAL = 0.5

#: How fast marker evidence saturates. With k=3, one marker moves the estimate
#: about a third of the way to the ceiling, three markers about two thirds.
SATURATION_K = 3.0


def _marker_hits(text: str, phrases: list[str]) -> int:
    """Count marker phrases present in ``text``.

    Multi-word markers are matched as substrings; single words are matched
    against the token set so ``"act"`` does not fire inside ``"contract"``.
    """
    lowered = text.lower()
    tokens = set(tokenize(lowered, drop_stopwords=False))
    hits = 0
    for phrase in phrases:
        target = phrase.lower().strip()
        if not target:
            continue
        if " " in target:
            if target in lowered:
                hits += 1
        elif target in tokens:
            hits += 1
    return hits


def _saturate(count: int) -> float:
    """Map an evidence count onto [0, 1) with diminishing returns."""
    if count <= 0:
        return 0.0
    return count / (count + SATURATION_K)


def estimate_trait_value(text: str, trait: TraitTarget) -> tuple[float, int]:
    """Estimate one trait's expressed level from text.

    Returns ``(value, evidence_count)``. Positive markers push the estimate above
    :data:`NEUTRAL`, counter-markers pull it below; with no evidence the estimate
    is exactly :data:`NEUTRAL` and ``evidence_count`` is 0, which the report
    surfaces so a confident-looking score cannot hide an empty basis.
    """
    positive = _marker_hits(text, trait.markers)
    negative = _marker_hits(text, trait.counter_markers)
    evidence = positive + negative

    if evidence == 0:
        return NEUTRAL, 0

    lift = _saturate(positive) * (1.0 - NEUTRAL)
    drop = _saturate(negative) * NEUTRAL
    value = NEUTRAL + lift - drop
    return round(min(1.0, max(0.0, value)), 6), evidence


def _build_result(
    per_trait: list[TraitScore],
    source: str,
) -> TraitFitResult:
    observed = [t.observed_value for t in per_trait]
    target = [t.target_value for t in per_trait]
    similarity = cosine_dense(observed, target) if per_trait else 0.0
    mae = (
        sum(abs(t.observed_value - t.target_value) for t in per_trait) / len(per_trait)
        if per_trait
        else 0.0
    )
    return TraitFitResult(
        cosine_similarity=round(similarity, 6),
        mean_absolute_error=round(mae, 6),
        per_trait=per_trait,
        source=source,  # type: ignore[arg-type]
    )


def score_dialogue_traits(
    dialogue: Dialogue,
    profile: TargetProfile | None = None,
    include_distinctive: bool = True,
) -> TraitFitResult:
    """Estimate trait fit from the mentor's turns in ``dialogue``."""
    profile = profile or load_profile()
    mentor_text = "\n".join(t.text for t in dialogue.mentor_turns)
    traits = profile.all_traits if include_distinctive else profile.traits

    per_trait: list[TraitScore] = []
    for trait in traits:
        observed, evidence = estimate_trait_value(mentor_text, trait)
        per_trait.append(
            TraitScore(
                trait=trait.key,
                label=trait.label,
                target_level=trait.target_level,
                target_value=trait.target_value,
                observed_value=observed,
                delta=round(observed - trait.target_value, 6),
                evidence_count=evidence,
            )
        )
    return _build_result(per_trait, source="dialogue")


def score_probe_traits(
    responses: list[ProbeResponse],
    profile: TargetProfile | None = None,
) -> TraitFitResult:
    """Estimate trait fit from BFI/TRAIT-style probe responses.

    Responses are grouped by trait and averaged. A ``reverse_scored`` probe has
    its contribution mirrored about :data:`NEUTRAL`. Traits with no probes are
    omitted from the vector rather than imputed.
    """
    profile = profile or load_profile()
    grouped: dict[str, list[tuple[float, int]]] = defaultdict(list)

    for response in responses:
        trait = profile.by_key(response.trait)
        if trait is None:
            raise ValueError(
                f"probe {response.probe_id!r} targets unknown trait {response.trait!r}; "
                f"known traits: {[t.key for t in profile.all_traits]}"
            )
        value, evidence = estimate_trait_value(response.answer, trait)
        if response.reverse_scored:
            value = round(1.0 - value, 6)
        grouped[trait.key].append((value, evidence))

    per_trait: list[TraitScore] = []
    for trait in profile.all_traits:
        entries = grouped.get(trait.key)
        if not entries:
            continue
        mean_value = sum(v for v, _ in entries) / len(entries)
        total_evidence = sum(e for _, e in entries)
        per_trait.append(
            TraitScore(
                trait=trait.key,
                label=trait.label,
                target_level=trait.target_level,
                target_value=trait.target_value,
                observed_value=round(mean_value, 6),
                delta=round(mean_value - trait.target_value, 6),
                evidence_count=total_evidence,
            )
        )

    if not per_trait:
        raise ValueError("no probe responses matched any trait in the profile")
    return _build_result(per_trait, source="probes")
