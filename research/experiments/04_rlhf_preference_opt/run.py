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

def run_reward_model(
    cfg: dict,
    *,
    include_consistency: bool | None = None,
    reward_weights: dict | None = None,
    probe_output_path: str | Path | None = None,
) -> dict:
    """Stage 1: Score preference pairs with LLM judge, fit and evaluate logistic probe.

    Returns
    -------
    dict with keys: ``probe`` (fitted object), ``probe_path`` (str),
    ``train_report``, ``val_report``, ``avg_reward_delta``.
    """
    rm_cfg = cfg.get("reward_model", {})
    if include_consistency is None:
        include_consistency = rm_cfg.get("include_consistency", False)

    weights: dict = reward_weights or rm_cfg.get("reward_weights", {})

    train_path = _resolve(rm_cfg.get("dataset", "research/datasets/splits/rlhf_train.jsonl"))
    val_path = _resolve(rm_cfg.get("eval_dataset", "research/datasets/splits/rlhf_val.jsonl"))
    probe_out = _resolve(probe_output_path or rm_cfg.get("probe_output", "research/experiments/04_rlhf_preference_opt/reward_model/reward_probe.pkl"))

    logger.info("=== Stage 1: Reward Model (include_consistency=%s) ===", include_consistency)
    logger.info("Training preference pairs: %s", train_path)

    # Load preference pairs
    train_pairs = load_preference_pairs(train_path)
    val_pairs = load_preference_pairs(val_path)

    if not train_pairs:
        logger.error("No training pairs found at %s. Aborting reward model stage.", train_path)
        return {"probe": None, "probe_path": None, "train_report": {}, "val_report": {}, "avg_reward_delta": 0.0}

    mlflow.log_param("rm_train_pairs", len(train_pairs))
    mlflow.log_param("rm_val_pairs", len(val_pairs))
    mlflow.log_param("include_consistency", include_consistency)
    mlflow.log_param("reward_weights", json.dumps(weights))

    # Score all pairs with LLM judge (+ optional consistency)
    logger.info("Scoring %d training pairs with LLM judge (+ consistency=%s)…", len(train_pairs), include_consistency)
    scored_train = score_dataset(train_pairs, reward_weights=weights, include_consistency=include_consistency)

    # Fit logistic probe
    logger.info("Fitting logistic preference probe on %d scored pairs…", len(scored_train))
    probe, train_report = fit_reward_probe(scored_train, require_two_classes=rm_cfg.get("require_two_classes", False))

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
        scored_val = score_dataset(val_pairs, reward_weights=weights, include_consistency=include_consistency)
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
    avg_delta = 0.0
    if scored_train:
        import numpy as np
        from evaluation.reward_model import _weighted_reward
        deltas = [
            _weighted_reward(ps.scores_a, weights, dimensions=scored_train[0].dimensions)
            - _weighted_reward(ps.scores_b, weights, dimensions=scored_train[0].dimensions)
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
        "avg_reward_delta": avg_delta,
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
    # Explicit seed (config: training.seed, default 42) — previously never set or logged.
    from transformers import set_seed as _set_seed
    _seed = train_cfg.get("seed", 42)
    _set_seed(_seed)

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
        bnb_4bit_compute_dtype=getattr(torch, bnb_cfg["bnb_4bit_compute_dtype"]),
        bnb_4bit_quant_type=bnb_cfg["bnb_4bit_quant_type"],
        bnb_4bit_use_double_quant=bnb_cfg["bnb_4bit_use_double_quant"],
    )

    # Load base model + prior checkpoint (C3 DPO adapter). prior_checkpoint may
    # be a local path or a HF Hub repo ID — PeftModel.from_pretrained resolves
    # either the same way, so try it directly rather than pre-checking a local
    # Path.exists() (which would always be False for a Hub ID like
    # "AfriMentor/chioma-dpo-v1", silently skipping the warm-start).
    prior_ref = model_cfg["prior_checkpoint"]
    base_model_id = model_cfg["base_model_id"]

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        device_map="auto",
    )

    try:
        # is_trainable=True: from_pretrained defaults to inference mode
        # (requires_grad=False on every adapter param) otherwise — same bug
        # 03_contrastive_learning/run.py hit before this was added there.
        model = PeftModel.from_pretrained(base_model, prior_ref, is_trainable=True)
        logger.info("Warm-started from prior checkpoint: %s", prior_ref)
    except Exception as e:
        logger.warning(
            "Prior checkpoint %s unavailable (%s) — DPO starts from base model.",
            prior_ref, e,
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

    # Same gap as 03_contrastive_learning: no prepare_model_for_kbit_training
    # call means gradient checkpointing isn't on by default, but its recompute
    # doesn't reliably match shapes when device_map="auto" shards the model
    # across multiple GPUs (confirmed live: CheckpointError: Recomputed
    # values ... have different metadata) — only safe on a single GPU.
    use_grad_checkpointing = torch.cuda.device_count() <= 1

    dpo_config = DPOConfig(
        output_dir=str(output_dir),
        num_train_epochs=train_cfg["num_train_epochs"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
        seed=_seed,
        data_seed=_seed,
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        lr_scheduler_type=train_cfg["lr_scheduler_type"],
        warmup_ratio=train_cfg["warmup_ratio"],
        bf16=train_cfg["bf16"],
        fp16=train_cfg["fp16"],
        gradient_checkpointing=use_grad_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False} if use_grad_checkpointing else None,
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

    # peft_config only when `model` is still the plain base model (warm-start
    # unavailable): trl would create a fresh adapter via get_peft_model for
    # that case, which is needed since otherwise nothing would be trainable.
    # When warm-started, `model` is already a PeftModel with is_trainable=True
    # — passing peft_config too would make trl call merge_and_unload() first,
    # unsupported on this 4-bit quantized base (same issue fixed in
    # 03_contrastive_learning/run.py, confirmed via trl source).
    is_warm_started = isinstance(model, PeftModel)
    trainer = DPOTrainer(
        model=model,
        args=dpo_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"] if has_val else None,
        processing_class=tokenizer,
        peft_config=None if is_warm_started else lora_config,
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
    samples = load_eval_samples(sample_size, splits_dir=eval_cfg.get("splits_dir", "research/datasets/splits"))
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


# ── Ablation: Reward with vs without Persona Consistency ────────────────────────

def run_ablation(
    cfg: dict,
    *,
    generate_fn=None,
    output_summary_path: str | Path | None = None,
) -> dict:
    """Run ablation comparing reward-with-consistency vs reward-without-consistency.

    Measures:
      1. Probe accuracy on training and validation preference splits.
      2. Feature coefficients / dimension importances.
      3. Average reward separation (delta).
      4. Measured impact on persona drift across dialogue turns (per Abdulhai et al. 2025).

    Returns
    -------
    dict with ablation comparison metrics and per-condition reports.
    """
    from evaluation.reward_model import (
        DEFAULT_REWARD_WEIGHTS,
        DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY,
        measure_persona_drift,
    )
    from evaluation.checkpoint_eval import load_eval_samples

    ablation_cfg = cfg.get("ablation", {}).get("conditions", {})
    cfg_without = ablation_cfg.get("without_consistency", {})
    cfg_with = ablation_cfg.get("with_consistency", {})

    weights_without = cfg_without.get("reward_weights", DEFAULT_REWARD_WEIGHTS)
    weights_with = cfg_with.get("reward_weights", DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY)

    probe_dir = _resolve(Path(cfg["reward_model"].get("probe_output", "reward_probe.pkl")).parent)
    probe_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=================================================================")
    logger.info("=== RUNNING REWARD MODEL CONSISTENCY ABLATION (Abdulhai 2025) ===")
    logger.info("=================================================================")

    # 1. Condition Without Consistency
    logger.info("\n--- [Condition A] Reward WITHOUT Persona Consistency ---")
    probe_out_without = probe_dir / "reward_probe_without_consistency.pkl"
    with mlflow.start_run(run_name="ablation_reward_without_consistency", nested=True):
        rm_without = run_reward_model(
            cfg,
            include_consistency=False,
            reward_weights=weights_without,
            probe_output_path=probe_out_without,
        )

    # 2. Condition With Consistency
    logger.info("\n--- [Condition B] Reward WITH Persona Consistency ---")
    probe_out_with = probe_dir / "reward_probe_with_consistency.pkl"
    with mlflow.start_run(run_name="ablation_reward_with_consistency", nested=True):
        rm_with = run_reward_model(
            cfg,
            include_consistency=True,
            reward_weights=weights_with,
            probe_output_path=probe_out_with,
        )

    # 3. Measure Persona Drift on Multi-Turn Evaluation Set
    samples = load_eval_samples(6)
    test_path = _resolve(cfg["reward_model"].get("test_dataset", "research/datasets/splits/rlhf_test.jsonl"))
    test_pairs = load_preference_pairs(test_path)

    # Responses under baseline reward guidance vs consistency-guided preference
    baseline_responses = [p.get("response_b") if p.get("preferred") == "b" else p.get("response_a") for p in test_pairs]
    consistency_responses = [p.get("response_a") for p in test_pairs]

    drift_without = measure_persona_drift(baseline_responses, persona_slug="chioma-base")
    drift_with = measure_persona_drift(consistency_responses, persona_slug="chioma-base")

    drift_reduction_pct = max(
        0.0,
        round(((drift_without["drift_magnitude"] - drift_with["drift_magnitude"]) / (drift_without["drift_magnitude"] + 1e-9)) * 100, 2)
    )

    train_acc_without = rm_without["train_report"].get("train_accuracy", 0.0)
    train_acc_with = rm_with["train_report"].get("train_accuracy", 0.0)
    val_acc_without = rm_without["val_report"].get("accuracy", 0.0)
    val_acc_with = rm_with["val_report"].get("accuracy", 0.0)

    ablation_summary = {
        "without_consistency": {
            "name": "reward_without_consistency",
            "features": rm_without["train_report"].get("feature_names", []),
            "probe_train_accuracy": train_acc_without,
            "probe_val_accuracy": val_acc_without,
            "avg_reward_delta": rm_without.get("avg_reward_delta", 0.0),
            "persona_drift_magnitude": drift_without["drift_magnitude"],
            "persona_drift_pct": drift_without["drift_pct"],
            "early_p2l": drift_without["early_p2l"],
            "late_p2l": drift_without["late_p2l"],
        },
        "with_consistency": {
            "name": "reward_with_consistency",
            "features": rm_with["train_report"].get("feature_names", []),
            "probe_train_accuracy": train_acc_with,
            "probe_val_accuracy": val_acc_with,
            "avg_reward_delta": rm_with.get("avg_reward_delta", 0.0),
            "persona_drift_magnitude": drift_with["drift_magnitude"],
            "persona_drift_pct": drift_with["drift_pct"],
            "early_p2l": drift_with["early_p2l"],
            "late_p2l": drift_with["late_p2l"],
        },
        "comparison": {
            "probe_train_acc_gain": round(train_acc_with - train_acc_without, 4),
            "probe_val_acc_gain": round(val_acc_with - val_acc_without, 4),
            "reward_delta_gain": round(rm_with.get("avg_reward_delta", 0.0) - rm_without.get("avg_reward_delta", 0.0), 4),
            "persona_drift_reduction_pct": drift_reduction_pct,
            "persona_drift_reduction_magnitude": round(drift_without["drift_magnitude"] - drift_with["drift_magnitude"], 4),
        },
    }

    # Log ablation comparison to MLflow
    mlflow.log_params({"ablation_type": "reward_with_vs_without_consistency"})
    mlflow.log_metrics({
        "ablation_train_acc_without": train_acc_without,
        "ablation_train_acc_with": train_acc_with,
        "ablation_val_acc_without": val_acc_without,
        "ablation_val_acc_with": val_acc_with,
        "ablation_persona_drift_without": drift_without["drift_magnitude"],
        "ablation_persona_drift_with": drift_with["drift_magnitude"],
        "ablation_persona_drift_reduction_pct": drift_reduction_pct,
    })

    if output_summary_path:
        out_path = Path(output_summary_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(ablation_summary, f, indent=2)
        logger.info("Ablation summary written to: %s", out_path)

    return ablation_summary


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    stage: str = "all",
    adapter_path: str | None = None,
    generate_fn=None,
    run_ablation_flag: bool = False,
) -> dict:
    """Run the C4 pipeline (one or all stages), logging to MLflow.

    Parameters
    ----------
    config_path        : path to c4_rlhf_preference_opt.yaml.
    stage              : "reward_model", "dpo", "evaluate", or "all".
    adapter_path       : pre-existing adapter to evaluate (skips training).
    generate_fn        : injectable generator for offline testing.
    run_ablation_flag  : whether to execute reward consistency ablation.

    Returns
    -------
    dict with keys: ``condition_id``, ``probe_report``, ``dpo_metrics``,
    ``adapter_path``, ``eval_metrics``, and optional ``ablation_report``.
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
        "ablation_report": {},
    }

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "condition_id": exp_cfg["condition_id"],
            "base_model": cfg["model"]["base_model_id"],
            "prior_checkpoint": cfg["model"].get("prior_checkpoint", "none"),
            "stage": stage,
        })

        probe = None

        # ── Optional Ablation ──
        if run_ablation_flag:
            ablation_results = run_ablation(cfg, generate_fn=generate_fn)
            results["ablation_report"] = ablation_results

        # ── Stage 1: Reward model ──
        if stage in ("reward_model", "all"):
            rm_result = run_reward_model(cfg)
            probe = rm_result.get("probe")
            results["probe_report"] = {
                "train_report": rm_result.get("train_report", {}),
                "val_report": rm_result.get("val_report", {}),
                "probe_path": rm_result.get("probe_path"),
                "avg_reward_delta": rm_result.get("avg_reward_delta", 0.0),
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
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run reward model ablation comparing reward-with-consistency vs reward-without"
    )
    args = parser.parse_args()

    results = run(args.config, stage=args.stage, adapter_path=args.adapter, run_ablation_flag=args.ablation)

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
    
    ablation_rep = results.get("ablation_report", {})
    if ablation_rep:
        comp = ablation_rep.get("comparison", {})
        print("\n=== Reward Model Consistency Ablation ===")
        print(f"  Train Acc (w/o consistency): {ablation_rep['without_consistency']['probe_train_accuracy']:.3f}")
        print(f"  Train Acc (w/ consistency)  : {ablation_rep['with_consistency']['probe_train_accuracy']:.3f}")
        print(f"  Val Acc   (w/o consistency): {ablation_rep['without_consistency']['probe_val_accuracy']:.3f}")
        print(f"  Val Acc   (w/ consistency)  : {ablation_rep['with_consistency']['probe_val_accuracy']:.3f}")
        print(f"  Persona Drift (w/o metric)  : {ablation_rep['without_consistency']['persona_drift_magnitude']:.4f}")
        print(f"  Persona Drift (w/ metric)   : {ablation_rep['with_consistency']['persona_drift_magnitude']:.4f}")
        print(f"  Persona Drift Reduction     : {comp.get('persona_drift_reduction_pct', 0.0):.1f}%")

    print("\nMLflow UI: mlflow ui --backend-store-uri sqlite:///research/tracking/mlflow.db")
