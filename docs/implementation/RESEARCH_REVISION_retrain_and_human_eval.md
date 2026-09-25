# Research-paper revision: multi-model retrain + human-evaluation fixes

Follows the submission of the capstone. Goal: resolve the methodological issues listed in
"RESEARCH PAPER ISSUES" for Paper 1 so the work can be published.

## Issue -> what changed

| Issue (Paper 1) | Change | Still needs a human |
| :--- | :--- | :--- |
| C4 reward probe is degenerate (every pair `preferred: "a"`) | New generator (`datasets/scripts/generate_dataset.py`) randomises A/B positions, so both classes exist. `fit_reward_probe(require_two_classes=True)` now **fails loudly** on a constant probe; enabled in every v2 C4 config. | Re-run C4 Stage 1 so the probe is genuinely fitted. |
| N=5 test set | Generator builds ~300 prompts (persona x country x topic, near-duplicates dropped), split **by prompt** (20% test = ~60). v2 configs evaluate on `splits_v2` with `sample_size: 60`. | Team spot-checks `human_review_sample.jsonl`. |
| Two raters only | `human_eval_aggregate.py` defaults to `--min-raters 3` (exit 2 otherwise), reports Krippendorff alpha per dimension, median adjudication (2-rater 3-point gaps are flagged `needs_third_rater`, not averaged), bootstrap 95% CI per condition. Sampler writes one independently-ordered packet per rater and a *paired* prompt subset (`--max-prompts`). | Recruit >=3 qualified raters. |
| Single model / Turing 4-bit only | `configs/llama31_8b/` and `configs/gptoss_20b/`; `comparative_eval.py --model-set`. | Kaggle GPU runs. |
| No training seed logged (appendix gap) | `training.seed` (default 42) now applied via `set_seed` + trainer `seed`/`data_seed` in C2/C3/C4. | Log the seed per run in the paper. |

## About "GPT"

Closed GPT models (GPT-4o etc.) cannot be fine-tuned on Kaggle. The only trainable GPT-family
model is the open-weight `openai/gpt-oss-20b` (already the C1 model). It is a 20B MoE: it needs a
newer trl/transformers/peft than `requirements-gpu.txt` pins and may not fit a Kaggle T4, so its
configs are marked EXPERIMENTAL. Plan: get the full pipeline working on Llama-3.1-8B first.

**Paper honesty point:** the deployed system used off-the-shelf Llama/GPT via OpenRouter (prompting
= condition C1). The fine-tuned adapters were research artefacts and were never the deployed model.
State this in the paper.

## Data caveats (must be disclosed)

- v2 data is **synthetic** (teacher-LLM generated). `manifest.json` records the teacher model.
- Use a teacher that is **not** one of the evaluated models, and say which. (gpt-oss-120b as
  teacher while gpt-oss-20b is evaluated is a leakage risk; prefer a different family.)
- Chosen = persona-prompted teacher answer; rejected = teacher answer under a *defect* prompt
  (taxonomy in `configs/dataset.yaml`). SFT therefore distils the teacher's persona behaviour.

## Runbook

1. **Generate data** (resumable; re-run after any rate-limit stop):
   `GEN_API_KEY=<openrouter key> GEN_BASE_URL=https://openrouter.ai/api/v1 GEN_MODEL=<teacher> python research/datasets/scripts/generate_dataset.py --n-prompts 300`
   Commit `research/datasets/splits_v2/`. Team reviews `human_review_sample.jsonl`.
2. **Kaggle, per model** (`llama31_8b` first). Accept Meta's Llama licence on HF for the token's account.
   `python research/experiments/02_supervised_finetuning/run.py --config research/configs/llama31_8b/c2_supervised_finetuning.yaml`, then C3, then C4 with `--stage all`.
   **Push the adapter and confirm the Hub commit before ending the session.**
3. **Evaluate**: `python research/evaluation/comparative_eval.py --model-set llama31_8b --splits-dir research/datasets/splits_v2 --sample-size 60 --output research/evaluation/results/comparative_llama31_8b.json`
   **Download the JSON immediately.**
4. **Human panel**: `python research/evaluation/human_eval_sampler.py --input <that json> --max-prompts 15 --n-raters 3`
   -> 15 prompts x 4 conditions = 60 responses per rater. Send each rater *their own* `rating_packet_rater<i>.csv`. **Back up `rating_key.json` off-machine.**
5. **Aggregate**: `python research/evaluation/human_eval_aggregate.py r1.csv r2.csv r3.csv --key <key>` (fails unless every sample has >=3 ratings).
6. **Freeze**: `python research/evaluation/freeze_results.py --version v2-llama31_8b --comparative <comparative json> --human-eval <human_eval json> --tag`.
7. Repeat 2-6 for `gptoss_20b`; report both models side by side.
8. Update the paper: sample sizes, alpha, CIs, synthetic-data statement, deployment note, seeds.

## Known limits of this change

- Nothing here has been run on a GPU yet; only offline tests (generator, aggregation, probe guard).
- Paper 2's blockers (pilot not run, ethics/jurisdiction open, C3.5/C4.5 data) are not addressed by code.
