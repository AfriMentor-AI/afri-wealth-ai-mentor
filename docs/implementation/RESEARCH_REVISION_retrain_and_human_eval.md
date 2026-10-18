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

## Decisions after the first Kaggle attempts (gpt-oss-20b)

- **gpt-oss-20b is not viable on Kaggle T4s with the plain Hugging Face stack.** Plain
  transformers dequantizes the MoE experts to bf16 (~40GB) and spills to CPU
  (`Some modules are dispatched on the CPU or the disk`). Unsloth's loader is the only documented
  route that fits (~14GB); it was not successfully tested (an unpinned `kernels` package broke
  imports). Treated as a follow-up needing either Unsloth porting of C2-C4 or a larger GPU.
- **Main results use Llama-3.1-8B-Instruct.** Scripts for gpt-oss (`gptoss_smoke_test.py`,
  `gptoss_unsloth_smoke_test.py`, harmony parsing) are kept for that follow-up.
- **C1 is now the same base model** (`--c1-source local`, source tag `live_hf_base`): base Llama +
  persona prompt, no adapter, greedy. The v1 C1 was a different, hosted model, which confounded
  "alignment" with "which model".
- **Avoid self-preference in the judge.** Teacher (data generation), judge, and evaluated models
  should be different families: teacher e.g. `qwen/qwen-2.5-72b-instruct`, judge
  `openai/gpt-oss-120b`, evaluated Llama-3.1-8B. Configure via `GEN_*` and
  `LLM_BASE_URL`/`LLM_API_KEY`/`EVAL_JUDGE_MODEL` (OpenRouter works for both).

## Update: gpt-oss-20b DOES fit via Unsloth (smoke test passed)

`gptoss_unsloth_smoke_test.py` on 2x T4: loads at 5.8 GiB/GPU, generates a parseable harmony answer,
5 LoRA steps with falling loss (peak 9.7 GiB). Required `pip uninstall -y kernels` after installing unsloth.
Unsloth forces float32 for gpt-oss on T4 (no bf16), so training is slower than Llama.

`experiments/gptoss_unsloth/train.py` (explicit PyTorch loop, no TRL): `sft` = C2; `dpo` = C3 (warm-start from
`model.sft_checkpoint`); `dpo --rlhf` = C4 (warm-start from `prior_checkpoint`, probe-guided pairs via
`pairs_to_dpo_format`; run `04_rlhf_preference_opt/run.py --stage reward_model` first to produce the probe,
otherwise dataset labels are used and a warning is printed). Evaluation uses
`evaluation/unsloth_generator.py` automatically for gpt-oss model sets.
NOT yet run end-to-end on a GPU — do a timing run first:
`train.py sft --config research/configs/gptoss_20b/c2_supervised_finetuning.yaml --dataset research/datasets/splits/sft_train.jsonl --max-examples 8 --epochs 1 --no-push`

## Final gpt-oss-20b finding (2026-09-26): stopped; not trainable on Kaggle T4 via Unsloth

Loads (5.8 GiB/GPU), generates coherently (including from a 189-token prompt), and the LoRA loop runs at
~3 s/example. But the plain training-style forward pass gives wrong logits at realistic lengths:
teacher-forced loss on one real example by prefix length = 3.95 (48 tok), 5.5 (96), 6.0 (128), 5.9 (160),
7.5 (224), 10.4 (320), 11.9 (392) — worse than uniform guessing (~12.2) in the second half. Identical with and
without an attention mask, and unchanged by `attn_implementation="eager"`. First SFT loss was 15.7. Training on
these logits would be meaningless, so no full run was made. Likely an Unsloth/T4 numerical path issue (float32 forced,
128-token sliding-window layers); would need an A100/H100 or a fixed Unsloth release. Label masking was verified
correct offline with the real tokenizer. Scripts kept for that follow-up:
`experiments/gptoss_unsloth/{train,core,loss_diag,loss_diag2}.py`, `evaluation/unsloth_generator.py`.

Paper wording: "gpt-oss-20b loads and generates on 2xT4 via Unsloth, but fine-tuning on T4 was numerically unreliable and
is left to future work on larger GPUs." Main results use Llama-3.1-8B-Instruct.

## Dataset v2 generated (2026-10-10) — what it is and its limits

`research/datasets/splits_v2/`: 300 pairs (train 210 / val 30 / test 60), teacher `qwen/qwen-2.5-72b-instruct` via OpenRouter,
split by prompt (0 overlap), A/B balanced (train 97a/113b, val 18/12, test 33/27), 6 personas x 7 countries, lengths matched
(chosen 89 vs rejected 84 words after a 0.6-1.6x parity filter), no persona-name/markup/instruction leakage, no identical pairs.
`cache.jsonl` holds every raw teacher call (resumable + auditable). `human_review_sample.jsonl` (40 pairs) is for team review.

**Limitations to disclose in the paper**
1. **Synthetic**: all prompts, chosen and rejected answers are teacher-LLM output.
2. **The preference signal is largely stylistic.** Chosen ends with a question 98% (rejected 1%) and contains a number 98%
   (rejected 32%); 71% of chosen answers open with a "friend"-style phrase. This is the persona spec, but it means gains
   can come from learning the surface template rather than better advice. The automatic judge's rubric also rewards
   "concrete numbers" and "sharp next action", so it may favour the same template.
3. **`rejection_reason` labels are unreliable.** Spot checks show some "culturally_misaligned" / "factually_incorrect"
   rejections are reasonable advice; what actually separates the pair is voice and concreteness. Do not report per-reason results.
4. Human raters should be told to judge advice substance and appropriateness, not template adherence.

## Llama-3.1-8B first full run (v2a) — result and what it means (2026-10-11)

Adapters: `AfriMentor/chioma-llama31-8b-{sft,dpo,rlhf}-v2` (kept on the Hub for the record). Scored on 60 held-out
prompts, judge `openai/gpt-oss-120b`: C1 0.512, C2 0.441, C3 0.399, **C4 0.099**.

- **C4 collapsed.** Responses degenerate into "friend friend friend ..." (13/60 repeat loops, 10/60 ran to the token
  cap; none in C1-C3). Cause: DPO stacked on an already-saturated C3 (reward accuracy 1.0, margin 6.5, loss 0.013) for 2 more
  epochs at lr 5e-5 collapsed onto the token 71% of chosen answers open with. This is a training failure, not evidence about RLHF.
- **Length confound.** Mean words C1 243 / C2 112 / C3 67 (training data was length-capped at 70-140 words). The judge
  rewards length (corr(words, composite) = +0.40 pooled; +0.41 within C1; mean composite 0.40 for <80 words -> 0.53 for >250).
  At matched length C2/C3 are level with the base model (e.g. 0-80 words: 0.39 / 0.40 / 0.41). Raw composites are therefore
  not a fair measure of alignment; report `evaluation/length_analysis.py` output alongside.
- **No fair baseline.** C1 was never told the answer format the trained models learned. Added **C1S** (base model + the
  teacher's format instruction, `evaluation/style_prompts.py`).
- **Safeguards added**: generation-health check before any push (blocks collapsed adapters); `rpo_alpha` NLL anchor; v2b configs
  (`configs/llama31_8b_v2b`: C3 lr 1e-5 x 2 ep, C4 lr 5e-6 x 1 ep, rpo_alpha 1.0). v2a results are retained in
  `evaluation/results/comparative_llama31_8b_v2a.json` and must be reported as the first attempt in the paper.
- Known remaining limitation: DPO prompts omit the persona system prompt (SFT and evaluation include it).

## Llama v2b result (2026-10-11): null result at small scale

Gentler DPO (v2b) trained cleanly; all adapters passed the health check. Composite (60 prompts, gpt-oss-120b judge):
C1 0.512, **C1S 0.545**, C2 0.441, C3 0.436, C4 0.440. Paired 95% bootstrap CIs over prompts: C2/C3/C4 mutually
indistinguishable (|diff| <= 0.005); C1S beats each trained model by ~0.10 (CIs exclude 0); C1S vs C1 +0.033 [-0.004, +0.073];
C2 vs C1 -0.071 [-0.112, -0.031]. Persona adherence: C1S 0.71 vs C2/C3/C4 0.52-0.56. Trained models include a digit in only
70-77% of answers (C1S 98%) and end with a question 93-98%, i.e. they learned the template's shape but not its content.
ROUGE-L/BERTScore favour the trained models (closer to teacher text) — expected and not evidence of better advice.
Interpretation: with 210 synthetic examples, fine-tuning did not beat a format-matched prompt; DPO/RLHF added nothing over
SFT. One judge, n=60, synthetic data, judge length bias -> report as a null result, not as "fine-tuning fails".
Human panel excludes C1 (`--exclude C1`): its 243-word markdown answers are trivially identifiable and break blinding.

## v3: best-of-4 judge-selected data (2026-10)

After the v2b null result (trained adapters learned the answer *shape* but did not beat a prompted base model), v3 changes the
signal rather than the hyper-parameters:

- `generate_dataset_v3.py`: 4 teacher samples per prompt, scored by a *selection* judge (DeepSeek-V3.1). SFT target = best sample
  (rejection sampling). DPO pair = best vs worst only when the composite gap >= 0.10 and the length ratio <= 1.35, so chosen and
  rejected share the template and length (v2 pairs were separable by template alone).
- 1,700 prompts requested -> 1,305 kept (dedupe + quality floor 0.55): train 1,085 / val 100 / test 120 prompts; 920 / 86 / 100 DPO pairs.
  Mean within-prompt spread 0.197. Chosen 91.9 words vs rejected 91.0; both end in a question (96.6% vs 93.6%), so no shortcut.
- Training and deployment use a ~30-token minimal system prompt (no 1.7k-token persona prompt).
- Evaluation conditions: C1P (base + minimal prompt), C1S (base + full prompt + format), C2, C3. C4 skipped pending C3 signal.
- **Limitations to state in the paper:** all data is LLM-generated; the selection judge (DeepSeek) must not be used as an evaluator
  (use gpt-oss-120b + a third family via `rescore.py`); winner's curse applies to judge-selected targets.

### v3 first attempt: SFT pad-token bug (2026-10-18)

The first v3 C2 adapter (Hub commit 539685084a52) never ended its turn: 118/120 test answers exceeded 200 words and looped
("What do you think the first step should be… Let's make this concrete…"). Cause: `tokenizer.pad_token = tokenizer.eos_token` in
the SFT script. TRL masks pad tokens out of the loss, so the end-of-turn token was never trained. The first-attempt C3
(44eaa2a447143f595c7c189fc892c4af239da6df) was warm-started from that adapter. It stopped normally (95 words, composite 0.566 vs
C1S 0.543) but cannot be treated as a clean result. The v2/v2b C2 adapters had the same pad setting (v2b C2 max 397 words),
so earlier C2 numbers may also understate SFT. Fix: dedicated `<|finetune_right_pad_id|>` pad token, plus the C3-style
generation-health guard before the push. C2 and C3 were retrained and re-evaluated; first-attempt results are kept as
`comparative_llama31_8b_v3_padbug.json` for the appendix. C1P/C1/C1S were reused unchanged.

### v3b result (fixed C2, C3 retrained on it; n=120 test prompts, Llama-3.1-8B-Instruct)

Hub: sft-v3 52951fed4f34, dpo-v3 acd6ce68d485. Results file `comparative_llama31_8b_v3b.json` (C1P/C1/C1S reused from the first v3 run).

| Condition | gpt-oss-120b | Mistral-large-2512 | median words |
|---|---|---|---|
| C1P base + ~30-token prompt | 0.392 | 0.647 | 319 |
| C1S base + full prompt + format | 0.543 | 0.748 | 107 |
| C2 SFT (minimal prompt) | 0.546 | 0.692 | 88 |
| C3 SFT + DPO (minimal prompt) | 0.586 | 0.720 | 93 |
| C1 base + full prompt (long) | 0.769 | 0.891 | 252 |

Paired differences, 95% bootstrap CI over prompts (gpt-oss / Mistral):
- C3 - C1P: +0.194 [+0.165,+0.223] / +0.073 [+0.051,+0.095]; C2 - C1P: +0.153 / +0.048. Robust: fine-tuning beats the base model that is given the same short prompt.
- C3 - C2: +0.041 [+0.019,+0.062] / +0.024 [+0.010,+0.038]. DPO adds a small gain under both judges.
- C3 - C1S: +0.043 [+0.013,+0.074] / **-0.028** [-0.046,-0.011]. The judges disagree in sign: no robust win over the prompted+formatted base.
- C2 - C1S: +0.002 [-0.029,+0.035] / -0.054 [-0.073,-0.036].
- C1 (full prompt, 252 words) beats everything under both judges, but its score correlates with length (r=0.63).

Behaviour (read the answers): 100% of C2/C3 answers end with a question; 67% open with "I get it, friend" (template); 78-82% contain a concrete number
(C1S 79%). Answers are coherent and in persona; advice quality is comparable to C1S, with some invented figures in both.
Not evaluated with the selection judge (DeepSeek) by design. Mistral coverage 116-120 of 120 per condition (upstream 429s dropped a few rows).

Claim supported: a prompt-free fine-tuned 8B matches the prompted base on format and persona at ~1/50 of the prompt tokens, and beats the
equally short-prompted base. Claim NOT supported: that fine-tuning beats prompting.
