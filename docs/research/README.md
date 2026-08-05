# Research & Evaluation Documentation

This directory contains research specifications, benchmark methodologies, and evaluation documents for the AfriMentor AI platform.

## Index of Research Specifications

- **[Personality-Consistency Metric Suite v0 (Card C1.3)](file:///home/venus/afri-wealth-ai-mentor/docs/research/personality-consistency-metric-suite-v0.md)**
  - Specification and initial scoring implementation for trait-level persona fit and behavioral consistency (prompt-to-line, line-to-line, Q&A consistency per Abdulhai et al. 2025).

- **[Personality Profile Specification v1 (Card C1.4)](file:///home/venus/afri-wealth-ai-mentor/services/persona-prompt-service/data/chioma_profile.v1.json)**
  - Machine-readable JSON specification and schema for CHIOMA persona target profile.

- **[Candidate Open Base Models Shortlist for SFT/RLHF (Card C1.5)](file:///home/venus/afri-wealth-ai-mentor/docs/research/base-model-shortlist-sft-rlhf.md)**
  - Shortlist document evaluating Llama 3.1 8B, Qwen 2.5 7B, and Mistral 7B v0.3 with tradeoffs matrix, PEFT/DPO alignment workflows, and GPU compute/hosting budget plan.

---

## Related Services

- **[Research & Evaluation Service (`services/research-evaluation-service`)](file:///home/venus/afri-wealth-ai-mentor/services/research-evaluation-service)**
  - Houses the metric suite implementation (`app/metrics`), toy dialogue data (`data/toy_dialogues`), and scoring script (`scripts/run_metrics.py`).
- **[Persona & Prompt Service (`services/persona-prompt-service`)](file:///home/venus/afri-wealth-ai-mentor/services/persona-prompt-service)**
  - Houses the canonical CHIOMA JSON profile (`data/chioma_profile.v1.json`), JSON Schema (`data/schemas/persona_profile.schema.json`), and prompt builder (`app/prompts.py`).
