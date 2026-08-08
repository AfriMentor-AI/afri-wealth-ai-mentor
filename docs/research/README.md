# Research & Evaluation Documentation

This directory contains research specifications, benchmark methodologies, and evaluation documents for the AfriMentor AI platform.

## Index of Research Specifications

- **[Personality-Consistency Metric Suite v0 (Card C1.3)](file:///home/venus/afri-wealth-ai-mentor/docs/research/personality-consistency-metric-suite-v0.md)**
  - Specification and initial scoring implementation for trait-level persona fit and behavioral consistency (prompt-to-line, line-to-line, Q&A consistency per Abdulhai et al. 2025).

---

## Related Services

- **[Research & Evaluation Service (`services/research-evaluation-service`)](file:///home/venus/afri-wealth-ai-mentor/services/research-evaluation-service)**
  - Houses the metric suite implementation (`app/metrics`), toy dialogue data (`data/toy_dialogues`), CHIOMA target profile (`data/chioma_profile.v0.json`), and scoring script (`scripts/run_metrics.py`).
