"""Evaluation script for AfriMentor alignment conditions.

This script loads a locally fine-tuned model adapter from the Hugging Face Hub,
merges it with the base model, generates a response to a sample user query,
and runs the full evaluation suite from `metrics.py`.

Usage:
    python research/evaluation/run_evaluation.py
"""
from __future__ import annotations
import os

import mlflow
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from research.evaluation.metrics import EvalResult, evaluate_response, log_eval_to_mlflow

# ── Constants ─────────────────────────────────────────────────────────────────

# The base model used during fine-tuning.
BASE_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# Your Hugging Face username, read from an environment variable.
HF_USERNAME = os.getenv("HF_USERNAME")
# The Hugging Face Hub ID of your fine-tuned adapter.
ADAPTER_MODEL_ID = f"{HF_USERNAME}/c2-sft-Qwen2.5-7B-chioma-persona" if HF_USERNAME else None

MLFLOW_EXPERIMENT_NAME = "C2_supervised_persona_finetuning"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ── Sample Query for Evaluation ───────────────────────────────────────────────

USER_MESSAGE = (
    "I'm a small-scale fish farmer in Kisumu. I sell my tilapia at the local "
    "market, but after transport costs and feeding the fish, my profit is very "
    "low. How can I increase my income?"
)

REFERENCE_RESPONSE = (
    "I understand completely. The margins in aquaculture can be very thin. "
    "Let's look at the numbers. What is your current monthly cost for fish feed, "
    "and how much do you spend on transport to the market? Vusi Thembekwayo often "
    "talks about value chains. Instead of just selling raw fish, have you considered "
    "adding a small smoker and selling smoked fish? This could increase your "
    "shelf life and fetch a higher price. What do you think is the biggest "
    "obstacle to trying that?"
)

def get_bnb_config() -> BitsAndBytesConfig:
    """Returns the BitsAndBytes config for 4-bit quantization."""
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

def main():
    """Main evaluation pipeline."""
    if not ADAPTER_MODEL_ID:
        print("❌ Error: HF_USERNAME environment variable not set.")
        print("Please set your Hugging Face username to load the model from the Hub.")
        return

    print("Starting evaluation for locally fine-tuned model (Condition C2)...")

    # Load the base model and tokenizer
    print(f"Loading base model: {BASE_MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=get_bnb_config(),
        device_map="auto",
    )

    # Load the PEFT adapter from the Hub and merge it into the base model
    print(f"Loading adapter from Hub: {ADAPTER_MODEL_ID}")
    model = PeftModel.from_pretrained(base_model, ADAPTER_MODEL_ID)
    model = model.eval()

    # Prepare the prompt using the same format as the training data
    prompt = (
        f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
        f"{USER_MESSAGE}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    model_inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)

    # Generate response
    print(f"\nGenerating response from model: {ADAPTER_MODEL_ID}")
    try:
        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )
        # Decode the response, skipping the prompt part
        response_text = tokenizer.batch_decode(generated_ids[:, model_inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
    except Exception as e:
        print(f"Error during model generation: {e}")
        return

    print(f"Generated Response:\n---\n{response_text}\n---")

    # Run evaluation
    print("\nRunning evaluation suite...")
    eval_result: EvalResult = evaluate_response(USER_MESSAGE, response_text, REFERENCE_RESPONSE)

    # Log to MLflow
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    with mlflow.start_run(run_name="sft_local_evaluation_run"):
        mlflow.log_param("model_id", ADAPTER_MODEL_ID)
        log_eval_to_mlflow(eval_result)
        print("\n✅ Evaluation complete. Results logged to MLflow.")

if __name__ == "__main__":
    main()