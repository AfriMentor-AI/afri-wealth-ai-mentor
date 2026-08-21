"""Report assembly — the numeric output required by C1.3's acceptance criteria."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.metrics.consistency import score_consistency
from app.metrics.profile import TargetProfile, load_profile
from app.metrics.schemas import ConsistencyResult, Dialogue, ProbeResponse, TraitFitResult
from app.metrics.scoring import SimilarityScorer, default_scorer
from app.metrics.tone_fact_scoring import score_fact_retrieval, score_tone_match
from app.metrics.trait_fit import score_dialogue_traits, score_probe_traits

#: Weights for the composite persona score. Trait fit answers "is this the right
#: personality"; consistency answers "does it hold". Both matter, so v0 weights
#: them equally. Revisit once C2.3 has real embedding-backed numbers.
TRAIT_WEIGHT = 0.5
CONSISTENCY_WEIGHT = 0.5


class EvaluationReport(BaseModel):
    """Per-dialogue metric report."""

    dialogue_id: str
    profile_id: str
    profile_version: str
    scorer: str
    trait_fit: TraitFitResult
    consistency: ConsistencyResult
    tone_match_score: float = 0.0
    fact_retrieval_score: float = 0.0
    probe_trait_fit: TraitFitResult | None = None
    warnings: list[str] = Field(default_factory=list)

    @property
    def composite_score(self) -> float:
        """Weighted blend of trait fit and consistency, in [0, 1].

        Cosine similarity is clamped at 0 before blending: the trait vectors are
        non-negative so a negative cosine is not meaningful here, and letting one
        through would drag the composite below the range consumers expect.
        """
        trait_component = max(0.0, self.trait_fit.cosine_similarity)
        return round(
            TRAIT_WEIGHT * trait_component + CONSISTENCY_WEIGHT * self.consistency.aggregate,
            4,
        )

    def summary_row(self) -> dict[str, object]:
        """Flat one-line-per-dialogue view, for CSV export and the console table."""
        return {
            "dialogue_id": self.dialogue_id,
            "composite": self.composite_score,
            "trait_cosine": self.trait_fit.cosine_similarity,
            "trait_mae": self.trait_fit.mean_absolute_error,
            "prompt_to_line": self.consistency.prompt_to_line,
            "line_to_line": self.consistency.line_to_line,
            "qa_consistency": self.consistency.qa_consistency,
            "worst_trait": (
                self.trait_fit.worst_trait.trait if self.trait_fit.worst_trait else None
            ),
        }


class ReportBundle(BaseModel):
    """A batch of reports plus corpus-level aggregates."""

    reports: list[EvaluationReport]
    mean_composite: float
    mean_trait_cosine: float
    mean_consistency: float

    def summary_rows(self) -> list[dict[str, object]]:
        return [r.summary_row() for r in self.reports]


def _collect_warnings(report_trait: TraitFitResult, consistency: ConsistencyResult) -> list[str]:
    """Flag results whose basis is too thin to read as a real measurement."""
    warnings: list[str] = []
    blind = [t.trait for t in report_trait.per_trait if t.evidence_count == 0]
    if blind:
        warnings.append(
            "no lexical evidence for traits: " + ", ".join(blind) + " (estimated at neutral)"
        )
    if consistency.n_line_to_line == 0:
        warnings.append("line-to-line not measurable: fewer than 2 mentor turns")
    if consistency.n_qa_pairs == 0:
        warnings.append("qa-consistency not measurable: no adjacent user→mentor pair")
    return warnings


def score_dialogue(
    dialogue: Dialogue,
    profile: TargetProfile | None = None,
    scorer: SimilarityScorer | None = None,
    probes: list[ProbeResponse] | None = None,
) -> EvaluationReport:
    """Score one dialogue on both metric families.

    ``probes``, when supplied, adds a probe-based trait estimate alongside the
    dialogue-derived one — the two are reported separately because Han et al.
    (2025) find self-reported and behaviourally-expressed personality diverge.
    """
    profile = profile or load_profile()
    scorer = scorer or default_scorer()

    trait_fit = score_dialogue_traits(dialogue, profile=profile)
    consistency = score_consistency(dialogue, scorer=scorer)
    tone_match = score_tone_match(dialogue, profile=profile, scorer=scorer)
    fact_retrieval = score_fact_retrieval(dialogue, scorer=scorer)
    probe_fit = score_probe_traits(probes, profile=profile) if probes else None

    return EvaluationReport(
        dialogue_id=dialogue.dialogue_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        scorer=type(scorer).__name__,
        trait_fit=trait_fit,
        consistency=consistency,
        tone_match_score=tone_match,
        fact_retrieval_score=fact_retrieval,
        probe_trait_fit=probe_fit,
        warnings=_collect_warnings(trait_fit, consistency),
    )


def score_dialogues(
    dialogues: list[Dialogue],
    profile: TargetProfile | None = None,
    scorer: SimilarityScorer | None = None,
) -> ReportBundle:
    """Score a batch of dialogues and aggregate across them."""
    if not dialogues:
        raise ValueError("no dialogues supplied")
    profile = profile or load_profile()
    scorer = scorer or default_scorer()

    reports = [score_dialogue(d, profile=profile, scorer=scorer) for d in dialogues]
    count = len(reports)
    return ReportBundle(
        reports=reports,
        mean_composite=round(sum(r.composite_score for r in reports) / count, 4),
        mean_trait_cosine=round(
            sum(r.trait_fit.cosine_similarity for r in reports) / count, 4
        ),
        mean_consistency=round(
            sum(r.consistency.aggregate for r in reports) / count, 4
        ),
    )
