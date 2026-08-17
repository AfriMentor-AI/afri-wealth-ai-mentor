"""Supervised Fine-Tuning (SFT) script for Alignment Condition #2.

This script fine-tunes a base model using QLoRA on the Chioma persona dataset.
It's configured to run as part of the MLflow experiment tracking for C2.
"""
from __future__ import annotations

import os

import mlflow
import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer

# ── Constants ─────────────────────────────────────────────────────────────────

# Official Hugging Face repo ID for Meta Llama 3
BASE_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
DATASET_ID = "chioma_persona_sft.jsonl"

HF_USERNAME = os.getenv("HF_USERNAME")
HUB_MODEL_ID = f"{HF_USERNAME}/c2-sft-Qwen2.5-7B-chioma-persona" if HF_USERNAME else None

NEW_MODEL_NAME = "c2-sft-Qwen2.5-7B-chioma-persona"
MLFLOW_EXPERIMENT_NAME = "C2_supervised_persona_finetuning"

# ── Configuration ─────────────────────────────────────────────────────────────

def get_qlora_config() -> LoraConfig:
    """Returns the QLoRA configuration for PEFT."""
    return LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )

def get_bnb_config() -> BitsAndBytesConfig:
    """Returns the BitsAndBytes config for 4-bit quantization.
    Uses float16 for standard compatibility with NVIDIA T4 GPUs.
    """
    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
    )

def get_training_args(output_dir: str) -> SFTConfig:
    """Returns the modern SFTConfig for TRL SFTTrainer."""
    return SFTConfig(
        output_dir=output_dir,
        dataset_text_field="text",
        max_seq_length=1024,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        num_train_epochs=3,
        logging_steps=10,
        save_total_limit=2,
        report_to="mlflow",
        push_to_hub=True,
        hub_model_id=HUB_MODEL_ID,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
    )

def main():
    """Main training loop."""
    if not HUB_MODEL_ID:
        print("❌ Error: HF_USERNAME environment variable not set.")
        print("Please set your Hugging Face username to save the model to the Hub.")
        return

    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name="sft_qlora_run"):
        mlflow.log_param("base_model", BASE_MODEL_ID)
        mlflow.log_param("dataset", DATASET_ID)
        mlflow.log_param("hub_model_id", HUB_MODEL_ID)
        mlflow.log_param("adapter_type", "QLoRA")
        mlflow.log_param("finetuning_type", "local_sft")

        # Load dataset
        dataset = load_dataset("json", data_files=DATASET_ID, split="train")

        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Load base quantized model
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_ID,
            quantization_config=get_bnb_config(),
            device_map="auto",
        )
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(model, get_qlora_config())

        output_dir = f"research/models/checkpoints/{NEW_MODEL_NAME}"
        training_args = get_training_args(output_dir)

        # Initialize modern SFTTrainer
        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset,
            processing_class=tokenizer,
            args=training_args,
        )

        print("Starting supervised fine-tuning...")
        trainer.train()
        print("Fine-tuning complete.")

        # Save and push final adapter
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        mlflow.log_artifact(output_dir, artifact_path="model_checkpoints")

        print("\n✅ SFT process finished successfully.")
        print(f"Find your trained model adapter on the Hugging Face Hub: {HUB_MODEL_ID}")

if __name__ == "__main__":
    main()