"""Condition C3 — Persona-Aware Contrastive Learning runner (card C3.1).

DPO fine-tuning on (chosen, rejected) persona response pairs, warm-started from
the C2 SFT checkpoint, followed by evaluation of the trained checkpoint against
the **shared metric suite** — the same 5-dimension rubric + ROUGE-L/BERTScore
that C1 and C2 use. That second stage is card C3.1's acceptance criterion:

    "Contrastive-learning checkpoint produced and evaluated against the same
     metric suite."

Because the eval logs the **same MLflow metric keys as C1/C2**
(``avg_persona_adherence`` … ``avg_composite_score``), the three conditions line
up directly in the tracker for comparison.

Two stages, two environments:
  * ``train()``  — DPO via TRL. GPU node only (torch/trl/peft imported lazily).
  * ``evaluate()`` — generate from the checkpoint and score it. Runs wherever the
    model can generate; generation is injectable so the scoring path is testable
    offline without loading a 7B model.

Usage (on a GPU node):
    # train, then evaluate the produced checkpoint
    python research/experiments/03_contrastive_learning/run.py

    # evaluate an already-trained adapter without retraining
    python research/experiments/03_contrastive_learning/run.py --eval-only \
        --adapter research/experiments/03_contrastive_learning/checkpoints/final
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import mlflow
import yaml

# Ensure research/ is on the path regardless of cwd, so `evaluation.*` resolves.
_RESEARCH_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_RESEARCH_ROOT))

from evaluation.checkpoint_eval import (  # noqa: E402
    HFCheckpointGenerator,
    evaluate_checkpoint,
    load_eval_samples,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEFAULT_CONFIG = _RESEARCH_ROOT / "configs" / "c3_contrastive_learning.yaml"


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _count_jsonl_lines(path: str | Path) -> int:
    """Number of non-blank lines in a JSONL file (0 if it does not exist)."""
    p = Path(path)
    if not p.exists():
        return 0
    with open(p) as f:
        return sum(1 for line in f if line.strip())


def _gpu_available() -> bool:
    """True only if torch is installed and a CUDA device is visible."""
    try:
        import torch
    except ImportError:
        logger.warning("PyTorch not installed. Install requirements-gpu.txt on a GPU node.")
        return False
    if not torch.cuda.is_available():
        logger.warning("No CUDA GPU detected. C3 DPO training requires a GPU node.")
        return False
    return True


# ── Training (GPU node) ────────────────────────────────────────────────────────

def train(cfg: dict) -> tuple[str | None, dict]:
    """Run DPO fine-tuning. GPU node only.

    Returns ``(adapter_path, dpo_eval_metrics)``. When no GPU is available the
    training is skipped and ``(None, {})`` is returned so the caller can decide
    what to do (the heavy torch/trl/peft imports live here, not at module top).

    Robust to an empty validation split: ``dpo_val.jsonl`` may legitimately be
    empty before the data pipeline has produced held-out pairs, in which case
    in-loop evaluation is disabled rather than crashing the trainer.
    """
    if not _gpu_available():
        return None, {}

    import torch
    from datasets import load_dataset
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import DPOConfig, DPOTrainer

    model_cfg = cfg["model"]
    dpo_cfg = cfg["dpo"]
    train_cfg = cfg["training"]
    bnb_cfg = cfg["quantization"]

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=bnb_cfg["load_in_4bit"],
        bnb_4bit_compute_dtype=getattr(torch, bnb_cfg["bnb_4bit_compute_dtype"]),
        bnb_4bit_quant_type=bnb_cfg["bnb_4bit_quant_type"],
        bnb_4bit_use_double_quant=bnb_cfg["bnb_4bit_use_double_quant"],
    )

    # Base model + SFT adapter = the DPO policy (warm start from C2).
    base_model = AutoModelForCausalLM.from_pretrained(
        model_cfg["base_model_id"],
        quantization_config=bnb_config,
        device_map="auto",
    )
    # is_trainable=True is required: PeftModel.from_pretrained defaults to
    # inference mode (every loaded adapter param gets requires_grad=False),
    # since loading a checkpoint for further training isn't the common case.
    # Without it: "element 0 of tensors does not require grad and does not
    # have a grad_fn" the moment loss.backward() is called.
    model = PeftModel.from_pretrained(base_model, model_cfg["sft_checkpoint"], is_trainable=True)
    tokenizer = AutoTokenizer.from_pretrained(model_cfg["base_model_id"])
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # An empty val split is valid (data pipeline may not have produced held-out
    # pairs yet) — train without in-loop eval rather than letting datasets choke.
    has_val = _count_jsonl_lines(dpo_cfg["eval_dataset"]) > 0
    data_files = {"train": dpo_cfg["dataset"]}
    if has_val:
        data_files["validation"] = dpo_cfg["eval_dataset"]
    else:
        logger.warning(
            "Validation split %s is empty — disabling in-loop DPO evaluation.",
            dpo_cfg["eval_dataset"],
        )
    dataset = load_dataset("json", data_files=data_files)

    # Gradient checkpointing's backward-pass recompute doesn't reliably match
    # shapes when `device_map="auto"` has sharded the model across multiple
    # GPUs (confirmed live: `torch.utils.checkpoint.CheckpointError:
    # Recomputed values ... have different metadata` on a 2xT4 session) — only
    # safe to enable on a single GPU, where it's still a real OOM mitigation
    # for a 7B QLoRA model with no prepare_model_for_kbit_training call.
    use_grad_checkpointing = torch.cuda.device_count() <= 1

    dpo_config = DPOConfig(
        output_dir=model_cfg["output_dir"],
        num_train_epochs=train_cfg["num_train_epochs"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
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

    # No peft_config here deliberately: `model` is already the canonical C2 adapter
    # loaded as a PeftModel. Passing peft_config alongside an existing PeftModel
    # makes trl call model.merge_and_unload() first — unsupported on a 4-bit
    # quantized base (confirmed via trl source on the actual installed build) and
    # would crash before training starts. Continuing to train the existing SFT
    # adapter under the DPO objective is also the correct read of "warm-start
    # from C2" anyway, not "merge it away and train a fresh one."
    trainer = DPOTrainer(
        model=model,
        args=dpo_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"] if has_val else None,
        processing_class=tokenizer,  # tokenizer= is deprecated on this trl build (confirmed on SFTTrainer; same base class)
    )

    trainer.train()
    adapter_path = f"{model_cfg['output_dir']}/final"
    trainer.save_model(adapter_path)

    # DPO-loss metrics (reward margins, accuracies) — kept for the run, but they
    # are NOT the persona metric suite; the AC is satisfied by evaluate() below.
    dpo_eval: dict = {}
    if has_val:
        dpo_eval = {k.replace("eval_", "dpo_"): v for k, v in trainer.evaluate().items()}

    logger.info("C3 DPO training complete. Adapter saved to %s", adapter_path)
    return adapter_path, dpo_eval


# ── Evaluation (the acceptance criterion) ──────────────────────────────────────

def evaluate(
    cfg: dict,
    adapter_path: str | None = None,
    generate_fn=None,
    log_to_mlflow: bool = True,
) -> dict:
    """Score a checkpoint against the shared metric suite; return the aggregate.

    Generation is injectable via ``generate_fn`` (for offline tests). In a real
    run it is ``None``, so a :class:`HFCheckpointGenerator` loads the base model +
    ``adapter_path`` on the GPU. Assumes an MLflow run is already active (opened
    by :func:`run`) so the ``avg_*`` metrics attach to the C3 run.
    """
    eval_cfg = cfg.get("evaluation", {})
    sample_size = eval_cfg.get("sample_size", 6)
    samples = load_eval_samples(sample_size)
    logger.info("Loaded %d eval samples for the metric suite", len(samples))

    if generate_fn is None:
        model_cfg = cfg["model"]
        generate_fn = HFCheckpointGenerator(
            base_model_id=model_cfg["base_model_id"],
            adapter_path=adapter_path,
            max_new_tokens=eval_cfg.get("max_new_tokens", 512),
            temperature=eval_cfg.get("temperature", 0.0),
        )

    agg = evaluate_checkpoint(generate_fn, samples, log_to_mlflow=log_to_mlflow)
    logger.info("Metric-suite eval complete — avg composite=%.3f",
                agg.get("composite_score", 0.0))
    return agg


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    do_train: bool = True,
    do_eval: bool = True,
    adapter_path: str | None = None,
    generate_fn=None,
) -> dict:
    """Train (optional) then evaluate the C3 checkpoint, logging both to one run.

    A single MLflow run carries the C3 params, the DPO-loss metrics, and the
    shared metric-suite results, so C3 is one comparable row against C1/C2.

    Returns a results dict: ``condition_id``, ``trained``, ``adapter_path``,
    ``dpo_eval``, ``eval_metrics``.
    """
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    model_cfg = cfg["model"]
    dpo_cfg = cfg["dpo"]
    train_cfg = cfg["training"]
    mlflow_cfg = cfg["mlflow"]

    mlflow.set_tracking_uri(
        os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db")
    )
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    run_name = f"{mlflow_cfg['run_name_prefix']}_dpo_beta{dpo_cfg['beta']}"
    results: dict = {
        "condition_id": exp_cfg["condition_id"],
        "trained": False,
        "adapter_path": adapter_path,
        "dpo_eval": {},
        "eval_metrics": {},
    }

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "condition_id": exp_cfg["condition_id"],
            "base_model": model_cfg["base_model_id"],
            "sft_checkpoint": model_cfg["sft_checkpoint"],
            "dpo_beta": dpo_cfg["beta"],
            "loss_type": dpo_cfg["loss_type"],
            "epochs": train_cfg["num_train_epochs"],
            "lr": train_cfg["learning_rate"],
            "eval_sample_size": cfg.get("evaluation", {}).get("sample_size", 6),
        })

        if do_train:
            trained_path, dpo_eval = train(cfg)
            if trained_path:
                results["trained"] = True
                results["adapter_path"] = adapter_path = trained_path
                results["dpo_eval"] = dpo_eval
                if dpo_eval:
                    mlflow.log_metrics(dpo_eval)
            elif generate_fn is None:
                # No GPU and no injected generator → cannot generate to score.
                # Bail rather than silently loading a 7B model on CPU.
                logger.warning(
                    "Training skipped (no GPU) and no generator provided; "
                    "skipping metric-suite evaluation."
                )
                do_eval = False

        if do_eval:
            results["eval_metrics"] = evaluate(
                cfg, adapter_path=adapter_path, generate_fn=generate_fn
            )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="C3 persona-aware contrastive learning (DPO)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--eval-only", action="store_true",
                        help="Skip DPO training; evaluate an existing checkpoint")
    parser.add_argument("--adapter", default=None,
                        help="Adapter path to evaluate (with --eval-only)")
    args = parser.parse_args()

    results = run(
        args.config,
        do_train=not args.eval_only,
        adapter_path=args.adapter,
    )

    print("\n=== C3 Contrastive Learning Results ===")
    print(f"  trained:      {results['trained']}")
    print(f"  adapter_path: {results['adapter_path']}")
    if results["dpo_eval"]:
        print(f"  DPO loss:     {results['dpo_eval'].get('dpo_loss', 'n/a')}")
    agg = results["eval_metrics"]
    if agg:
        print(f"  composite:    {agg.get('composite_score', 0.0):.3f}")
        print(f"  persona:      {agg.get('persona_adherence', 0.0):.3f}")
    print("\nMLflow UI: mlflow ui --backend-store-uri sqlite:///research/tracking/mlflow.db")
