"""Supervised Fine-Tuning (SFT) script for Alignment Condition #2.

This script fine-tunes a base model using QLoRA on the Chioma persona dataset.
It's configured to run as part of the MLflow experiment tracking for C2.

This approach runs locally on a machine with a suitable GPU and does not
depend on a third-party fine-tuning API.

Usage:
    python run_sft.py
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
    TrainingArguments,
)
from trl import SFTTrainer

# ── Constants ─────────────────────────────────────────────────────────────────

# A powerful, open-source model suitable for fine-tuning on a single,
# widely available cloud GPU (e.g., NVIDIA T4, V100, A100).
BASE_MODEL_ID = "meta-llama/Llama-3-8B-Instruct"
DATASET_ID = "chioma_persona_sft.jsonl"

# The name for the new model adapter on the Hugging Face Hub.
HF_USERNAME = os.getenv("HF_USERNAME")
HUB_MODEL_ID = f"{HF_USERNAME}/c2-sft-llama3-8b-chioma-persona" if HF_USERNAME else None

NEW_MODEL_NAME = "c2-sft-llama3-8b-chioma-persona"
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
    """Returns the BitsAndBytes config for 4-bit quantization."""
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

def get_training_args(output_dir: str) -> TrainingArguments:
    """Returns the TrainingArguments for the SFT trainer."""
    return TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        num_train_epochs=3,
        logging_steps=10,
        save_total_limit=2,
        report_to="mlflow",
        # Push the model to the Hub, saving disk space on the training machine
        push_to_hub=True,
        hub_model_id=HUB_MODEL_ID,
    )

def main():
    """Main training loop."""
    if not HUB_MODEL_ID:
        print("❌ Error: HF_USERNAME environment variable not set.")
        print("Please set your Hugging Face username to save the model to the Hub.")
        return

    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name="sft_qlora_run"):
        # Log parameters
        mlflow.log_param("base_model", BASE_MODEL_ID)
        mlflow.log_param("dataset", DATASET_ID)
        mlflow.log_param("hub_model_id", HUB_MODEL_ID)
        mlflow.log_param("adapter_type", "QLoRA")
        mlflow.log_param("finetuning_type", "local_sft")

        # Load dataset
        dataset = load_dataset("json", data_files=DATASET_ID, split="train")

        # Load tokenizer and model
        # NOTE: You will need to authenticate with Hugging Face to download Llama 3.
        # Run `huggingface-cli login` in your terminal and provide an access token.
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
        tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_ID,
            quantization_config=get_bnb_config(),
            device_map="auto", # Automatically uses the GPU if available
        )
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(model, get_qlora_config())

        # Set up trainer
        output_dir = f"research/models/checkpoints/{NEW_MODEL_NAME}"
        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset,
            peft_config=get_qlora_config(),
            dataset_text_field="text",
            max_seq_length=1024,
            tokenizer=tokenizer,
            args=get_training_args(output_dir),
        )

        # Train the model
        print("Starting supervised fine-tuning...")
        trainer.train()
        print("Fine-tuning complete.")

        # Log model artifact to MLflow
        # The trainer saves checkpoints to the output_dir. We can log this.
        mlflow.log_artifact(output_dir, artifact_path="model_checkpoints")

        print("\n✅ SFT process finished successfully.")
        print(f"Find your trained model adapter on the Hugging Face Hub: {HUB_MODEL_ID}")

if __name__ == "__main__":
    main()