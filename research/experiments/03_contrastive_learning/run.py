"""Condition C3 — Persona-Aware Contrastive Learning runner (card D1.4).

DPO fine-tuning on (chosen, rejected) persona response pairs.
Warm-starts from the C2 SFT checkpoint. Requires GPU.

Usage (on GPU node):
    python research/experiments/03_contrastive_learning/run.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import mlflow
import yaml

sys.path.insert(0, str(Path(__file__).parents[2]))

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "c3_contrastive_learning.yaml"


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run(config_path: str | Path = DEFAULT_CONFIG) -> None:
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    model_cfg = cfg["model"]
    dpo_cfg = cfg["dpo"]
    train_cfg = cfg["training"]
    mlflow_cfg = cfg["mlflow"]

    try:
        import torch
        if not torch.cuda.is_available():
            print("WARNING: No CUDA GPU detected. C3 DPO requires a GPU node.")
            return
    except ImportError:
        print("PyTorch not installed. Install requirements-gpu.txt on a GPU node.")
        return

    from datasets import load_dataset
    from peft import LoraConfig, PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import DPOConfig, DPOTrainer
    import torch as _torch

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db"))
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    run_name = f"{mlflow_cfg['run_name_prefix']}_dpo_beta{cfg['dpo']['beta']}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "condition_id": exp_cfg["condition_id"],
            "base_model": model_cfg["base_model_id"],
            "sft_checkpoint": model_cfg["sft_checkpoint"],
            "dpo_beta": dpo_cfg["beta"],
            "loss_type": dpo_cfg["loss_type"],
            "epochs": train_cfg["num_train_epochs"],
            "lr": train_cfg["learning_rate"],
        })

        bnb_cfg = cfg["quantization"]
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=bnb_cfg["load_in_4bit"],
            bnb_4bit_compute_dtype=_torch.bfloat16,
            bnb_4bit_quant_type=bnb_cfg["bnb_4bit_quant_type"],
            bnb_4bit_use_double_quant=bnb_cfg["bnb_4bit_use_double_quant"],
        )

        # Load base model + SFT adapter as the policy model
        base_model = AutoModelForCausalLM.from_pretrained(
            model_cfg["base_model_id"],
            quantization_config=bnb_config,
            device_map="auto",
        )
        model = PeftModel.from_pretrained(base_model, model_cfg["sft_checkpoint"])
        tokenizer = AutoTokenizer.from_pretrained(model_cfg["base_model_id"])
        tokenizer.pad_token = tokenizer.eos_token

        lora_cfg = cfg["lora"]
        lora_config = LoraConfig(
            r=lora_cfg["r"],
            lora_alpha=lora_cfg["lora_alpha"],
            lora_dropout=lora_cfg["lora_dropout"],
            target_modules=lora_cfg["target_modules"],
            bias=lora_cfg["bias"],
            task_type=lora_cfg["task_type"],
        )

        dataset = load_dataset("json", data_files={
            "train": dpo_cfg["dataset"],
            "validation": dpo_cfg["eval_dataset"],
        })

        dpo_config = DPOConfig(
            output_dir=model_cfg["output_dir"],
            num_train_epochs=train_cfg["num_train_epochs"],
            per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
            gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
            learning_rate=train_cfg["learning_rate"],
            lr_scheduler_type=train_cfg["lr_scheduler_type"],
            warmup_ratio=train_cfg["warmup_ratio"],
            bf16=train_cfg["bf16"],
            logging_steps=train_cfg["logging_steps"],
            eval_steps=train_cfg["eval_steps"],
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
            eval_dataset=dataset["validation"],
            tokenizer=tokenizer,
            peft_config=lora_config,
        )

        trainer.train()
        trainer.save_model(f"{model_cfg['output_dir']}/final")

        eval_results = trainer.evaluate()
        mlflow.log_metrics({k.replace("eval_", ""): v for k, v in eval_results.items()})

        print(f"C3 DPO complete. Adapter saved to {model_cfg['output_dir']}/final")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    run(args.config)
