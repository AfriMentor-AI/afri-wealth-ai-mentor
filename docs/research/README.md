# Research & Evaluation Documentation

This directory contains research specifications, benchmark methodologies, and evaluation documents for the AfriMentor AI platform.

## Index of Research Specifications

- **[Personality-Consistency Metric Suite v0 (Card C1.3)](file:///home/venus/afri-wealth-ai-mentor/docs/research/personality-consistency-metric-suite-v0.md)**
  - Specification and initial scoring implementation for trait-level persona fit and behavioral consistency (prompt-to-line, line-to-line, Q&A consistency per Abdulhai et al. 2025).
- **[Pilot Data-Collection Plan v0 (Card C2.5)](file:///home/venus/afri-wealth-ai-mentor/docs/research/pilot-data-collection-plan-v0.md)**
  - Draft eligibility criteria, consent-form content, and pre/post survey instrument for the Proposal 2 pilot. Section 2's power analysis is the load-bearing part: at N = 20-30 the between-arm comparison cannot be a hypothesis test, so the study is specified as a feasibility and instrument-validation pilot. **Awaiting review by Grace.**

---

## Related Services

- **[Research & Evaluation Service (`services/research-evaluation-service`)](file:///home/venus/afri-wealth-ai-mentor/services/research-evaluation-service)**
  - Houses the metric suite implementation (`app/metrics`), toy dialogue data (`data/toy_dialogues`), CHIOMA target profile (`data/chioma_profile.v0.json`), and scoring script (`scripts/run_metrics.py`).
  - `scripts/pilot_power_analysis.py` reproduces every figure in section 2 of the pilot plan; run it from the service directory with the service venv.
