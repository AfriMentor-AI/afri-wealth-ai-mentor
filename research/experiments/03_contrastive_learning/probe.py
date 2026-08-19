"""Card C3.3 — persona-vector probing runner.

Extracts per-trait persona vectors from the C3 model's activations and reports how
well they separate held-out persona markers — the latent-space layer of the metric
suite. Warm-starts from the same base (+ optional C3 DPO adapter) as the runner in
``run.py``; the heavy extraction requires a GPU/model node.

This is a **separate** entry point from ``run.py`` on purpose: the probing pipeline
lives in the shared, import-only module ``research/evaluation/persona_probe.py`` and
this thin CLI just wires config → extractor → MLflow, so it neither depends on nor
collides with the DPO training/eval runner.

Usage (on a GPU node):
    python research/experiments/03_contrastive_learning/probe.py
    python research/experiments/03_contrastive_learning/probe.py \
        --adapter research/experiments/03_contrastive_learning/checkpoints/final
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import mlflow
import yaml

sys.path.insert(0, str(Path(__file__).parents[2]))  # research/ root -> evaluation.*

_RESEARCH_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _RESEARCH_ROOT.parent
DEFAULT_CONFIG = _RESEARCH_ROOT / "configs" / "c3_contrastive_learning.yaml"


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _resolve(path_str: str) -> Path:
    """Resolve a config path (repo-relative or absolute) against the repo root."""
    p = Path(path_str)
    return p if p.is_absolute() else _REPO_ROOT / p


def run(
    config_path: str | Path = DEFAULT_CONFIG,
    adapter_path: str | None = None,
    out_path: str | None = None,
) -> dict | None:
    """Extract persona vectors from the C3 model and log the separation diagnostic.

    Returns the per-trait diagnostic report, or ``None`` when no GPU is available
    (safe no-op — never loads a 7B model on a CPU-only host, matching ``run.py``).
    """
    from evaluation.persona_probe import (
        HFActivationExtractor,
        build_contrastive_pairs,
        extract_persona_vectors,
        load_persona_profile,
        log_probe_to_mlflow,
        probe_separation,
    )

    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    model_cfg = cfg["model"]
    probe_cfg = cfg.get("probing", {})
    mlflow_cfg = cfg["mlflow"]

    try:
        import torch

        if not torch.cuda.is_available():
            print("WARNING: No CUDA GPU detected. C3.3 activation extraction needs a GPU node.")
            return None
    except ImportError:
        print("PyTorch not installed. Install requirements-gpu.txt on a GPU node.")
        return None

    profile = load_persona_profile(_resolve(probe_cfg.get("profile_path", "")))
    pairs = build_contrastive_pairs(
        profile,
        heldout_fraction=probe_cfg.get("heldout_fraction", 0.3),
        max_markers=probe_cfg.get("max_markers"),
    )

    adapter = adapter_path or model_cfg.get("dpo_checkpoint") or None
    extractor = HFActivationExtractor(
        base_model_id=model_cfg["base_model_id"],
        adapter_path=adapter,
        pooling=probe_cfg.get("pooling", "mean"),
        max_length=probe_cfg.get("max_length", 256),
    )

    mlflow.set_tracking_uri(
        os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db")
    )
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    with mlflow.start_run(run_name=f"{mlflow_cfg['run_name_prefix']}_persona_probe"):
        mlflow.log_params({
            "condition_id": exp_cfg["condition_id"],
            "base_model": model_cfg["base_model_id"],
            "probe_adapter": adapter or "base",
            "probe_pooling": probe_cfg.get("pooling", "mean"),
            "probe_traits": len(pairs),
            "profile_version": profile.get("profile_version", "unknown"),
        })

        vector_set = extract_persona_vectors(
            pairs,
            extractor,
            pooling=probe_cfg.get("pooling", "mean"),
            profile_version=profile.get("profile_version", "unknown"),
        )
        report = probe_separation(vector_set, pairs, extractor)  # sets best_layer
        log_probe_to_mlflow(report)

        out = _resolve(out_path or probe_cfg.get(
            "output_path",
            "research/experiments/03_contrastive_learning/checkpoints/persona_vectors.npz",
        ))
        vector_set.save(out)
        if mlflow_cfg.get("log_artifacts"):
            mlflow.log_artifact(str(out))
            mlflow.log_artifact(str(out) + ".meta.json")

        for trait, r in sorted(report.items()):
            print(f"  {trait:<22} best_layer={r['best_layer']:>3} "
                  f"acc={r['best_accuracy']:.3f} margin={r['best_margin']:+.3f} "
                  f"({r['slice']})")
        print(f"C3.3 persona probing complete. Vectors saved to {out}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="C3.3 persona-vector probing")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--adapter", default=None, help="PEFT adapter path (default: base model)")
    parser.add_argument("--out", default=None, help="output .npz path for persona vectors")
    args = parser.parse_args()
    run(args.config, adapter_path=args.adapter, out_path=args.out)
