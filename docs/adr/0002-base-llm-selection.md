# ADR 0002 — Base LLM Selection & Hosting Strategy

- **Status:** Approved
- **Card:** D1.1 (Sprint 1)
- **Date:** 2026-07-28
- **Last Updated:** 2026-07-31 (Sprint 1 implementation findings)
- **Author:** Daniel Kusi Boateng (Lead Software Engineer / ML Engineer)
- **Approvers:** Olusegun (Cost / Infra), Chukwuebuka (ML Feasibility)
- **Depends on:** ADR 0001 (service boundaries — chat-orchestration-service)

---

## 1. Context & Business Need

AfriMentor AI requires a base LLM for two distinct operational requirements:

1. **User-Facing Mentorship Engine** — real-time interactive chat with persona-driven
   mentors; p95 response time < 3 s.
2. **Academic & Research Pipeline (Proposal 1)** — parameter-efficient fine-tuning
   (LoRA/QLoRA) and DPO/RLHF alignment experiments to evaluate persona-constrained
   LLM behaviour.

---

## 2. Candidate Options Evaluated

### Option A — Proprietary Commercial APIs (Claude 3.5 Sonnet / GPT-4o)

| Dimension | Detail |
|---|---|
| p95 Latency | ~1.5 s – 2.8 s (150–200 token responses) |
| Cost | $2.50 – $3.00 / 1 M tokens |
| Data Residency | US/EU cloud nodes; no sub-Saharan African endpoints |
| Fine-Tuning | Restricted — no custom RLHF loss functions or adapter extraction |

### Option B — Managed Serverless Open-Weight APIs (Groq / Together AI — Llama 3 8B / Qwen 2.5 7B)

| Dimension | Detail |
|---|---|
| p95 Latency | ~0.4 s – 0.9 s (vLLM/LPU clusters) |
| Cost | $0.15 – $0.20 / 1 M tokens (10×–15× cheaper than Option A) |
| Data Residency | US/EU cloud; strict data non-retention policies |
| Fine-Tuning | Inference API only; custom LoRA/DPO adapters can be served via custom vLLM |

### Option C — Self-Hosted Open-Weight Model (vLLM on AWS EC2 g5.xlarge / RunPod A10G)

| Dimension | Detail |
|---|---|
| p95 Latency | ~1.2 s – 2.0 s (continuous batching via vLLM) |
| Cost | ~$0.75 – $1.00 / hr fixed (~$540 – $720 / month per 24/7 GPU node) |
| Data Residency | Native — AWS Cape Town (af-south-1) |
| Fine-Tuning | 100 % unconstrained — full QLoRA, DPO, PPO pipelines |

---

## 3. Evaluation Matrix

| Criteria | Requirement | Option A | Option B | Option C |
|---|---|---|---|---|
| p95 Latency | < 3.0 s | ~2.0 s ✓ | ~0.6 s ✓ (best) | ~1.5 s ✓ |
| Operational Cost | Minimal Sprint 1–3 | High ($2.50+/M tokens) | Ultra-low ($0.18/M tokens) | Fixed ~$720/mo |
| Data Residency | African user data | US/EU cloud | US/EU cloud | AWS af-south-1 ✓ |
| Fine-Tuning / RLHF | Required (Proposal 1) | Minimal / closed | API inference only | Full support ✓ |
| DevOps Effort | Minimal | ~1 hr (API key) | ~1 hr (API key) | High (GPU/container mgmt) |

---

## 4. Decision — Hybrid Two-Tier Strategy

**Approved.**

### Tier 1 — Production Runtime Inference (Sprint 1–3)

The live application runtime currently calls an OpenAI-compatible provider over
`LLM_BASE_URL` / `LLM_MODEL` environment variables. The default configuration in
this repo is the Groq endpoint (`https://api.groq.com/openai/v1`) with
`openai/gpt-oss-20b` as the active runtime model.

The original sprint strategy still distinguishes between:
- **runtime provider**: Groq / Together AI / local vLLM through a standard
  OpenAI-compatible API; this is what `chat-orchestration-service` actually calls
- **research checkpoint artifacts**: the canonical SFT adapter
  `AfriMentor/chioma-sft-v1` and the DPO/RLHF adapters
  `AfriMentor/chioma-dpo-v1` and `AfriMentor/chioma-rlhf-v1`. They are published
  for auditability and future hosted deployment but are not directly imported by
  the FastAPI service. All three use the Qwen base-model family.

The original rationale for Qwen 2.5 7B as the research base remains valid, but the
current live runtime is GPT-OSS through Groq. A Qwen checkpoint becomes a runtime
option only after deploying the Qwen base plus adapter behind an OpenAI-compatible
endpoint.

Rationale for Qwen 2.5 7B as primary target model for research hosting:

- **Structured JSON output** — superior strict JSON schema enforcement and function
  calling; critical for rendering interactive UI widgets and milestone action cards
  (contract G1.3). Reduces TypeScript parsing errors in the Next.js frontend.
- **Multilingual & regional vernacular** — trained on 29+ languages; significantly more
  resilient with West African Pidgin, Twi/Swahili loanwords, and local business
  terminology than Llama 3.1 (predominantly English-trained).
- **Apache 2.0 licence** — zero commercial restrictions for deployment, fine-tuning,
  weight redistribution, and research publication. Llama 3.1 carries Meta's custom
  licence with usage caps and attribution clauses.
- **Mathematical reasoning** — higher scores on HumanEval, MATH, and GSM8K benchmarks;
  directly benefits financial mentorship use cases (profit margins, unit economics,
  inventory math).

Rationale for Llama 3.1 8B as secondary/fallback:

- Slightly punchier conversational persona roleplay tone.
- Broad community support and tooling.
- Both models share identical OpenAI-compatible API schemas on Groq/Together AI —
  switching is a single config-line change in `chat-orchestration-service`.

#### Sprint 1 Implementation Finding — Groq Model Availability

During Sprint 1 implementation and live testing of `chat-orchestration-service`,
**Qwen/Qwen2.5-7B-Instruct was found to be unavailable on Groq's platform**.
Groq's available model catalogue (verified 2026-07-31) does not include Qwen 2.5 7B.

Available models on Groq at time of writing:

| Model ID | Notes |
|---|---|
| `llama-3.1-8b-instant` | Active Sprint 1 model — fastest on Groq free tier |
| `llama-3.3-70b-versatile` | Available but overkill for Sprint 1 |
| `qwen/qwen3.6-27b` | Qwen available but larger/slower than target |
| `whisper-large-v3` | STT only — for voice-service |

**Interim decision:** `llama-3.1-8b-instant` is the active model for Sprint 1–3 on
Groq. This is the ADR-0002 fallback model and performs well — live test confirmed
~0.3 s p95 response time and high-quality Chioma persona output.

**Qwen 2.5 7B remains the primary target model** and will be served via **Together AI**
(`Qwen/Qwen2.5-7B-Instruct`) when Sprint 2 frontend integration begins, or when Groq
adds it to their catalogue. The `LLM_BASE_URL` and `LLM_MODEL` config vars in
`chat-orchestration-service` make this a zero-code switch.

Model comparison:

| Feature | Qwen/Qwen2.5-7B-Instruct | meta-llama/Llama-3.1-8B-Instruct |
|---|---|---|
| Context Window | 128 k tokens | 128 k tokens |
| JSON & Function Calling | ⭐⭐⭐⭐⭐ Exceptional | ⭐⭐⭐⭐ Very Good |
| Multilingual / Local Slang | ⭐⭐⭐⭐⭐ Superior | ⭐⭐⭐ Standard English |
| Persona Roleplay Tone | ⭐⭐⭐⭐ Grounded/Direct | ⭐⭐⭐⭐⭐ Slightly punchier |
| Fine-Tuning | Fully supported (Apache 2.0) | Fully supported (Meta licence) |
| Serverless API Latency | ~0.4 s p95 | ~0.6 s p95 |
| Licence | Apache 2.0 | Meta Custom Licence |

This guarantees sub-second response times (< 1.0 s p95), minimal DevOps setup, and
near-zero cost during initial frontend and RAG development.

### Tier 2 — Research & Fine-Tuning Execution (Sprint 4–5)

Rent **on-demand ephemeral cloud GPUs** (RunPod / AWS EC2 g5.xlarge with NVIDIA A10G)
strictly during fine-tuning passes and RLHF alignment runs. Trained LoRA/DPO adapter
weights will be:

1. Published to Hugging Face.
2. Quantized to 4-bit / GGUF / AWQ.
3. Deployed to custom vLLM containers for evaluation.

---

## 5. Consequences

**Positive:** sub-second latency in Sprint 1–3 at near-zero cost; no GPU management
overhead during frontend/RAG development; full fine-tuning freedom in Sprint 4–5 without
paying for idle GPU time; Apache 2.0 licence removes legal friction for research
publication; `llama-3.1-8b-instant` on Groq confirmed ~0.3 s p95 in live testing.

**Negative / trade-offs:** US/EU data residency in Tier 1 (mitigated by provider
non-retention policies; full residency compliance deferred to Tier 2 / prod hardening via
AWS af-south-1); dependency on third-party API availability during Sprint 1–3;
Qwen 2.5 7B unavailable on Groq — Together AI required to serve the primary model
(zero-code switch via `LLM_BASE_URL` env var).

**Follow-up ADRs:** 0003 RAG embedding model selection; 0004 multi-region data residency
& AWS af-south-1 migration criteria.

---

## 6. Sign-off

| Reviewer | Role | Status |
|---|---|---|
| Olusegun | Product Owner / Backend Lead (Cost & Infra) | ✅ Approved |
| Chukwuebuka | Lead ML Engineer (ML Feasibility) | ✅ Approved |
| Daniel Kusi Boateng | Lead Software Engineer / ML Engineer (Author) | ✅ Approved |
