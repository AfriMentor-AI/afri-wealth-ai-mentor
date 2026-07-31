"""MLflow experiment registry for AfriMentor AI Proposal 1 (card D1.4).

Run this once to create all 4 alignment condition experiments in MLflow:
    python research/tracking/setup_mlflow.py

The MLflow server is started via docker-compose (see tracking/mlflow.Dockerfile).
In local dev without Docker, MLflow uses a local SQLite backend + artifact store.
"""
from __future__ import annotations

import os

import mlflow

# ── Server config ─────────────────────────────────────────────────────────────
# In docker-compose: MLFLOW_TRACKING_URI=http://mlflow:5000
# In local dev:      defaults to local SQLite + ./mlruns artifact store
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db")
ARTIFACT_ROOT = os.getenv("MLFLOW_ARTIFACT_ROOT", "research/tracking/artifacts")

mlflow.set_tracking_uri(TRACKING_URI)

# ── Experiment definitions ─────────────────────────────────────────────────────
# Each dict maps to one Proposal 1 alignment condition.
# Tags follow the convention: condition_id, model_family, sprint.
EXPERIMENTS = [
    {
        "name": "C1_baseline_prompting",
        "tags": {
            "condition_id": "C1",
            "condition_name": "Baseline Prompting",
            "description": (
                "Zero-shot and few-shot prompting of the base model with the "
                "Chioma persona system prompt. No weight updates. Establishes "
                "the performance floor for all other conditions."
            ),
            "model_family": "Qwen2.5-7B / Llama-3.1-8B",
            "sprint": "3",
            "requires_gpu": "false",
        },
    },
    {
        "name": "C2_supervised_persona_finetuning",
        "tags": {
            "condition_id": "C2",
            "condition_name": "Supervised Persona Fine-Tuning",
            "description": (
                "QLoRA supervised fine-tuning on curated Chioma persona "
                "conversation demonstrations. Trains the model to adopt the "
                "Chioma voice, cultural fluency, and financial domain knowledge "
                "via next-token prediction on high-quality examples."
            ),
            "model_family": "Qwen2.5-7B / Llama-3.1-8B",
            "sprint": "4",
            "requires_gpu": "true",
            "adapter_type": "LoRA/QLoRA",
        },
    },
    {
        "name": "C3_persona_contrastive_learning",
        "tags": {
            "condition_id": "C3",
            "condition_name": "Persona-Aware Contrastive Learning",
            "description": (
                "Contrastive fine-tuning using (chosen, rejected) response pairs "
                "where chosen responses exhibit strong Chioma persona alignment "
                "and rejected responses are generic or culturally misaligned. "
                "Uses DPO loss without a reward model."
            ),
            "model_family": "Qwen2.5-7B / Llama-3.1-8B",
            "sprint": "4",
            "requires_gpu": "true",
            "adapter_type": "DPO",
            "depends_on": "C2 SFT checkpoint (warm-start)",
        },
    },
    {
        "name": "C4_rlhf_preference_optimization",
        "tags": {
            "condition_id": "C4",
            "condition_name": "RLHF / Preference Optimization",
            "description": (
                "Full RLHF pipeline: train a reward model on human preference "
                "annotations, then run PPO to optimise the policy against the "
                "reward signal. Targets persona constraint adherence, cultural "
                "fluency, and anti-dependency behaviour as reward dimensions."
            ),
            "model_family": "Qwen2.5-7B / Llama-3.1-8B",
            "sprint": "5",
            "requires_gpu": "true",
            "adapter_type": "PPO + reward model",
            "depends_on": "C3 DPO checkpoint (warm-start)",
        },
    },
]


def setup_experiments() -> None:
    print(f"MLflow tracking URI: {TRACKING_URI}")
    for exp in EXPERIMENTS:
        existing = mlflow.get_experiment_by_name(exp["name"])
        if existing:
            print(f"  EXISTS   {exp['name']} (id={existing.experiment_id})")
            continue
        exp_id = mlflow.create_experiment(
            name=exp["name"],
            artifact_location=f"{ARTIFACT_ROOT}/{exp['name']}",
            tags=exp["tags"],
        )
        print(f"  CREATED  {exp['name']} (id={exp_id})")


if __name__ == "__main__":
    setup_experiments()
    print("\nAll experiments registered. Open MLflow UI:")
    print("  mlflow ui --backend-store-uri", TRACKING_URI)
