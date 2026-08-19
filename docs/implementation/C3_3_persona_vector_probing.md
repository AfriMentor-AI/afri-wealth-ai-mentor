# Persona Vector Probing — Card C3.3

## Overview

The AfriMentor evaluation suite has three layers (see
`research/afrimentor-Research-paper/docs/paper-scope-decision.md`): psychometric
trait-fit, behavioral consistency (card **C3.2**), and **latent-space probing**.
Card **C3.3** delivers that third layer.

The behavioral metrics (`evaluation/metrics.py`, LLM-as-judge) and the C3.2
consistency job measure the persona from the model's **outputs** — what it says.
C3.3 measures it from the model's **internal activations** — how it represents the
persona before it speaks. This is a white-box complement to the black-box
behavioral scores, following the two papers the related-work section already
cites: Chen et al. 2025, *Persona Vectors: Monitoring and Controlling Character
Traits in Language Models*, and Frising et al. 2025, *Linear Personality Probing
and Steering in LLMs: A Big Five Study*.

Its acceptance criterion:

> **Per-trait persona vectors are extracted from model activations via contrastive
> pairs, and a linear probe scores a response's trait expression from its
> activations — reported with a separation diagnostic and logged alongside the
> behavioral metrics.**

The contrastive material is free: the C1.4 CHIOMA target profile
(`services/persona-prompt-service/data/chioma_profile.v1.json`) already lists, per
trait, `markers` (phrases that express the trait) and `counter_markers` (phrases
that express its opposite). Those are exactly the positive/negative sides of a
diff-of-means — no labels to collect, no new data pipeline.

### The gap this card closed

| | Before C3.3 | After C3.3 |
|---|---|---|
| Behavioral persona scoring (LLM-judge) | ✅ (`metrics.py`) | ✅ |
| Behavioral consistency over sessions | ✅ (C3.2) | ✅ |
| **Latent-space persona vectors** | ❌ | ✅ (per trait, per layer) |
| **Activation-level trait probe** | ❌ | ✅ (projection score) |
| **Separation diagnostic (vectors are real)** | ❌ | ✅ (held-out acc + margin) |
| **Logged beside behavioral metrics in MLflow** | ❌ | ✅ (`probe_*` keys) |

## Architecture

Two decoupled halves, so the model-heavy half stays on the GPU and the numeric
half stays testable on a bare CPU:

```
probe.py  (thin runner — GPU node only)
  │  one MLflow run — C3 params + probe diagnostic attach here
  │
  ├─► torch/CUDA available?   no ─► return None            ← safe no-op off-GPU
  │
  ├─► load_persona_profile(chioma_profile.v1.json)         markers / counter_markers
  ├─► build_contrastive_pairs(profile)                     per-trait pos/neg + held-out split
  ├─► HFActivationExtractor(base, adapter)  :: ActivationFn text -> (n_layers, hidden)
  │
  ├─► extract_persona_vectors(pairs, extract_fn)           v = normalize(mean(act⁺) − mean(act⁻))
  │        └─ PersonaVectorSet {trait: (n_layers, hidden)}
  ├─► probe_separation(vectors, pairs, extract_fn)         held-out acc + margin / layer → best_layer
  ├─► log_probe_to_mlflow(report)                          probe_sep_acc_*, probe_best_layer_*
  └─► PersonaVectorSet.save(persona_vectors.npz)           + sidecar .meta.json (steering-ready)
```

### Why an activation seam

`extract_persona_vectors`, `probe_separation`, and `PersonaProbe` all take an
`ActivationFn: (text) -> ndarray (n_layers, hidden_dim)`. In a real run it is an
`HFActivationExtractor` that loads the 7B model on the GPU and mean-pools the
hidden states of a forward pass. In tests it is a trivial fake that plants a known
direction at one layer. This single seam lets the entire extract → probe →
diagnose pipeline — the part the AC is about — be verified on numpy alone, with no
model, GPU, or network. It mirrors the `GenerateFn` seam C3.1 uses for the
checkpoint-eval harness.

### Why diff-of-means over marker templates

Markers are short phrases. Each is dropped into a small set of neutral carrier
sentences (`CARRIER_TEMPLATES`), and — crucially — positives and negatives use the
**identical** carriers. The carrier's own activation is therefore shared across
both classes and cancels in the difference of class means, leaving the trait
content as the persona direction. This is the label-free v1 estimator; a
supervised logistic-regression probe is a documented future refinement.

## Components

### `research/evaluation/persona_probe.py` (new, shared)

The reusable probing module (numpy core + lazy-torch extractor). C4 can reuse it
verbatim to probe its RLHF policy.

- `load_persona_profile(path)` — the C1.4 profile, with a built-in `_FALLBACK_PROFILE`
  (two traits) so the pipeline always has contrastive material.
- `build_contrastive_pairs(profile, templates, heldout_fraction, max_markers)` —
  per-trait `{train:{positive,negative}, heldout:{positive,negative}}`; splits
  markers into a train slice (builds the vector) and a held-out slice (validates
  it), expands each phrase across carriers. Traits lacking either side are skipped
  with a warning.
- `extract_persona_vectors(pairs, activation_fn, ...)` → `PersonaVectorSet` — the
  per-trait, per-layer diff-of-means, unit-normalized.
- `PersonaVectorSet` — `{trait: (n_layers, hidden_dim)}` + metadata + `best_layer`;
  `save`/`load` via `.npz` + sidecar `.meta.json`.
- `PersonaProbe` — `score_trait` / `score_all`: projection of a response's pooled
  activation onto the unit persona vector (defaults to each trait's `best_layer`).
- `probe_separation(...)` / `select_best_layers(...)` — held-out separation
  (accuracy + margin) per trait/layer; picks and records the most discriminative
  layer. Falls back to the train slice (flagged) when a trait has too few markers
  to hold any out.
- `log_probe_to_mlflow(report)` — `probe_sep_acc_<trait>`, `probe_sep_margin_<trait>`,
  `probe_best_layer_<trait>`, and run-level `probe_sep_acc_mean` / `_margin_mean`.
- `HFActivationExtractor(base_model_id, adapter_path, pooling, ...)` — the real
  `ActivationFn`; torch/transformers/peft imported **lazily** in `_ensure_loaded`,
  `output_hidden_states=True`, mean- (or last-) pools token states per layer.

### `research/experiments/03_contrastive_learning/probe.py` (new)

Thin GPU-node CLI: config → pairs → extractor → vectors → separation → save → log,
in a single MLflow run. GPU-gated (returns `None`, no CPU 7B load, when CUDA is
absent — the same discipline as C3.1's `train()`). A **separate** entry point from
`run.py` so the probing layer neither depends on nor conflicts with the DPO
training/eval runner. CLI: `--config`, `--adapter`, `--out`.

### `research/configs/c3_contrastive_learning.yaml` (updated)

Added a `probing:` block: `profile_path`, `pooling` (`mean`|`last`),
`heldout_fraction`, `max_markers`, `max_length`, and the `output_path` for the
saved vectors.

## MLflow comparability

The probe diagnostic logs into the same C3 run as the DPO metrics and (via C3.1)
the behavioral `avg_*` suite, so a dashboard can line the latent layer up against
the behavioral one:

- per trait: `probe_sep_acc_<trait>`, `probe_sep_margin_<trait>`, `probe_best_layer_<trait>`
- per run: `probe_sep_acc_mean`, `probe_sep_margin_mean`
- the `persona_vectors.npz` (+ `.meta.json`) attached as a run artifact

## GPU runbook

Extracting activations from the real 7B model requires CUDA and is **not** done in
the dev environment. On an ephemeral GPU node (RunPod / EC2 `g5.xlarge`):

```bash
cd research
pip install -r requirements.txt -r requirements-gpu.txt
export MLFLOW_TRACKING_URI=...        # e.g. the docker-compose mlflow service

# Probe the base model (or pass --adapter to probe the C3 DPO checkpoint)
python experiments/03_contrastive_learning/probe.py \
    --adapter experiments/03_contrastive_learning/checkpoints/final

# Inspect: separation accuracy per trait, best layer, and the saved vectors
mlflow ui --backend-store-uri "$MLFLOW_TRACKING_URI"
```

## Testing

Fully offline — no GPU, no network, no model. Activations come from a deterministic
fake that plants a known direction at one layer; `mlflow`/`torch` are stubbed
(torch reports no CUDA) only if absent.

```bash
cd research
python -m pytest evaluation/tests/ -v
# 15 passed
```

Coverage:

- **Profile** — real CHIOMA profile loads; missing file → built-in fallback.
- **Pairs** — real-profile pairs (pos/neg disjoint, non-empty); templating expands
  markers across carriers; traits missing a side are skipped; bad `heldout_fraction`
  rejected.
- **Extraction** — diff-of-means recovers the planted direction (cosine > 0.9);
  every layer row is unit-norm.
- **Probe** — projection sign follows trait expression; unknown trait raises.
- **Separation** — finds the planted layer with accuracy 1.0 and positive margin,
  persists `best_layer`; falls back to the train slice when no held-out exists.
- **Persistence** — `.npz` + metadata save/load round-trip preserves vectors and
  `best_layer`.
- **MLflow** — the expected `probe_*` keys are logged.
- **Runner** — `run()` takes the safe no-GPU path (returns `None`).

## Environment constraints & status

Implemented in the dev environment, which has **no GPU** and does not carry the ML
stack (torch / transformers / peft). Per that constraint:

- The **probing pipeline is complete and verified** offline (15 tests) — this is
  the code path the acceptance criterion describes. The numeric core (extraction,
  probe, separation, persistence) is pure numpy and runs anywhere.
- The **real 7B activations are extracted later on a GPU node** via the runbook
  above. `probe.run()` is a safe no-op here; it never loads a model on CPU and
  never fabricates vectors.
- The extract → probe → diagnose path was validated end-to-end with an **injected
  activation function** standing in for the model, proving the pipeline the real
  hidden states will flow through unchanged on the GPU node.

## Acceptance Criteria Met

- [x] Per-trait, per-layer persona vectors extracted via contrastive diff-of-means
      from the CHIOMA profile's `markers` / `counter_markers`.
- [x] Linear probe scores a response's per-trait expression from its activations;
      best layer selected by held-out separation.
- [x] Separation diagnostic (held-out accuracy + margin) and probe metrics logged
      to MLflow under stable `probe_*` keys, beside the behavioral suite.
- [x] `HFActivationExtractor` real path implemented with lazy imports; the module
      imports and runs on numpy alone with torch absent.
- [x] CPU-only offline test suite (torch/mlflow stubbed); self-contained, with no
      dependency on the unmerged C3.1 code.
- [ ] Real 7B persona-vector extraction on a GPU node — deferred to a GPU execution
      run per the environment constraint above (runbook provided).

## References

- Card C1.4: CHIOMA target personality profile (`chioma_profile.v1.json`) — the
  markers / counter_markers that seed the contrastive pairs
- Card C1.3: personality-consistency metric suite (psychometric trait-fit layer)
- Card C3.1: contrastive-learning checkpoint eval — the `ActivationFn`/`GenerateFn`
  seam pattern and MLflow-logging convention this card mirrors
- Card C3.2: behavioral consistency metrics (the behavioral layer this complements)
- `research/evaluation/metrics.py` — the black-box behavioral suite
- Chen et al. 2025 — *Persona Vectors: Monitoring and Controlling Character Traits*
- Frising et al. 2025 — *Linear Personality Probing and Steering in LLMs: A Big Five Study*
