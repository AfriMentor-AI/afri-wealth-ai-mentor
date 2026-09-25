"""Condition C2 — Supervised Persona Fine-Tuning runner (card D1.4).

QLoRA fine-tuning of Qwen2.5-7B-Instruct on Chioma persona conversation
demonstrations. Requires GPU (RunPod / AWS EC2 g5.xlarge).

Usage (on GPU node):
    pip install -r research/requirements.txt -r research/requirements-gpu.txt
    python research/experiments/02_supervised_finetuning/run.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import mlflow
import yaml

sys.path.insert(0, str(Path(__file__).parents[2]))

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "c2_supervised_finetuning.yaml"


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run(config_path: str | Path = DEFAULT_CONFIG) -> None:
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    model_cfg = cfg["model"]
    train_cfg = cfg["training"]
    mlflow_cfg = cfg["mlflow"]

    # GPU check
    try:
        import torch
        if not torch.cuda.is_available():
            print("WARNING: No CUDA GPU detected. C2 SFT requires a GPU node.")
            print("Run on RunPod / AWS EC2 g5.xlarge with requirements-gpu.txt installed.")
            return
    except ImportError:
        print("PyTorch not installed. Install requirements-gpu.txt on a GPU node.")
        return

    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db"))
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    run_name = f"{mlflow_cfg['run_name_prefix']}_qlora_r{cfg['lora']['r']}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "condition_id": exp_cfg["condition_id"],
            "base_model": model_cfg["base_model_id"],
            "lora_r": cfg["lora"]["r"],
            "lora_alpha": cfg["lora"]["lora_alpha"],
            "epochs": train_cfg["num_train_epochs"],
            "lr": train_cfg["learning_rate"],
            "batch_size": train_cfg["per_device_train_batch_size"],
            "grad_accum": train_cfg["gradient_accumulation_steps"],
        })

        # 4-bit quantization config
        bnb_cfg = cfg["quantization"]
        # Explicit seed (config: training.seed, default 42) — previously never set or logged.
        from transformers import set_seed as _set_seed
        _seed = train_cfg.get("seed", 42)
        _set_seed(_seed)
        import torch as _torch
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=bnb_cfg["load_in_4bit"],
            bnb_4bit_compute_dtype=getattr(_torch, bnb_cfg["bnb_4bit_compute_dtype"]),
            bnb_4bit_quant_type=bnb_cfg["bnb_4bit_quant_type"],
            bnb_4bit_use_double_quant=bnb_cfg["bnb_4bit_use_double_quant"],
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_cfg["base_model_id"],
            quantization_config=bnb_config,
            device_map="auto",
        )
        tokenizer = AutoTokenizer.from_pretrained(model_cfg["base_model_id"])
        tokenizer.pad_token = tokenizer.eos_token

        model = prepare_model_for_kbit_training(model)
        lora_cfg = cfg["lora"]
        lora_config = LoraConfig(
            r=lora_cfg["r"],
            lora_alpha=lora_cfg["lora_alpha"],
            lora_dropout=lora_cfg["lora_dropout"],
            target_modules=lora_cfg["target_modules"],
            bias=lora_cfg["bias"],
            task_type=lora_cfg["task_type"],
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

        dataset = load_dataset("json", data_files={
            "train": train_cfg["dataset"],
            "validation": train_cfg["eval_dataset"],
        })

        # trl 0.13.0 moved SFT-specific args (max_seq_length, packing, ...) onto
        # SFTConfig itself rather than accepting them as SFTTrainer kwargs.
        training_args = SFTConfig(
            output_dir=model_cfg["output_dir"],
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
            logging_steps=train_cfg["logging_steps"],
            eval_steps=train_cfg["eval_steps"],
            save_steps=train_cfg["save_steps"],
            save_total_limit=train_cfg["save_total_limit"],
            max_seq_length=train_cfg["max_seq_length"],
            report_to="none",               # MLflow logging handled manually
        )

        # sft_train.jsonl rows are {"messages": [...]} (chat format), but this
        # trl version's SFTTrainer only reads a flat `text` field by default —
        # it does not auto-detect a `messages` column. Render it explicitly.
        def _format_example(example: dict) -> str:
            return tokenizer.apply_chat_template(example["messages"], tokenize=False)

        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["validation"],
            processing_class=tokenizer,
            formatting_func=_format_example,
        )

        trainer.train()
        trainer.save_model(f"{model_cfg['output_dir']}/final")

        # Log final eval metrics
        eval_results = trainer.evaluate()
        mlflow.log_metrics({k.replace("eval_", ""): v for k, v in eval_results.items()})

        if mlflow_cfg.get("log_model"):
            mlflow.peft.log_model(model, "sft_adapter")

        print(f"C2 SFT complete. Adapter saved to {model_cfg['output_dir']}/final")
        print(f"Publish to HuggingFace: huggingface-cli upload {model_cfg['hub_repo']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    run(args.config)
