"""Condition C4 — Personality-Focused RLHF / Preference Optimization (card D1.4).

Three-stage pipeline:
  Stage 1 (reward_model): Collect human preference data over response pairs that
    differ in personality expression but are matched for task quality.  Score each
    pair with the LLM-as-judge, then fit a lightweight logistic probe on the
    per-dimension score deltas — the "reward/critique model for personality fit."
  Stage 2 (dpo): Apply Direct Preference Optimization on top of the best prior
    checkpoint (C3 DPO adapter, warm-starting from C3).  The probe re-ranks pairs
    before DPO so training targets the model-verified preference signal, not just
    raw human annotations.
  Stage 3 (evaluate): Score the resulting checkpoint against the shared metric
    suite — same 5-dimension rubric + ROUGE-L/BERTScore as C1/C2/C3.

CPU safety
----------
Stage 1 and Stage 3 run on CPU (Groq API + sklearn).  Stage 2 (DPO fine-tuning)
requires a GPU; it skips gracefully on CPU with an informative message, and the
evaluate stage still runs against the base model (or an injected generator) so
the run always produces comparable metrics.

Usage (no GPU — reward probe + evaluation):
    python research/experiments/04_rlhf_preference_opt/run.py --stage all

Usage (GPU node — full pipeline):
    python research/experiments/04_rlhf_preference_opt/run.py --stage all

Stage-by-stage:
    python research/experiments/04_rlhf_preference_opt/run.py --stage reward_model
    python research/experiments/04_rlhf_preference_opt/run.py --stage dpo
    python research/experiments/04_rlhf_preference_opt/run.py --stage evaluate
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import mlflow
import yaml

# Ensure research/ is on path so evaluation.* resolves.
_RESEARCH_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _RESEARCH_ROOT.parent
sys.path.insert(0, str(_RESEARCH_ROOT))

from evaluation.reward_model import (  # noqa: E402
    fit_reward_probe,
    evaluate_probe,
    load_preference_pairs,
    pairs_to_dpo_format,
    save_reward_probe,
    score_dataset,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEFAULT_CONFIG = _RESEARCH_ROOT / "configs" / "c4_rlhf_preference_opt.yaml"


# ── Config ─────────────────────────────────────────────────────────────────────

def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _resolve(path_str: str) -> Path:
    """Resolve a config path (repo-relative or absolute) against the repo root."""
    p = Path(path_str)
    return p if p.is_absolute() else _REPO_ROOT / p


def _count_jsonl(path: str | Path) -> int:
    """Non-blank line count of a JSONL file, 0 if it does not exist."""
    p = Path(path)
    if not p.exists():
        return 0
    with open(p) as f:
        return sum(1 for line in f if line.strip())


def _gpu_available() -> bool:
    try:
        import torch
    except ImportError:
        logger.warning("PyTorch not installed. Install requirements-gpu.txt on a GPU node.")
        return False
    if not torch.cuda.is_available():
        logger.warning("No CUDA GPU detected. C4 DPO fine-tuning requires a GPU node.")
        return False
    return True


# ── Stage 1: Reward / Critique Model ──────────────────────────────────────────

def run_reward_model(cfg: dict) -> dict:
    """Stage 1: Score preference pairs with LLM judge, fit and evaluate logistic probe.

    Returns
    -------
    dict with keys: ``probe`` (fitted object), ``probe_path`` (str),
    ``train_report``, ``val_report``.
    """
    rm_cfg = cfg["reward_model"]
    reward_weights: dict = rm_cfg.get("reward_weights", {})

    train_path = _resolve(rm_cfg["dataset"])
    val_path = _resolve(rm_cfg["eval_dataset"])
    probe_out = _resolve(rm_cfg["probe_output"])

    logger.info("=== Stage 1: Reward Model ===")
    logger.info("Training preference pairs: %s", train_path)

    # Load preference pairs
    train_pairs = load_preference_pairs(train_path)
    val_pairs = load_preference_pairs(val_path)

    if not train_pairs:
        logger.error("No training pairs found at %s. Aborting reward model stage.", train_path)
        return {"probe": None, "probe_path": None, "train_report": {}, "val_report": {}}

    mlflow.log_param("rm_train_pairs", len(train_pairs))
    mlflow.log_param("rm_val_pairs", len(val_pairs))
    mlflow.log_param("reward_weights", json.dumps(reward_weights))

    # Score all pairs with LLM judge
    logger.info("Scoring %d training pairs with LLM judge (this calls the API)…", len(train_pairs))
    scored_train = score_dataset(train_pairs, reward_weights=reward_weights)

    # Fit logistic probe
    logger.info("Fitting logistic preference probe on %d scored pairs…", len(scored_train))
    probe, train_report = fit_reward_probe(scored_train)

    mlflow.log_metric("probe_train_accuracy", train_report["train_accuracy"])
    mlflow.log_metric("probe_train_samples", train_report["n_samples"])
    logger.info("  probe_train_accuracy=%.3f (n=%d)", train_report["train_accuracy"], train_report["n_samples"])

    # Log per-dimension coefficients (feature importances)
    for dim, coef in train_report.get("probe_coefficients", {}).items():
        mlflow.log_metric(f"probe_coef_{dim}", coef)

    # Evaluate on validation set (if it has data)
    val_report: dict = {}
    if val_pairs:
        logger.info("Scoring %d validation pairs…", len(val_pairs))
        scored_val = score_dataset(val_pairs, reward_weights=reward_weights)
        val_report = evaluate_probe(probe, scored_val)
        mlflow.log_metric("probe_val_accuracy", val_report["accuracy"])
        mlflow.log_metric("probe_val_samples", val_report["n_samples"])
        logger.info("  probe_val_accuracy=%.3f (n=%d)", val_report["accuracy"], val_report["n_samples"])
    else:
        logger.warning("No validation pairs — skipping probe validation.")

    # Save probe
    save_reward_probe(probe, probe_out)
    if cfg.get("mlflow", {}).get("log_artifacts"):
        mlflow.log_artifact(str(probe_out))

    # Compute and log average reward delta (reward_a − reward_b across training set)
    if scored_train:
        import numpy as np
        from evaluation.reward_model import _weighted_reward
        deltas = [
            _weighted_reward(ps.scores_a, reward_weights) - _weighted_reward(ps.scores_b, reward_weights)
            for ps in scored_train
        ]
        avg_delta = float(np.mean(deltas))
        mlflow.log_metric("avg_reward_delta", avg_delta)
        logger.info("  avg_reward_delta=%.3f (should be > 0 since response_a is always preferred)", avg_delta)

    return {
        "probe": probe,
        "probe_path": str(probe_out),
        "train_report": train_report,
        "val_report": val_report,
    }


# ── Stage 2: DPO on probe-ranked personality pairs ────────────────────────────

def run_dpo(cfg: dict, probe=None) -> tuple[str | None, dict]:
    """Stage 2: Apply DPO fine-tuning on reward-model-ranked preference pairs.

    Returns ``(adapter_path, dpo_metrics)``.  On CPU the training is skipped and
    ``(None, {})`` is returned so the caller can decide what to do.

    The probe is used to re-rank pairs before training (probe-guided DPO): pairs
    where the probe disagrees with the human label (or is uncertain) keep their
    original label; pairs where the probe is confident reinforce the personality
    signal.
    """
    if not _gpu_available():
        logger.warning(
            "DPO fine-tuning skipped — no GPU available. "
            "Reward probe and evaluation stages still run."
        )
        return None, {}

    import torch
    from datasets import load_dataset, Dataset
    from peft import LoraConfig, PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import DPOConfig, DPOTrainer

    rm_cfg = cfg["reward_model"]
    dpo_cfg = cfg["dpo"]
    model_cfg = cfg["model"]
    train_cfg = cfg["training"]
    lora_cfg = cfg["lora"]
    bnb_cfg = cfg["quantization"]

    logger.info("=== Stage 2: DPO (personality-focused) ===")

    # Convert RLHF pairs → DPO format using probe-guided re-ranking
    train_pairs = load_preference_pairs(_resolve(rm_cfg["dataset"]))
    val_pairs = load_preference_pairs(_resolve(rm_cfg["eval_dataset"]))

    logger.info("Converting %d training pairs to DPO format (probe-guided re-ranking)…", len(train_pairs))
    dpo_train = pairs_to_dpo_format(train_pairs, probe=probe,
                                    reward_weights=rm_cfg.get("reward_weights"))
    dpo_val = pairs_to_dpo_format(val_pairs, probe=probe,
                                  reward_weights=rm_cfg.get("reward_weights"))

    # Write converted datasets
    converted_train_path = _resolve(dpo_cfg["converted_dataset"])
    converted_val_path = _resolve(dpo_cfg["converted_eval_dataset"])
    converted_train_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_jsonl(records: list[dict], path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

    _write_jsonl(dpo_train, converted_train_path)
    logger.info("  Wrote %d DPO training pairs to %s", len(dpo_train), converted_train_path)
    has_val = bool(dpo_val)
    if has_val:
        _write_jsonl(dpo_val, converted_val_path)
        logger.info("  Wrote %d DPO val pairs to %s", len(dpo_val), converted_val_path)

    mlflow.log_param("dpo_train_pairs", len(dpo_train))
    mlflow.log_param("dpo_val_pairs", len(dpo_val))
    mlflow.log_param("dpo_beta", dpo_cfg["beta"])
    mlflow.log_param("dpo_loss_type", dpo_cfg["loss_type"])

    # Quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=bnb_cfg["load_in_4bit"],
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type=bnb_cfg["bnb_4bit_quant_type"],
        bnb_4bit_use_double_quant=bnb_cfg["bnb_4bit_use_double_quant"],
    )

    # Load base model + prior checkpoint (C3 DPO adapter)
    prior_ckpt = _resolve(model_cfg["prior_checkpoint"])
    base_model_id = model_cfg["base_model_id"]

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        device_map="auto",
    )

    if prior_ckpt.exists():
        logger.info("Warm-starting from C3 DPO adapter: %s", prior_ckpt)
        model = PeftModel.from_pretrained(base_model, str(prior_ckpt))
    else:
        logger.warning(
            "C3 DPO adapter not found at %s — DPO starts from base model.", prior_ckpt
        )
        model = base_model

    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg["lora_dropout"],
        target_modules=lora_cfg["target_modules"],
        bias=lora_cfg["bias"],
        task_type=lora_cfg["task_type"],
    )

    # Build HF dataset
    data_files = {"train": str(converted_train_path)}
    if has_val:
        data_files["validation"] = str(converted_val_path)
    dataset = load_dataset("json", data_files=data_files)

    output_dir = _resolve(model_cfg["output_dir"])
    dpo_config = DPOConfig(
        output_dir=str(output_dir),
        num_train_epochs=train_cfg["num_train_epochs"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        lr_scheduler_type=train_cfg["lr_scheduler_type"],
        warmup_ratio=train_cfg["warmup_ratio"],
        bf16=train_cfg["bf16"],
        logging_steps=train_cfg["logging_steps"],
        eval_steps=train_cfg["eval_steps"] if has_val else None,
        eval_strategy="steps" if has_val else "no",
        save_steps=train_cfg["save_steps"],
        save_total_limit=train_cfg["save_total_limit"],
        beta=dpo_cfg["beta"],
        loss_type=dpo_cfg["loss_type"],
        max_length=dpo_cfg["max_length"],
        max_prompt_length=dpo_cfg["max_prompt_length"],
        report_to="none",
    )

    trainer = DPOTrainer(
        model=model,
        args=dpo_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"] if has_val else None,
        tokenizer=tokenizer,
        peft_config=lora_config,
    )

    trainer.train()
    adapter_path = str(output_dir / "final")
    trainer.save_model(adapter_path)
    logger.info("C4 DPO adapter saved to %s", adapter_path)

    dpo_metrics: dict = {}
    if has_val:
        raw = trainer.evaluate()
        dpo_metrics = {k.replace("eval_", "dpo_"): v for k, v in raw.items()}
        for k, v in dpo_metrics.items():
            mlflow.log_metric(k, v)

    return adapter_path, dpo_metrics


# ── Stage 3: Evaluate against shared metric suite ────────────────────────────

def run_evaluate(cfg: dict, adapter_path: str | None = None, generate_fn=None) -> dict:
    """Stage 3: Score the C4 checkpoint against the shared metric suite.

    Logs the same MLflow keys as C1/C2/C3 so the four conditions are directly
    comparable in the tracker.

    Parameters
    ----------
    adapter_path : path to a PEFT adapter, or None (scores the base model / mock).
    generate_fn  : injectable generator for offline testing.
    """
    from evaluation.checkpoint_eval import (
        HFCheckpointGenerator,
        evaluate_checkpoint,
        load_eval_samples,
    )

    eval_cfg = cfg.get("evaluation", {})
    model_cfg = cfg["model"]
    sample_size = eval_cfg.get("sample_size", 6)

    logger.info("=== Stage 3: Evaluate (shared metric suite) ===")
    logger.info("Loading %d eval samples from sft_test.jsonl…", sample_size)
    samples = load_eval_samples(sample_size)
    logger.info("Loaded %d samples", len(samples))

    if generate_fn is None:
        if adapter_path is None:
            logger.warning(
                "No adapter path and no GPU — generating with base model on CPU. "
                "This may be very slow or OOM on a small machine."
            )
        generate_fn = HFCheckpointGenerator(
            base_model_id=model_cfg["base_model_id"],
            adapter_path=adapter_path,
            max_new_tokens=eval_cfg.get("max_new_tokens", 512),
            temperature=eval_cfg.get("temperature", 0.0),
        )

    agg = evaluate_checkpoint(generate_fn, samples, log_to_mlflow=True)
    logger.info(
        "Metric-suite eval complete — avg composite=%.3f",
        agg.get("composite_score", 0.0),
    )
    return agg


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    stage: str = "all",
    adapter_path: str | None = None,
    generate_fn=None,
) -> dict:
    """Run the C4 pipeline (one or all stages), logging to MLflow.

    Parameters
    ----------
    config_path  : path to c4_rlhf_preference_opt.yaml.
    stage        : "reward_model", "dpo", "evaluate", or "all".
    adapter_path : pre-existing adapter to evaluate (skips training).
    generate_fn  : injectable generator for offline testing.

    Returns
    -------
    dict with keys: ``condition_id``, ``probe_report``, ``dpo_metrics``,
    ``adapter_path``, ``eval_metrics``.
    """
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    mlflow_cfg = cfg["mlflow"]

    mlflow.set_tracking_uri(
        os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db")
    )
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    run_name = f"{mlflow_cfg['run_name_prefix']}_{stage}"
    results: dict = {
        "condition_id": exp_cfg["condition_id"],
        "probe_report": {},
        "dpo_metrics": {},
        "adapter_path": adapter_path,
        "eval_metrics": {},
    }

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "condition_id": exp_cfg["condition_id"],
            "base_model": cfg["model"]["base_model_id"],
            "prior_checkpoint": cfg["model"].get("prior_checkpoint", "none"),
            "stage": stage,
        })

        probe = None

        # ── Stage 1: Reward model ──
        if stage in ("reward_model", "all"):
            rm_result = run_reward_model(cfg)
            probe = rm_result.get("probe")
            results["probe_report"] = {
                "train_report": rm_result.get("train_report", {}),
                "val_report": rm_result.get("val_report", {}),
                "probe_path": rm_result.get("probe_path"),
            }

        # ── Stage 2: DPO ──
        if stage in ("dpo", "all"):
            trained_path, dpo_metrics = run_dpo(cfg, probe=probe)
            if trained_path:
                adapter_path = trained_path
                results["adapter_path"] = adapter_path
            results["dpo_metrics"] = dpo_metrics

        # ── Stage 3: Evaluate ──
        if stage in ("evaluate", "all"):
            if generate_fn is not None or _gpu_available() or adapter_path:
                results["eval_metrics"] = run_evaluate(
                    cfg,
                    adapter_path=adapter_path,
                    generate_fn=generate_fn,
                )
            else:
                logger.warning(
                    "Evaluation skipped — no GPU, no adapter, and no generator injected. "
                    "Provide --adapter or run on a GPU node to evaluate the checkpoint."
                )

    return results


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="C4: Personality-Focused RLHF — reward probe + DPO + evaluation"
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="Path to c4_rlhf_preference_opt.yaml")
    parser.add_argument(
        "--stage",
        choices=["reward_model", "dpo", "evaluate", "all"],
        default="all",
        help="Which stage(s) to run (default: all)"
    )
    parser.add_argument("--adapter", default=None,
                        help="Existing adapter path to evaluate (skips DPO training)")
    args = parser.parse_args()

    results = run(args.config, stage=args.stage, adapter_path=args.adapter)

    print("\n=== C4 RLHF Results ===")
    probe_rep = results.get("probe_report", {})
    train_rep = probe_rep.get("train_report", {})
    val_rep = probe_rep.get("val_report", {})
    if train_rep:
        print(f"  probe_train_accuracy : {train_rep.get('train_accuracy', 'n/a'):.3f}  (n={train_rep.get('n_samples', '?')})")
    if val_rep:
        print(f"  probe_val_accuracy   : {val_rep.get('accuracy', 'n/a'):.3f}  (n={val_rep.get('n_samples', '?')})")
    if results["adapter_path"]:
        print(f"  adapter_path         : {results['adapter_path']}")
    agg = results["eval_metrics"]
    if agg:
        print(f"  composite_score      : {agg.get('composite_score', 0.0):.3f}")
        print(f"  persona_adherence    : {agg.get('persona_adherence', 0.0):.3f}")
    print("\nMLflow UI: mlflow ui --backend-store-uri sqlite:///research/tracking/mlflow.db")
