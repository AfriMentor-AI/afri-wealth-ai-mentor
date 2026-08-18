# Persona-Aware Contrastive Learning — Card C3.1

## Overview

Condition **C3** is the third of the four alignment conditions. It applies
**Direct Preference Optimization (DPO)** — a PCL-inspired contrastive-learning
objective — over `(chosen, rejected)` persona response pairs, warm-starting from
the C2 SFT checkpoint, to sharpen consistent use of each persona's role
characteristics.

Card **C3.1** delivers the piece that makes C3 *comparable* to the other
conditions. Its acceptance criterion is:

> **Contrastive-learning checkpoint produced and evaluated against the same
> metric suite.**

Training a DPO adapter was already scaffolded. What was missing — and what this
card adds — is the **evaluation half**: after training, generate from the tuned
checkpoint and score it with the **shared** evaluation suite
(`evaluation/metrics.py`), logging the **same MLflow metric keys** that C1 and C2
log. Only then do the three conditions line up as comparable rows in the tracker.

### The gap this card closed

The previous runner logged **only `trainer.evaluate()`** — the DPO loss / reward
margins. Those measure preference optimization, not persona quality, and share no
keys with C1/C2, so C3 could not be compared against them. The runner now runs
the full persona metric suite on the trained checkpoint and logs
`avg_persona_adherence … avg_composite_score` into the same run.

| | Before C3.1 | After C3.1 |
|---|---|---|
| Trains DPO adapter | ✅ | ✅ |
| Logs DPO loss | ✅ (`dpo_loss`, margins) | ✅ (namespaced `dpo_*`) |
| **Scores persona metric suite** | ❌ | ✅ (`avg_*`, per-persona composites) |
| **Comparable to C1/C2 in MLflow** | ❌ | ✅ (identical metric keys) |

## Architecture

Two stages, deliberately decoupled so the expensive half stays on the GPU and the
comparable half stays testable:

```
run(config, do_train, do_eval, adapter_path, generate_fn)
  │   one MLflow run — C3 params + DPO metrics + metric suite all attach here
  │
  ├─► train(cfg)                         [GPU node only]
  │     ├─ _gpu_available()?  no ─► return (None, {})   ← safe no-op off-GPU
  │     ├─ base Qwen2.5-7B + C2 SFT adapter  (4-bit QLoRA)
  │     ├─ DPOTrainer over dpo_train.jsonl  (empty val split → in-loop eval off)
  │     ├─ save adapter → checkpoints/final
  │     └─ return (adapter_path, dpo_* loss metrics)
  │
  └─► evaluate(cfg, adapter_path, generate_fn)     ← THE acceptance criterion
        ├─ load_eval_samples(sample_size)          shared sft_test.jsonl split
        ├─ generate_fn := HFCheckpointGenerator(base, adapter)   [GPU]
        │                 └─ or an injected fake                 [tests]
        └─ evaluate_checkpoint(generate_fn, samples)
              ├─ per sample: render persona prompt → generate → evaluate_response
              ├─ log_eval_to_mlflow(step=i)        per-sample metrics
              └─ log avg_* aggregates + per-persona composites   ← same keys as C1
```

### Why a generation seam

`evaluate_checkpoint` takes a `generate_fn: (system_prompt, user_message) -> str`.
In a real run it is a `HFCheckpointGenerator` that loads the 7B base + adapter on
the GPU. In tests it is a trivial function returning a fixed string. This is the
single seam that lets the entire scoring/aggregation/logging pipeline — the part
the AC is about — be verified on a bare CPU interpreter without a model.

## Components

### `research/evaluation/checkpoint_eval.py` (new, shared)

The reusable "score a *trained* checkpoint against the suite" harness. C4 (RLHF)
should reuse it verbatim.

- `load_eval_samples(sample_size, splits_dir, eval_file)` — the same held-out
  `sft_test.jsonl` C1 uses, normalised to `{user, reference, persona, …}`; one
  synthetic sample per persona as a fallback so the harness always runs.
- `render_system_prompt(persona_slug)` — the D1.3 persona prompt (fine-tuning
  reinforces the persona, it does not remove the prompt at inference); local
  fallback if the persona service is unavailable.
- `avg_scores(rows)` — mean of every numeric field.
- `evaluate_checkpoint(generate_fn, samples, system_prompt_fn, log_to_mlflow)` —
  generate → `evaluate_response` → per-sample + aggregate MLflow logging with the
  **C1/C2 keys**. Returns the aggregate dict.
- `HFCheckpointGenerator(base_model_id, adapter_path, …)` — real generator; torch
  / transformers / peft imported **lazily**, so importing this module costs
  nothing on CPU.

### `research/experiments/03_contrastive_learning/run.py` (rewritten)

- `train(cfg) -> (adapter_path | None, dpo_metrics)` — GPU-gated DPO. Returns
  `(None, {})` when no CUDA is present (no crash, no CPU 7B load). Handles the
  **empty validation split** (`dpo_val.jsonl` is legitimately 0 lines today) by
  disabling in-loop eval instead of letting `datasets` choke.
- `evaluate(cfg, adapter_path, generate_fn) -> agg` — the metric-suite stage.
- `run(config, do_train, do_eval, adapter_path, generate_fn) -> results` — opens
  a single MLflow run, logs C3 params, trains (optional), then evaluates. Returns
  `{condition_id, trained, adapter_path, dpo_eval, eval_metrics}`.
- CLI: `--config`, `--eval-only`, `--adapter PATH`.

### `research/configs/c3_contrastive_learning.yaml` (updated)

Added under `evaluation`: `sample_size` (100), `eval_split` (`sft_test.jsonl`),
`max_new_tokens`, and `temperature: 0.0` (greedy — a comparison point must not
carry sampling noise, matching the C2.3 baseline convention).

## MLflow comparability

`evaluate_checkpoint` logs exactly what C1's runner logs, so a dashboard or query
can put the conditions side by side:

- per sample (`step=i`): `persona_adherence`, `cultural_fluency`,
  `anti_dependency`, `financial_accuracy`, `urgency`, `rouge_l`,
  `bert_score_f1`, `composite_score`
- per run: `avg_persona_adherence` … `avg_composite_score`, and
  `avg_composite_<persona>` for each persona seen
- C3-only extras: `dpo_*` loss metrics and the C3 params (`condition_id=C3`,
  `dpo_beta`, `loss_type`, `sft_checkpoint`, …)

`evaluation.compare_against` in the config points at C2, the warm-start parent.

## GPU runbook

Training the real 7B checkpoint requires CUDA and is **not** done in the dev
environment. On an ephemeral GPU node (RunPod / EC2 `g5.xlarge`):

```bash
# 1. Environment (CUDA deps live in requirements-gpu.txt — never install locally)
cd research
pip install -r requirements.txt -r requirements-gpu.txt

# 2. Credentials for the LLM-as-judge (Groq) + MLflow backend
export LLM_API_KEY=...                       # judge client (evaluation/metrics.py)
export MLFLOW_TRACKING_URI=...               # e.g. the docker-compose mlflow service

# 3. Prerequisites
#    - The C2 SFT adapter must exist at model.sft_checkpoint (warm start).
#    - dpo_train.jsonl must be populated; dpo_val.jsonl may be empty (handled).

# 4. Train + evaluate in one run
python experiments/03_contrastive_learning/run.py

# 5. Or re-evaluate an existing adapter without retraining
python experiments/03_contrastive_learning/run.py --eval-only \
    --adapter experiments/03_contrastive_learning/checkpoints/final

# 6. Inspect / compare against C1 & C2
mlflow ui --backend-store-uri "$MLFLOW_TRACKING_URI"
```

## Testing

Fully offline — no GPU, no network, no model. `torch` is stubbed to report no
CUDA, `mlflow`/`openai` are mocked, generation is injected, and the LLM judge is
patched to a fixed score.

```bash
cd research
python -m pytest experiments/03_contrastive_learning/tests/ -v
# 15 passed
```

Coverage:

- **Eval loader** — synthetic fallback, sample-size cap, real-split path.
- **Aggregation** — numeric means, non-numeric fields ignored, empty input.
- **`evaluate_checkpoint`** — generates once per sample; composite honours the
  rubric weights; logs `avg_composite_score` / `avg_persona_adherence` and one
  per-sample metric batch per sample.
- **`train()`** — returns `(None, {})` on a no-GPU host without importing the
  training stack.
- **`run()`** — eval-only returns the metric suite; C3 params logged; the
  comparable `avg_composite` key is logged; a skipped (no-GPU) train still
  evaluates when a generator is injected.
- **Config** — eval + DPO keys present; scored dimensions equal the C1/C2 rubric.

## Environment constraints & status

This card was implemented in the dev environment, which has **no GPU** and does
not carry the CUDA training stack (torch / trl / peft / bitsandbytes). Per that
constraint:

- The **pipeline and the evaluation wiring are complete and verified** offline
  (15 mocked tests) — this is the code path the acceptance criterion describes.
- The **real 7B DPO checkpoint is produced later on a GPU node** via the runbook
  above. `train()` is a safe no-op here; it does not fabricate a checkpoint.
- The metric-suite eval was validated end-to-end with an **injected generator**
  standing in for the model, proving the scoring/aggregation/MLflow-logging path
  the checkpoint will flow through unchanged on the GPU node.

In short: the AC's *mechanism* — "evaluated against the same metric suite" — is
built and tested; running it on the actual trained weights is a GPU-node
execution step, not a code change.

## Acceptance Criteria Met

- [x] DPO (contrastive-learning) training pipeline implemented, warm-starting
      from the C2 SFT checkpoint, robust to the empty validation split.
- [x] Trained checkpoint **evaluated against the same metric suite** as C1/C2
      (`evaluation/metrics.py`) — persona/cultural/anti-dependency/financial/
      urgency + ROUGE-L/BERTScore + composite.
- [x] Results logged to the experiment tracker with the **same MLflow keys** as
      conditions #1 and #2, for direct comparison (`compare_against: C2`).
- [x] Runner correct/robust: single MLflow run, `--eval-only` re-scoring,
      no-GPU safety, empty-val handling.
- [x] CPU-only offline test suite (torch/trl/mlflow/judge mocked).
- [ ] Real 7B checkpoint produced & scored on a GPU node — deferred to a GPU
      execution run per the environment constraint above (runbook provided).

## References

- Card D3.4: DPO preference-pair dataset (dependency)
- Condition C1: Baseline Prompting (`experiments/01_baseline_prompting/run.py`) —
  the metric-logging pattern C3 mirrors
- Condition C2: Supervised Fine-Tuning (warm-start parent; `compare_against`)
- `research/evaluation/metrics.py` — the shared 5-dimension + reference metric suite
- `research/evaluation/checkpoint_eval.py` — shared post-training eval harness (reused by C4)
- Rafailov et al. 2023 — Direct Preference Optimization
