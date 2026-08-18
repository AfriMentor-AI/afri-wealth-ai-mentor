from __future__ import annotations
import gc
import json
import os
import sys
import numpy as np
import pandas as pd
import torch
import mlflow

from kaggle_secrets import UserSecretsClient
try:
    user_secrets = UserSecretsClient()
    # Pull LLM Judge key from secrets if available
    llm_key = user_secrets.get_secret("LLM_API_KEY") or user_secrets.get_secret("GROQ_API_KEY")
    if llm_key:
        os.environ["LLM_API_KEY"] = llm_key
except Exception as e:
    print(f"Notice regarding API secrets: {e}", flush=True)

from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from metrics import evaluate_response, EvalResult

def load_eval_data(file_path: str):
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def main():
    gc.collect()
    torch.cuda.empty_cache()

    adapter_path = "/kaggle/working/checkpoints"
    data_path = "/kaggle/input/datasets/danielkusiboateng/chioma-persona-sft/sft_val.jsonl"
    
    # Check for test split if available, otherwise val
    test_path = "/kaggle/input/datasets/danielkusiboateng/chioma-persona-sft/sft_test.jsonl"
    if os.path.exists(test_path):
        data_path = test_path

    print(f"Loading evaluation dataset: {data_path}", flush=True)
    samples = load_eval_data(data_path)
    print(f"Total evaluation samples: {len(samples)}", flush=True)

    print("Loading fine-tuned model for inference...", flush=True)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_path,
        max_seq_length=2048,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)

    tokenizer = get_chat_template(
        tokenizer,
        chat_template="qwen-2.5",
    )

    eval_results = []
    
    print("\nStarting generation and scoring...", flush=True)
    for i, sample in enumerate(samples):
        messages = sample.get("messages", sample.get("conversations", []))
        if not messages:
            continue

        # Extract user input and ground truth reference
        user_msg = ""
        ref_msg = ""
        prompt_messages = []
        
        for msg in messages:
            if msg["role"] == "user":
                user_msg = msg["content"]
                prompt_messages.append(msg)
            elif msg["role"] == "assistant":
                ref_msg = msg["content"]

        # Format prompt with chat template for inference
        input_ids = tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to("cuda")

        with torch.no_grad():
            output = model.generate(
                input_ids=input_ids,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9,
                use_cache=True,
            )

        # Slice generated response
        generated_tokens = output[0][input_ids.shape[1]:]
        generated_text = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        print(f"\n--- Sample {i+1} ---")
        print(f"User: {user_msg}")
        print(f"Model: {generated_text}")
        print(f"Reference: {ref_msg}\n")

        # Evaluate against the rubric & reference
        score: EvalResult = evaluate_response(
            user_message=user_msg,
            response=generated_text,
            reference=ref_msg if ref_msg else None,
        )
        
        eval_results.append(score.to_dict())

    # Aggregate metric averages
    df = pd.DataFrame(eval_results)
    avg_scores = df.mean(numeric_only=True).to_dict()

    # Calculate composite score from averages
    composite = (
        avg_scores.get("persona_adherence", 0.0) * 0.25
        + avg_scores.get("cultural_fluency", 0.0) * 0.20
        + avg_scores.get("anti_dependency", 0.0) * 0.20
        + avg_scores.get("financial_accuracy", 0.0) * 0.20
        + avg_scores.get("urgency", 0.0) * 0.15
    )
    avg_scores["composite_score"] = composite

    # Log to MLflow
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "file:/kaggle/working/mlruns"))
    mlflow.set_experiment("C2_supervised_persona_finetuning")
    with mlflow.start_run(run_name="evaluation_summary"):
        mlflow.log_metrics(avg_scores)

    print("\n================ EVALUATION SUMMARY ================")
    for metric, value in avg_scores.items():
        print(f"{metric:<25}: {value:.4f}")
    print("====================================================\n")

if __name__ == "__main__":
    main()