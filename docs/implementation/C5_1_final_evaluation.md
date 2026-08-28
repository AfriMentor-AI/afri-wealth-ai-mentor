# Final Full Evaluation Run — Card C5.1

## Overview

Card C5.1 asks for the final, frozen evaluation across all 4 alignment
conditions (automatic metrics + human evaluation panel), locked as the
paper's canonical dataset. This document records what's built, what's real,
and what's still outstanding — the acceptance criterion ("final results
frozen and tagged") is **not yet met**, and this doc says exactly why, so it
isn't mistaken for done.

## What was missing going in

- `comparative_eval.py` (card D4.3) already runs C1–C4 through the shared
  metric suite, but only C1 (live Groq) and C2 (a recorded past Kaggle SFT
  run) produce real numbers. C3 and C4 have no confirmed trained checkpoint
  on HuggingFace Hub (`afrimentor/chioma-dpo-v1`, `afrimentor/chioma-rlhf-v1`)
  in this environment, so the harness falls back to literature-extrapolated
  estimates, clearly labeled `estimated_dpo_extrapolation` /
  `estimated_rlhf_extrapolation` (see `comparative_eval.py` and
  `results_table.py`'s footnote-marker convention — this honesty pattern
  predates this card and is preserved, not invented, here).
- There was no human-evaluation-panel infrastructure at all — no rubric, no
  rater tool, no aggregation.
- There was no "frozen and tagged as canonical" mechanism — no git-tag
  convention, no immutable results snapshot, nothing that would stop
  `comparative_results.json` from being silently overwritten by a later run.

## What this card adds

### 1. Freeze / tag mechanism — `evaluation/freeze_results.py`

Snapshots `comparative_results.json` (+ `safety_results.json` +
`human_eval_results.json`, when present) into an immutable, versioned
directory (`evaluation/results/canonical/<version>/`) with a manifest that
records git commit/branch, per-condition provenance (real vs. estimated,
read from the `source` field those tools already stamp), and per-condition
human-eval coverage. It computes an explicit status:

| Status | Meaning |
| :--- | :--- |
| `PUBLICATION_READY` | Every condition is real and has human ratings on file. |
| `PARTIAL_CONTAINS_ESTIMATES` | One or more conditions are literature estimates, not measurements. |
| `PARTIAL_MISSING_HUMAN_EVAL` | All conditions real, but human ratings outstanding. |
| `PARTIAL_ESTIMATES_AND_MISSING_HUMAN_EVAL` | Both gaps present. |
| `NO_COMPARATIVE_RESULTS` | Nothing to freeze yet. |

`--tag` creates a **local** git tag `eval-freeze-<version>` (never pushed by
the tool itself — that's a deliberate human decision). A freeze never
retroactively upgrades a result's honesty: it only reports what
`comparative_eval.py` and `human_eval_aggregate.py` already recorded.

### 2. Human-evaluation panel scaffolding

- **`evaluation/human_eval_rubric.md`** — the protocol: why a human panel is
  needed alongside the LLM-as-judge automatic score, the same 5-dimension
  rubric plus a holistic overall-quality item, blinding procedure, rater
  count (≥2 per sample), and the honesty contract (a condition with no
  ratable text is `pending_human_ratings`, never filled with a guess).
- **`evaluation/human_eval_sampler.py`** — reads `comparative_results.json`,
  pulls every `(user_message, response)` pair that has real generated text
  (only live-run conditions have any — this is also why `comparative_eval.py`
  now records `user_message`/`response` on every row, a small addition made
  as part of this card), shuffles and relabels with opaque sample ids, and
  writes a rater-facing `rating_packet.csv` plus a private `rating_key.json`
  raters never see.
- **`evaluation/human_eval_aggregate.py`** — ingests one or more completed
  rater CSVs, unblinds via the key, computes per-condition means in the same
  shape `comparative_results.json` uses, and flags samples where raters
  disagree by ≥2 points on the 1–5 overall-quality item rather than quietly
  averaging the disagreement away.

**What this does not do**: actually run the human panel. That requires real
raters (Grace's field team or another qualified reviewer) using
`rating_packet.csv` — no agent or script can substitute for a human judgment
call without fabricating the paper's data.

### 3. Tests

`evaluation/tests/test_freeze_results.py`,
`test_human_eval_sampler.py`, `test_human_eval_aggregate.py` — 16 new tests,
fully offline (no GPU, no network), covering: status computation for every
combination of real/estimated × rated/pending, that an estimated condition
is never asked for human ratings (there's no text to rate), immutability of
a freeze, blinding determinism, and disagreement flagging.

## Current honest state

Running `comparative_eval.py --sample-size 3 --skip-c2 --skip-c3 --skip-c4`
(C1 only — this environment has no GPU for C2–C4 checkpoint inference, and
C3/C4 adapters aren't confirmed to exist) and then `freeze_results.py
--version v1-partial` produces a freeze whose status is
**`PARTIAL_MISSING_HUMAN_EVAL`**: C1 is labeled `live_groq` (real, not
estimated), but see the critical finding below before trusting that label —
and no human ratings exist yet. See
`evaluation/results/canonical/v1-partial/manifest.json` for the exact
snapshot (gitignored — a local artifact, not committed; `results/` is
excluded repo-wide per `.gitignore:35`).

## Critical finding: C1's "live" output is not usable as-is

Storing `response`/`user_message` on every row (this card's small addition to
`comparative_eval.py`) immediately surfaced a bug invisible in every prior
run: **`qwen/qwen3.6-27b` (the `.env` `LLM_MODEL`, the Groq C1 proxy since
`llama-3.1-8b-instant` was retired) is a reasoning model that emits its
`<think>...</think>` chain-of-thought inline in `content`**, with no separate
`reasoning_content` field on this endpoint. At the harness's default
`max_tokens=512` it hits `finish_reason: length` **while still inside the
`<think>` block, on every sample tested** — including a trivial "say hello in
one sentence" smoke test, confirmed 100% reproducible. There is no post-think
answer to extract; the model never reaches one within budget.

**Consequence:** every C1 `live_groq` result — in this run, and very likely
every prior comparative/safety run against this model — has been the
automatic judge scoring an incomplete internal reasoning trace, not the
persona's actual response. The unusually low/erratic composite scores in this
run (0.525, 0.265, 0.060) are consistent with that, not with real
persona-adherence variance.

This is a methodology decision, not a bug I fixed silently: raising
`LLM_MAX_TOKENS` enough for the model to finish reasoning, switching to a
non-reasoning model for the harness, or checking whether Groq exposes a
reasoning-suppression parameter for this model are all real options with
different cost/quality tradeoffs, and changing it changes the meaning of
every past `live_groq` result already in the repo — worth a decision, not an
assumption. **The generated `rating_packet.csv` from this run should not be
sent to human raters as-is**; it contains truncated reasoning traces, not
answers.

## What's still blocking a real C5.1 completion

0. **Fix the C1 reasoning-truncation bug (see above) before trusting any
   `live_groq` result**, including the ones already in this repo from
   D4.3/C4.3. This blocks C1 being genuinely "real," not just C3/C4.
1. **C3/C4 real checkpoints.** Someone needs to actually run the GPU DPO/RLHF
   training jobs (`research/experiments/03_contrastive_learning/run.py`,
   `04_rlhf_preference_opt/run.py`) on a cloud GPU node and publish the
   adapters, then re-run `comparative_eval.py` so C3/C4 stop being estimates.
2. **A real human-evaluation panel.** `human_eval_rubric.md` and the
   sampler/aggregator are ready to use the moment `comparative_eval.py` has
   produced ratable text for a condition — but actual human raters (2+ per
   sample) need to do the rating.
3. **G3.4** (a listed dependency for this card) does not exist anywhere in
   this repository — no commit, doc, or card with a "G" prefix. Treated as
   external/not blocking per product-owner direction, but worth confirming
   its actual status doesn't reintroduce a real dependency later.
4. Once 1 and 2 land, re-run `freeze_results.py --version v2 --tag` — it
   will only report `PUBLICATION_READY` when every condition is genuinely
   measured and rated, which is the actual bar this card's acceptance
   criterion sets.

## References

- `research/evaluation/comparative_eval.py` — card D4.3, the automatic-metrics harness this extends
- `research/evaluation/results_table.py` — the estimated-source footnote convention this reuses
- `research/evaluation/safety_eval.py` — the `pending_generation` honesty-contract pattern this mirrors
- `research/README.md` — the 4 alignment conditions (C1–C4) definition
