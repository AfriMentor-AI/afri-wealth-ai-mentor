"""Condition C4 — RLHF / Preference Optimization runner (card D1.4).

Two-stage pipeline:
  Stage 1: Train a reward model on human preference annotations.
  Stage 2: PPO policy optimisation against the reward model.

Warm-starts from the C3 DPO checkpoint. Requires GPU.

Usage (on GPU node):
    python research/experiments/04_rlhf_preference_opt/run.py --stage reward_model
    python research/experiments/04_rlhf_preference_opt/run.py --stage ppo
    python research/experiments/04_rlhf_preference_opt/run.py --stage all
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import mlflow
import yaml

sys.path.insert(0, str(Path(__file__).parents[2]))

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "c4_rlhf_preference_opt.yaml"


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def train_reward_model(cfg: dict) -> None:
    """Stage 1: Train reward model on human preference annotations."""
    from datasets import load_dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, TrainingArguments, Trainer
    from peft import LoraConfig, get_peft_model
    import torch as _torch

    rm_cfg = cfg["reward_model"]
    mlflow.log_param("stage", "reward_model")
    mlflow.log_param("reward_weights", str(rm_cfg["reward_weights"]))

    tokenizer = AutoTokenizer.from_pretrained(rm_cfg["base_model_id"])
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForSequenceClassification.from_pretrained(
        rm_cfg["base_model_id"],
        num_labels=1,                       # scalar reward output
        device_map="auto",
    )

    dataset = load_dataset("json", data_files={
        "train": rm_cfg["dataset"],
        "validation": rm_cfg["eval_dataset"],
    })

    training_args = TrainingArguments(
        output_dir=rm_cfg["output_dir"],
        num_train_epochs=rm_cfg["num_train_epochs"],
        per_device_train_batch_size=rm_cfg["per_device_train_batch_size"],
        learning_rate=rm_cfg["learning_rate"],
        bf16=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        tokenizer=tokenizer,
    )
    trainer.train()
    trainer.save_model(f"{rm_cfg['output_dir']}/final")
    print(f"Reward model saved to {rm_cfg['output_dir']}/final")


def train_ppo(cfg: dict) -> None:
    """Stage 2: PPO policy optimisation against the reward model."""
    from datasets import load_dataset
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, pipeline
    from trl import PPOConfig, PPOTrainer, AutoModelForCausalLMWithValueHead
    import torch as _torch

    model_cfg = cfg["model"]
    ppo_cfg = cfg["ppo"]
    bnb_cfg = cfg["quantization"]
    rm_cfg = cfg["reward_model"]
    mlflow.log_param("stage", "ppo")
    mlflow.log_params({k: v for k, v in ppo_cfg.items() if not isinstance(v, dict)})

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=bnb_cfg["load_in_4bit"],
        bnb_4bit_compute_dtype=_torch.bfloat16,
        bnb_4bit_quant_type=bnb_cfg["bnb_4bit_quant_type"],
        bnb_4bit_use_double_quant=bnb_cfg["bnb_4bit_use_double_quant"],
    )

    tokenizer = AutoTokenizer.from_pretrained(model_cfg["base_model_id"])
    tokenizer.pad_token = tokenizer.eos_token

    # Policy model (warm-started from C3 DPO checkpoint)
    policy = AutoModelForCausalLMWithValueHead.from_pretrained(
        model_cfg["dpo_checkpoint"],
        quantization_config=bnb_config,
        device_map="auto",
    )

    # Reward pipeline
    reward_pipe = pipeline(
        "text-classification",
        model=f"{rm_cfg['output_dir']}/final",
        tokenizer=tokenizer,
        device_map="auto",
    )

    ppo_config = PPOConfig(
        learning_rate=ppo_cfg["learning_rate"],
        batch_size=ppo_cfg["batch_size"],
        mini_batch_size=ppo_cfg["mini_batch_size"],
        gradient_accumulation_steps=ppo_cfg["gradient_accumulation_steps"],
        ppo_epochs=ppo_cfg["ppo_epochs"],
        kl_penalty=ppo_cfg["kl_penalty"],
        init_kl_coef=ppo_cfg["init_kl_coef"],
        target=ppo_cfg["target_kl"],
    )

    trainer = PPOTrainer(
        config=ppo_config,
        model=policy,
        tokenizer=tokenizer,
    )

    # TODO Sprint 5: load prompts from rlhf_train split and run PPO loop
    # Scaffold is in place; full loop requires the preference dataset (Sprint 4-5)
    print("PPO trainer initialised. Full training loop runs in Sprint 5.")
    policy.save_pretrained(f"{model_cfg['output_dir']}/ppo_final")
    print(f"PPO policy saved to {model_cfg['output_dir']}/ppo_final")


def run(config_path: str | Path = DEFAULT_CONFIG, stage: str = "all") -> None:
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    mlflow_cfg = cfg["mlflow"]

    try:
        import torch
        if not torch.cuda.is_available():
            print("WARNING: No CUDA GPU detected. C4 RLHF requires a GPU node.")
            return
    except ImportError:
        print("PyTorch not installed. Install requirements-gpu.txt on a GPU node.")
        return

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db"))
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    run_name = f"{mlflow_cfg['run_name_prefix']}_{stage}"
    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("condition_id", exp_cfg["condition_id"])
        if stage in ("reward_model", "all"):
            train_reward_model(cfg)
        if stage in ("ppo", "all"):
            train_ppo(cfg)
    print(f"C4 RLHF stage '{stage}' complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--stage", choices=["reward_model", "ppo", "all"], default="all")
    args = parser.parse_args()
    run(args.config, args.stage)
