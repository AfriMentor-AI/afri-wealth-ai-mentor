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
  on HuggingFace Hub (`AfriMentor/chioma-dpo-v1`, `AfriMentor/chioma-rlhf-v1`)
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
estimated) and — as of the fix in the section below — that label is now
trustworthy; no human ratings exist yet. See
`evaluation/results/canonical/v1-partial/manifest.json` for the exact
snapshot (gitignored — a local artifact, not committed; `results/` is
excluded repo-wide per `.gitignore:35`).

## Critical finding: C1's "live" output is not usable as-is (RESOLVED)

**Update:** Fixed. `comparative_eval.py`'s `_run_c1_live` and
`safety_eval.py`'s `make_openai_generator` now pass
`extra_body={"reasoning_format": "hidden"}` on the Groq call, and
`LLM_MAX_TOKENS` was raised from 512 to 4096 (`.env`, `.env.example`,
`docker-compose.yml`). Verified live against Groq: this model burns
**~2000+ tokens on its hidden `<think>` trace before any visible answer**,
even for trivial prompts — 512, 1024, and 2048 all still hit
`finish_reason: length` with an empty `content` once reasoning is hidden;
3072–4096 was reliably enough across tested prompts. A re-run of
`comparative_eval.py --sample-size 3 --skip-c2 --skip-c3 --skip-c4` now
produces clean, real persona responses (composite 0.843 / 0.883 / 0.880 —
consistent, not the erratic 0.525/0.265/0.060 from the truncated-trace runs)
with no `<think>` in `content`.

The same bug existed in production: `chat-orchestration-service/app/llm.py`
calls the identical model with the identical `max_tokens=512` pattern at all
three of its Groq call sites (`chat_completion`, `stream_chat_completion`,
`generate_daily_action_for_user`) — all three now carry the same
`reasoning_format=hidden` fix and the raised token budget.
`generate_daily_action_for_user` additionally had its own independent bug:
its message list was system-role only, which Groq rejects outright
("No user query found in messages"), so every call has been silently
falling back to the stub task since this function was written. Fixed by
splitting it into a proper system/user pair.

**Cost/latency tradeoff, not free**: this model needs ~2000 completion
tokens of hidden reasoning per response regardless of answer length — a
real 4-8x increase in tokens billed and generation latency versus the
512-token budget the D5.2 latency/cost optimization pass tuned around. That
pass's assumptions no longer hold for this model and are worth revisiting
(e.g. evaluating a non-reasoning model) — not done here since it's a
product/quality call, not a mechanical fix, and the available non-reasoning
alternatives on this Groq key (`allam-2-7b`, `groq/compound-mini`) either
have unverified persona/cultural-fluency quality or materially different
runtime behavior (compound models call tools/web-search internally).

**Consequence for existing results**: every prior `live_groq` measurement in
this repo (including anything already merged from D4.3/C4.3) was scoring a
truncated reasoning trace, not a real answer, and should be treated as
invalid — re-run before trusting any of it.

**Update 2 (same day): moved off qwen entirely, onto `openai/gpt-oss-20b`.**
Rather than keep paying the reasoning-trace tax above, tested
`openai/gpt-oss-20b` (also available on this Groq key) as a direct C1
replacement. It has no `<think>`-in-`content` behavior at all — verified
across a trivial prompt and 5 varied financial-advice prompts, `content` is
always the clean final answer, no `reasoning_format` needed. Token cost is
far lower too: a trivial "say hello" used 55 completion tokens (vs.
qwen's ~350 even with reasoning hidden), and 2048 `max_tokens` was
sufficient on every one of 5 varied real dataset prompts (all finished with
`finish_reason: stop`, none truncated) — no need for qwen's 4096.
Composite scores on the 3 samples the judge scored cleanly: 0.740 / 0.770 /
0.883, comparable to qwen's post-fix 0.843 / 0.883 / 0.880. `LLM_MODEL` is
now `openai/gpt-oss-20b` and `LLM_MAX_TOKENS` is `2048` everywhere (`.env`,
`.env.example`, `docker-compose.yml`, `chat-orchestration-service/app/config.py`
default, and the `C1_MODEL_ID`/`C1_MAX_TOKENS` fallback defaults in
`comparative_eval.py`/`safety_eval.py`). The `reasoning_format=hidden`
`extra_body` was left in place at every call site rather than removed — it's
a verified no-op for gpt-oss-20b (confirmed live: no error, param silently
ignored) and guards against this exact bug recurring if `LLM_MODEL` is ever
pointed back at a reasoning model.

Two things noticed during the swap:
- **2 of 5 test samples scored `composite=0.000`** in the comparison run —
  not a gpt-oss-20b quality issue (the underlying persona responses were
  substantive, 1000+ chars, ending cleanly). The LLM-judge itself
  (`metrics.py::score_all_dimensions`) had a hardcoded `max_tokens=512` for
  its own JSON-scoring call, which truncated before it finished emitting the
  closing `}`. **Fixed**: root-caused by direct testing —
  `openai/gpt-oss-120b` (the judge model) spends a variable, *invisible*
  amount of its budget on internal reasoning that never surfaces in
  `content` or `reasoning_content` (confirmed live: the same judge prompt
  used all 512 tokens on one call and only ~475 on another, both mostly
  hidden reasoning, with the visible JSON a small fraction of that). 512 was
  a silent-failure risk, not a safe budget, regardless of which model C1
  uses. Raised to a configurable `_JUDGE_MAX_TOKENS` (`EVAL_JUDGE_MAX_TOKENS`
  env var, default 1536) in `metrics.py`. Re-ran the same 5-sample
  comparison after the fix: all 5 samples scored cleanly (0.670 / 0.305 /
  0.713 / 0.750 / 0.820), zero judge-side failures.
- gpt-oss-20b hit more Groq `429` rate limits than qwen during the same
  5-sample test run, suggesting tighter free-tier limits for this model on
  this key. Not disqualifying, but worth watching if traffic increases.

<details>
<summary>Original finding (for context)</summary>

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

</details>

## C2 checkpoint reconciliation (2026-08-31)

A second, independent C2 SFT run was done this session on Kaggle
(`AfriMentor/chioma-sft-v1` — 3 epochs, plain `SFTTrainer`, no response-loss
masking, 22 pairs) as a reproducibility check against the repo's checked-in
`02_supervised_finetuning/run.py`. Compared against Daniel's own report
(`research/experiments/02_supervised_finetuning/README.md`, cross-referenced
in `docs/implementation/C2_1_supervised_finetuning.md`), which swept 3 vs. 10
epochs and a response-only-masking variant (Unsloth's
`train_on_responses_only`) and reached composite 0.587 at peak / 0.476 on the
22-pair run already recorded as C2 in this repo (`source:
"recorded_kaggle_run"`): **`Danleon56/chioma-sft-v1` stays canonical C2** —
his sweep is more methodologically thorough (response-masking + epoch
search) than this session's single-config run, so there's no basis to
displace the recorded result. `AfriMentor/chioma-sft-v1` is kept on the Hub
as a verification artifact, not wired into `comparative_eval.py`/
`safety_eval.py`.

This does not change C2's status for this card's acceptance criterion — C2
was already `recorded_kaggle_run` (real, not estimated) before this session.
**Still open, and known before this reconciliation too**:
`02_supervised_finetuning/run.py` doesn't implement response-only masking,
so it isn't actually reproducing the methodology behind the recorded C2
number — a real gap `C2_1_supervised_finetuning.md` already flagged,
unresolved as of this note.

## C3 real checkpoint (2026-09-01)

`research/experiments/03_contrastive_learning/run.py` was actually run on a
Kaggle GPU node (T4), warm-started from `Danleon56/chioma-sft-v1` (C2), and
published to `AfriMentor/chioma-dpo-v1` on HF Hub. `comparative_eval.py`
already pointed at this exact repo ID (from the casing fix earlier in this
doc), so it picks up the real checkpoint automatically on the next run — no
code change needed there.

**Result: composite 0.598** (persona_adherence 0.530), scored via the same
harness/judge as C1/C2 — close to and slightly above the literature-based
`C3_ESTIMATED` placeholder (0.602) that's been standing in for it, a
reasonable sanity check that the estimate wasn't far off. Small sample (5
held-out examples, same caveat as every other live GPU eval in this doc).

Getting the training script to actually run surfaced three real code bugs,
none of them environment-specific, all fixed in `run.py`:
- `trl==0.13.0`'s `DPOTrainer(peft_config=..., model=<already a PeftModel>)`
  combination triggers an internal `model.merge_and_unload()` that isn't
  supported on a 4-bit quantized base (confirmed via `trl` source on the
  installed build) — fixed by dropping `peft_config` entirely and continuing
  to train the existing SFT adapter directly, which is also the more
  faithful reading of "warm-start from C2" than merging it away.
- Gradient checkpointing (added defensively, before this ever ran) crashes
  with `CheckpointError: Recomputed values ... have different metadata` when
  `device_map="auto"` shards the model across >1 GPU — now only enabled on a
  single-GPU session (`torch.cuda.device_count() <= 1`).
- `PeftModel.from_pretrained(..., is_trainable=True)` is required when
  loading a checkpoint for further training — it defaults to inference mode
  (`requires_grad=False` on every adapter param), silently making the whole
  model untrainable (`element 0 of tensors does not require grad`) until
  this was added explicitly.

## C4 real checkpoint (2026-09-01)

**Attempt 1** (same Kaggle T4 session as C3): `run.py --stage all` — Stage 1
(reward probe, 50 train / 12 val pairs, `probe_train_accuracy=1.000`,
`probe_val_accuracy=1.000`), Stage 2 (DPO, warm-started from
`AfriMentor/chioma-dpo-v1`, `train_loss=2.670`), Stage 3 (shared-metric-suite
eval, **composite 0.629** manually corrected for 2/5 judge-quota-failed
samples — see the harness-fix note below). This adapter was **never
actually secured**: both the local zip-download and the HF Hub push were
believed to have run, but neither had — confirmed later via HF's "Recent
Activity" feed showing no `chioma-rlhf-v1` entry at all. By the time this
was caught, the Kaggle session had reset and the checkpoint files were
gone. **The 0.629 score is real (it measured an actual trained model), but
that exact checkpoint no longer exists** — don't treat 0.629 as this
condition's number without a fresh measurement (below).

**Attempt 2** (fresh Kaggle session, same day): re-ran the pipeline with one
optimization — `--stage dpo` only, skipping Stage 1 entirely. This dataset's
reward probe is provably a no-op (every one of the 50 training pairs already
has `preferred: "a"`; the fitted probe is a `DummyClassifier` that always
predicts "prefer a" regardless of input — see `_prob_prefer_a` in
`reward_model.py`), so `pairs_to_dpo_format(pairs, probe=None, ...)`
produces byte-identical DPO training data to running Stage 1 first, at zero
judge-API cost. Training succeeded (adapter saved), and this time the push
was verified immediately, before anything else touched the session:
published to `AfriMentor/chioma-rlhf-v1` on HF Hub, commit `7a598cd8`,
confirmed via the `CommitInfo(...)` object returned. **This checkpoint is
the real, currently-existing C4 adapter.** Stage 3 (evaluate) has not yet
been re-run against it — the 0.629 figure above is from Attempt 1's now-gone
checkpoint, not this one. Same training data/hyperparameters, so a similar
score is expected, but it needs an actual measurement before being recorded
as C4's result.

**The harness bug found along the way, fixed regardless of which checkpoint
number ends up canonical:** Attempt 1's Stage 3 eval hit the Groq daily
token quota (`tokens per day (TPD)`) partway through its 5-sample eval — 2
of 5 samples got 429'd and silently fell back to `metrics.py`'s zero-score
default, and the harness's own reported `avg composite=0.378` **averaged
those two corrupted zeros in** with the 3 real scores (0.495, 0.580, 0.812)
— nothing in `evaluate_checkpoint`/`avg_scores` distinguished "genuinely
scored 0" from "judge call failed." This exact quota/429 exhaustion hit
multiple stages that day (C3's `pairs_to_dpo_format`, C4 Attempt 1's Stage
1, C4 Attempt 1's Stage 3 twice — once on `gpt-oss-120b`, again on
`gpt-oss-20b` after switching). **Fixed**: `score_all_dimensions` now tags
a failure with `_judge_failed`, threaded through `EvalResult.metadata` to
`avg_scores` (and `comparative_eval._avg_scores`, now a re-export of the
same function instead of a duplicate), which excludes failed rows from the
mean and reports `n_judge_failed`/`n_samples_scored` instead of silently
diluting. 10 offline tests in
`research/evaluation/tests/test_judge_failure_handling.py` lock this in,
including a reproduction of this exact 3-real/2-failed shape.

**Stage 3 re-run against the Attempt 2 (currently-live) checkpoint: clean
5/5, no judge failures — composite 0.632, persona_adherence 0.470.** Nearly
identical to Attempt 1's manually-corrected 0.629 (n=3), a good consistency
check that the retrained checkpoint genuinely matches the lost one's
quality. **0.632 (n=5) is C4's real, final, trustworthy result.**

With this, **all 4 conditions now have real, non-estimated checkpoints**:
C1 (`live_groq`), C2 (`Danleon56/chioma-sft-v1`, recorded, composite 0.476),
C3 (`AfriMentor/chioma-dpo-v1`, composite 0.598), C4
(`AfriMentor/chioma-rlhf-v1`, composite **0.632**) — a clean, monotonic
C2→C3→C4 improvement curve, consistent with what the alignment pipeline is
supposed to do at each stage.

## First real 4-condition comparative_eval.py run (2026-09-01)

With C2/C3/C4 all real HF Hub checkpoints, `comparative_eval.py --sample-size
5` was run for the first time ever producing **live, non-fallback results for
all four conditions in one reproducible pass** — same harness, same held-out
samples, same judge, confirming the eval-harness fix (above) behaves
correctly in the full pipeline, not just the offline test suite:

| Condition | Composite | Source |
| :--- | :---: | :--- |
| C1 | 0.697 | `live_groq` |
| C2 | 0.585 | `live_hf_adapter` (`Danleon56/chioma-sft-v1`) |
| C3 | 0.589 | `live_hf_adapter` (`AfriMentor/chioma-dpo-v1`) |
| C4 | 0.616 | `live_hf_adapter` (`AfriMentor/chioma-rlhf-v1`) |

This is the first time C2 has been live-measured through this exact
pipeline rather than relying on Daniel's originally recorded 0.476 — a
different number (5-sample set here vs. his larger held-out split there),
not a contradiction, just a second independent measurement of the same
checkpoint. C3/C4 land close to their individual-script measurements
(0.598/0.632), small-N variance accounted for.

`human_eval_sampler.py` then built the blinded rating packet from this run:
**20 samples, all 4 conditions ratable** (`rating_packet.csv` +
`rating_key.json`, both downloaded from Kaggle; `comparative_results.json`
kept alongside as the audit trail). Handed off to human raters — **not
something this session can do itself**.

## What's still blocking a real C5.1 completion

1. ~~The eval-harness silent-zero-dilution gap~~ — **fixed and verified**
   (above) in the actual 4-condition pipeline, not just offline tests.
2. **The human-evaluation panel itself.** The blinded packet exists and is
   with raters (Grace's field team or another qualified reviewer per
   `human_eval_rubric.md` — informal-sector/micro-enterprise familiarity in
   Nigeria/Ghana/Kenya). Need 2+ completed `rating_packet.csv` copies back,
   then `human_eval_aggregate.py rater1.csv rater2.csv` (pure CSV/JSON, runs
   locally, no GPU/API needed) to produce `human_eval_results.json`.
3. **G3.4** (a listed dependency for this card) does not exist anywhere in
   this repository — no commit, doc, or card with a "G" prefix. Treated as
   external/not blocking per product-owner direction, but worth confirming
   its actual status doesn't reintroduce a real dependency later.
4. Once 2-3 are addressed, re-run `freeze_results.py --version v2 --tag` — it
   will only report `PUBLICATION_READY` when every condition is genuinely
   measured and rated, which is the actual bar this card's acceptance
   criterion sets.

## References

- `research/evaluation/comparative_eval.py` — card D4.3, the automatic-metrics harness this extends
- `research/evaluation/results_table.py` — the estimated-source footnote convention this reuses
- `research/evaluation/safety_eval.py` — the `pending_generation` honesty-contract pattern this mirrors
- `research/README.md` — the 4 alignment conditions (C1–C4) definition
