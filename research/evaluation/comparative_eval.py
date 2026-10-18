"""Unified comparative evaluation across all 4 alignment conditions (C1-C4).

Runs baseline prompting, supervised fine-tuning, contrastive learning, and RLHF
on the identical held-out test set (sft_test.jsonl) through the complete metric
suite, producing the results table that anchors the paper's Results section.

Usage:
    python research/evaluation/comparative_eval.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from evaluation.checkpoint_eval import avg_scores as _avg_scores
from evaluation.checkpoint_eval import load_eval_samples, render_system_prompt
from evaluation.metrics import evaluate_response

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SPLITS_DIR = _RESEARCH_ROOT / "datasets" / "splits"
DEFAULT_OUTPUT = _RESEARCH_ROOT / "evaluation" / "results" / "comparative_results.json"

C1_MODEL_ID = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
C1_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
C1_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
C1_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# Which base model + published adapters each run evaluates. "qwen" is the original
# (v1) run frozen as eval-freeze-v1; the others are the papers-revision retrains.
MODEL_SETS = {
    "qwen": {"base": "Qwen/Qwen2.5-7B-Instruct",
             "c2": ["Danleon56/chioma-sft-v1", "Danleon56/qwen2.5-7b-chioma-sft-merged"],
             "c3": "AfriMentor/chioma-dpo-v1", "c4": "AfriMentor/chioma-rlhf-v1"},
    "llama31_8b": {"base": "meta-llama/Llama-3.1-8B-Instruct",
                   "c2": ["AfriMentor/chioma-llama31-8b-sft-v2"],
                   "c3": "AfriMentor/chioma-llama31-8b-dpo-v2", "c4": "AfriMentor/chioma-llama31-8b-rlhf-v2"},
    # v2b: C3/C4 retrained with gentler DPO after the first attempt (v2a) collapsed (C4 degenerate).
    # C1/C2 are unchanged and can be reused from the v2a results via --reuse-from.
    "llama31_8b_v2b": {"base": "meta-llama/Llama-3.1-8B-Instruct",
                       "c2": ["AfriMentor/chioma-llama31-8b-sft-v2"],
                       "c3": "AfriMentor/chioma-llama31-8b-dpo-v2b", "c4": "AfriMentor/chioma-llama31-8b-rlhf-v2b"},
    # v3: best-of-4 judge-selected data, trained with the ~30-token minimal system prompt ("prompt-free").
    # C1P = base + the same minimal prompt (the fair prompt-free baseline); C1S = base + FULL persona prompt + format
    # instruction (the strong, expensive baseline). C4 is not run in this set.
    "llama31_8b_v3": {"base": "meta-llama/Llama-3.1-8B-Instruct", "trained_system": "minimal",
                      "c2": ["AfriMentor/chioma-llama31-8b-sft-v3"],
                      "c3": "AfriMentor/chioma-llama31-8b-dpo-v3", "c4": "AfriMentor/chioma-llama31-8b-rlhf-v3"},
    "gptoss_20b": {"base": "unsloth/gpt-oss-20b",  # loaded via Unsloth (plain HF expands experts to ~40GB on a T4)
                   "c2": ["AfriMentor/chioma-gptoss-20b-sft-v2"],
                   "c3": "AfriMentor/chioma-gptoss-20b-dpo-v2", "c4": "AfriMentor/chioma-gptoss-20b-rlhf-v2"},
}

C2_RECORDED = {
    "persona_adherence": 0.4900, "cultural_fluency": 0.4500,
    "anti_dependency": 0.4900, "financial_accuracy": 0.4600,
    "urgency": 0.4900, "rouge_l": 0.1298, "bert_score_f1": 0.8454,
    "composite_score": 0.4760, "source": "recorded_kaggle_run",
    "note": "Recorded from Kaggle SFT run (22-pair, fixed parse).",
}

C3_ESTIMATED = {
    "persona_adherence": 0.6200, "cultural_fluency": 0.5800,
    "anti_dependency": 0.6100, "financial_accuracy": 0.5900,
    "urgency": 0.6000, "rouge_l": 0.1550, "bert_score_f1": 0.8620,
    "composite_score": 0.6020, "source": "estimated_dpo_extrapolation",
    "note": (
        "Estimated: C2 recorded baseline + DPO literature gains (~+12% persona "
        "metrics, ~+2pp ROUGE-L). Source: Rafailov et al. (2023) and Ziegler et al. "
        "(2019). Fallback only if the published C3 checkpoint cannot be loaded."
    ),
}

C4_ESTIMATED = {
    "persona_adherence": 0.6800, "cultural_fluency": 0.6300,
    "anti_dependency": 0.6600, "financial_accuracy": 0.6400,
    "urgency": 0.6500, "rouge_l": 0.1680, "bert_score_f1": 0.8710,
    "composite_score": 0.6540, "source": "estimated_rlhf_extrapolation",
    "note": (
        "Estimated: C3 baseline + RLHF/PPO literature gains (~+6% persona metrics, "
        "~+1.3pp ROUGE-L). Source: Ouyang et al. InstructGPT (2022). "
        "Fallback only if the published C4 checkpoint cannot be loaded."
    ),
}


# _avg_scores is checkpoint_eval.avg_scores (imported above): rows where the
# LLM judge failed (metrics.py's "judge_failed" metadata) get excluded
# instead of silently averaged in as zeros — reused here instead of
# duplicating that logic, so the fix applies uniformly to C1-C4.



def _abort_if_judge_down(rows: list[dict], label: str) -> None:
    """A missing/invalid judge key makes every sample score 0.000 and would be saved as if it were data."""
    head = rows[:3]
    if len(head) == 3 and all(r.get("judge_failed") for r in head):
        raise RuntimeError(f"[{label}] the judge failed on the first 3 samples (missing LLM_API_KEY / EVAL_JUDGE_MODEL / "
                           "no credits?). Stopping before wasting GPU time or saving zero scores.")

def _run_c1_live(samples: list[dict], api_key: str) -> list[dict]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=C1_BASE_URL)
    rows = []
    for i, sample in enumerate(samples):
        system_prompt = render_system_prompt(sample["persona"])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sample["user"]},
        ]
        response = client.chat.completions.create(
            model=C1_MODEL_ID, messages=messages,
            max_tokens=C1_MAX_TOKENS, temperature=C1_TEMPERATURE,
            # No-op for the current C1 model (gpt-oss-20b); kept as a guard in
            # case LLM_MODEL points back at a reasoning model like
            # qwen/qwen3.6-27b, which otherwise leaks a raw <think> trace into
            # `content` (see docs/implementation/C5_1_final_evaluation.md).
            extra_body={"reasoning_format": "hidden"},
        )
        response_text = response.choices[0].message.content or ""
        result = evaluate_response(sample["user"], response_text, sample.get("reference"))
        rows.append({**result.to_dict(), "persona": sample["persona"],
                     "composite_score": result.composite_score,
                     "user_message": sample["user"], "response": response_text})
        if result.metadata.get("judge_failed"):
            rows[-1]["judge_failed"] = True
        _abort_if_judge_down(rows, "C1")
        logger.info("  [C1] sample %d/%d persona=%-14s composite=%.3f",
                    i + 1, len(samples), sample["persona"], result.composite_score)
    return rows


def _run_checkpoint_condition(condition_id, base_model_id, adapter_path,
                              samples, max_new_tokens=512, temperature=0.0, user_suffix="", system_prompt_fn=None):
    from evaluation.checkpoint_eval import HFCheckpointGenerator
    generator_cls = HFCheckpointGenerator
    if "gpt-oss" in base_model_id.lower():
        from evaluation.unsloth_generator import UnslothCheckpointGenerator
        generator_cls = UnslothCheckpointGenerator
        max_new_tokens = max(max_new_tokens, 1536)  # analysis channel spends tokens before the answer
    generator = generator_cls(
        base_model_id=base_model_id, adapter_path=adapter_path,
        max_new_tokens=max_new_tokens, temperature=temperature,
    )
    rows = []
    try:
        _generate_rows(rows, condition_id, generator, samples, user_suffix, system_prompt_fn)
    finally:
        del generator
        import gc
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001 - no torch/CUDA on CPU-only machines
            pass
    return rows


def _generate_rows(rows, condition_id, generator, samples, user_suffix="", system_prompt_fn=None):
    for i, sample in enumerate(samples):
        system_prompt = (system_prompt_fn or render_system_prompt)(sample["persona"])
        # the suffix (C1S only) is part of what the model is asked, never of the recorded user_message
        response = generator(system_prompt, sample["user"] + user_suffix)
        truncated = bool(getattr(generator, "last_truncated", False))
        if truncated:
            # No final answer (reasoning ate the token budget): never let the judge
            # score an empty string as if it were a real response.
            logger.warning("  [%s] sample %d/%d: generation truncated before final answer",
                           condition_id, i + 1, len(samples))
            rows.append({"judge_failed": True, "persona": sample["persona"],
                         "user_message": sample["user"], "response": "", "generation_truncated": 1})
            continue
        result = evaluate_response(sample["user"], response, sample.get("reference"))
        rows.append({**result.to_dict(), "persona": sample["persona"],
                     "composite_score": result.composite_score,
                     "user_message": sample["user"], "response": response, "generation_truncated": 0,
                     "response_words": len(response.split())})
        if result.metadata.get("judge_failed"):
            rows[-1]["judge_failed"] = True
        _abort_if_judge_down(rows, condition_id)
        logger.info("  [%s] sample %d/%d persona=%-14s composite=%.3f",
                    condition_id, i + 1, len(samples), sample["persona"],
                    result.composite_score)
    return rows


def run(sample_size: int = 5, output_path: str | Path = DEFAULT_OUTPUT,
        *, run_c1: bool = True, run_c2: bool = True,
        run_c3: bool = True, run_c4: bool = True,
        model_set: str = "qwen", splits_dir: str | Path = SPLITS_DIR,
        c1_source: str | None = None, resume: bool = True,
        reuse_from: str | Path | None = None, reuse: tuple[str, ...] = (),
        run_c1s: bool | None = None) -> dict:
    ms = MODEL_SETS[model_set]
    # C1 must be the SAME base model the adapters were trained from, or C1-vs-C2..C4 confounds
    # "alignment" with "different model". "api" (legacy Qwen run: a hosted model) vs "local"
    # (base weights + persona prompt, no adapter, greedy) — local is the default for new sets.
    c1_source = c1_source or ("api" if model_set == "qwen" else "local")
    splits_dir = Path(splits_dir)
    samples = load_eval_samples(sample_size, splits_dir=splits_dir)
    logger.info("Loaded %d eval samples from %s", len(samples),
                splits_dir / "sft_test.jsonl")

    meta = {
        "sample_size": len(samples),
        "eval_split": "sft_test.jsonl",
        "model_set": model_set, "base_model": ms["base"], "splits_dir": str(splits_dir),
        "metric_suite": [
            "persona_adherence", "cultural_fluency", "anti_dependency",
            "financial_accuracy", "urgency", "rouge_l", "bert_score_f1",
            "composite_score",
        ],
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }
    output_path = Path(output_path)
    results = {"meta": meta, "conditions": {}}

    # Resume: a multi-hour run must survive a dropped session. Reuse conditions already measured live
    # in an earlier run of the *same* configuration; never reuse anything else.
    if resume and output_path.exists():
        prev = json.loads(output_path.read_text(encoding="utf-8"))
        same = all(prev.get("meta", {}).get(k) == meta[k]
                   for k in ("sample_size", "model_set", "base_model", "splits_dir"))
        if same:
            for cid, cond in prev.get("conditions", {}).items():
                if str(cond.get("aggregate", {}).get("source", "")).startswith("live_"):
                    results["conditions"][cid] = cond
                    logger.info("Resuming: keeping previously measured %s", cid)

    if reuse_from and reuse:
        prev = json.loads(Path(reuse_from).read_text(encoding="utf-8"))
        pm = prev.get("meta", {})
        if not all(pm.get(k) == meta[k] for k in ("sample_size", "base_model", "splits_dir")):
            raise RuntimeError("--reuse-from file was produced with a different base model / sample size / split; "
                               "its conditions are not comparable")
        for cid in reuse:
            cond = prev.get("conditions", {}).get(cid)
            if not cond or not str(cond.get("aggregate", {}).get("source", "")).startswith("live_"):
                raise RuntimeError(f"cannot reuse {cid}: not a live measurement in {reuse_from}")
            if cid not in results["conditions"]:
                results["conditions"][cid] = {**cond, "reused_from": str(reuse_from)}
                logger.info("Reusing %s from %s", cid, reuse_from)

    def save() -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)

    def measure(cid: str, adapters: list[str | None], fallback: dict | None, user_suffix: str = "",
                system_prompt_fn=None) -> None:
        if cid in results["conditions"]:
            return
        rows = None
        for adapter in adapters:
            try:
                logger.info("  [%s] trying adapter: %s", cid, adapter)
                rows = _run_checkpoint_condition(cid, ms["base"], adapter, samples, user_suffix=user_suffix,
                                                 system_prompt_fn=system_prompt_fn)
                break
            except Exception as e:  # noqa: BLE001
                logger.warning("  [%s] failed to run %s: %s", cid, adapter, e)
        if rows:
            source = "live_hf_base" if adapters == [None] else "live_hf_adapter"
            results["conditions"][cid] = {"aggregate": {**_avg_scores(rows), "source": source}, "rows": rows}
        elif fallback is not None and model_set == "qwen":
            logger.warning("%s unavailable - using the recorded/estimated value (qwen set only).", cid)
            results["conditions"][cid] = {"aggregate": fallback, "rows": []}
        else:
            # Estimates/recordings belong to the original Qwen run. For any other model they would be
            # someone else's numbers presented as this model's — fail instead.
            raise RuntimeError(f"{cid} could not be measured for model set {model_set!r} "
                               f"(tried {adapters}); refusing to substitute estimated results.")
        save()

    minimal = ms.get("trained_system") == "minimal"
    if minimal:
        from evaluation.style_prompts import minimal_system_prompt
        sysfn = minimal_system_prompt
        if run_c1:
            measure("C1P", [None], None, system_prompt_fn=sysfn)   # base + minimal prompt: the fair prompt-free baseline
    else:
        sysfn = None

    if run_c1 and c1_source == "local" and not minimal:
        logger.info("Running C1 as the local base model (%s) with the persona prompt, no adapter...", ms["base"])
        measure("C1", [None], None)
    elif run_c1 and "C1" not in results["conditions"]:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY", "")
        if not api_key:
            logger.warning("LLM_API_KEY not set - C1 uses recorded fallback.")
            results["conditions"]["C1"] = {
                "aggregate": {
                    "persona_adherence": 0.2000, "cultural_fluency": 0.3700,
                    "anti_dependency": 0.3100, "financial_accuracy": 0.3200,
                    "urgency": 0.2300, "rouge_l": 0.1400,
                    "bert_score_f1": 0.8300, "composite_score": 0.2750,
                    "source": "recorded_baseline",
                },
                "rows": [],
            }
        else:
            logger.info("Running C1 baseline prompting live via Groq...")
            rows = _run_c1_live(samples, api_key)
            results["conditions"]["C1"] = {
                "aggregate": {**_avg_scores(rows), "source": "live_groq"},
                "rows": rows,
            }
        save()

    if run_c1s is None:
        run_c1s = c1_source == "local" and run_c1
    if run_c1s:
        # Fair baseline: the untrained base model told the same format the teacher was told (see style_prompts).
        from evaluation.style_prompts import CHOSEN_STYLE
        measure("C1S", [None], None, user_suffix=CHOSEN_STYLE)

    if run_c2:
        measure("C2", list(ms["c2"]), C2_RECORDED, system_prompt_fn=sysfn)
    if run_c3:
        measure("C3", [ms["c3"]], C3_ESTIMATED, system_prompt_fn=sysfn)
    if run_c4:
        measure("C4", [ms["c4"]], C4_ESTIMATED, system_prompt_fn=sysfn)

    save()
    logger.info("Comparative results written to %s", output_path)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comparative evaluation across C1-C4")
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--model-set", choices=sorted(MODEL_SETS), default="qwen")
    parser.add_argument("--c1-source", choices=["api", "local"], default=None,
                        help="C1 via hosted API, or local base model + persona prompt (default: local for new model sets)")
    parser.add_argument("--reuse-from", default=None, help="earlier results json to copy live conditions from")
    parser.add_argument("--reuse", default="", help="comma-separated condition ids to reuse, e.g. C1,C2")
    parser.add_argument("--skip-c1s", action="store_true", help="omit the format-matched base-model baseline")
    parser.add_argument("--no-resume", action="store_true",
                        help="ignore an existing output file instead of reusing already-measured conditions")
    parser.add_argument("--splits-dir", default=str(SPLITS_DIR),
                        help="dir holding sft_test.jsonl (v2: research/datasets/splits_v2)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--skip-c1", action="store_true")
    parser.add_argument("--skip-c2", action="store_true")
    parser.add_argument("--skip-c3", action="store_true")
    parser.add_argument("--skip-c4", action="store_true")
    args = parser.parse_args()

    results = run(
        sample_size=args.sample_size, output_path=args.output,
        run_c1=not args.skip_c1, run_c2=not args.skip_c2,
        run_c3=not args.skip_c3, run_c4=not args.skip_c4,
        model_set=args.model_set, splits_dir=args.splits_dir, c1_source=args.c1_source,
        resume=not args.no_resume,
        reuse_from=args.reuse_from, reuse=tuple(x for x in args.reuse.split(",") if x),
        run_c1s=False if args.skip_c1s else None,
    )

    print("\n=== Comparative Evaluation Results ===")
    for cond_id, cond in results["conditions"].items():
        agg = cond["aggregate"]
        comp = agg.get("composite_score")
        comp_str = f"{comp:.3f}" if comp is not None else "N/A"
        print(f"  {cond_id}: composite={comp_str}  source={agg.get('source', 'unknown')}")
    print(f"\nFull results: {args.output}")