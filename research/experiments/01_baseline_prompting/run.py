"""Condition C1 — Baseline Prompting experiment runner (card D1.4).

Evaluates the base model (no fine-tuning) across zero-shot and few-shot
prompting modes for all 6 Chioma personas. Establishes the performance
floor all other conditions are measured against.

Usage:
    python research/experiments/01_baseline_prompting/run.py
    python research/experiments/01_baseline_prompting/run.py --config research/configs/c1_baseline_prompting.yaml
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import mlflow
import yaml
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parents[2]))
from evaluation.metrics import evaluate_response, log_eval_to_mlflow

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "c1_baseline_prompting.yaml"


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Persona system prompts (stub — replaced by persona-prompt-service in Sprint 2) ──

def _get_system_prompt(persona_slug: str) -> str:
    """Load rendered persona prompt from the persona-prompt-service templates."""
    try:
        svc_path = Path(__file__).parents[3] / "services" / "persona-prompt-service"
        sys.path.insert(0, str(svc_path))
        from app.renderer import render_persona_prompt
        template_map = {
            "chioma-base": "chioma_base.j2",
            "market-queen": "sub_market_queen.j2",
            "tech-founder": "sub_tech_founder.j2",
            "trader": "sub_trader.j2",
            "rural-hustler": "sub_rural_hustler.j2",
            "creative": "sub_creative.j2",
        }
        return render_persona_prompt(template_map.get(persona_slug, "chioma_base.j2"))
    except Exception:
        return "You are Chioma, an African financial mentor. Be direct, warm, and practical."


# ── Inference ─────────────────────────────────────────────────────────────────

def run_inference(client: OpenAI, model_id: str, system_prompt: str,
                  user_message: str, few_shot_examples: list[dict],
                  max_tokens: int, temperature: float) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    for ex in few_shot_examples:
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": ex["assistant"]})
    messages.append({"role": "user", "content": user_message})
    response = client.chat.completions.create(
        model=model_id,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


# ── Eval dataset loader ───────────────────────────────────────────────────────

def load_eval_samples(split_dir: Path, sample_size: int) -> list[dict]:
    """Load evaluation samples. Returns synthetic samples if split not yet generated."""
    eval_file = split_dir / "sft_test.jsonl"
    if eval_file.exists():
        samples = []
        with open(eval_file) as f:
            for line in f:
                samples.append(json.loads(line))
                if len(samples) >= sample_size:
                    break
        return samples

    # Synthetic seed samples for Sprint 1 scaffold testing
    return [
        {"user": "How do I start saving as a market trader in Lagos?", "reference": None, "persona": "market-queen"},
        {"user": "I want to launch a fintech app in Nairobi. Where do I start?", "reference": None, "persona": "tech-founder"},
        {"user": "How do I manage forex risk when importing from China?", "reference": None, "persona": "trader"},
        {"user": "My harvest income is seasonal. How do I budget for the lean months?", "reference": None, "persona": "rural-hustler"},
        {"user": "I'm a photographer. How do I price my work properly?", "reference": None, "persona": "creative"},
    ][:sample_size]


# ── Main runner ───────────────────────────────────────────────────────────────

def run(config_path: str | Path = DEFAULT_CONFIG) -> None:
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    model_cfg = cfg["model"]
    eval_cfg = cfg["evaluation"]
    mlflow_cfg = cfg["mlflow"]

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db"))
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=model_cfg["base_url"],
    )

    samples = load_eval_samples(
        Path("research/datasets/splits"),
        eval_cfg["sample_size"],
    )

    for mode in cfg["prompting"]["modes"]:
        few_shot_n = int(mode.split("_")[-1]) if "few_shot" in mode else 0
        run_name = f"{mlflow_cfg['run_name_prefix']}_{mode}"

        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({
                "condition_id": exp_cfg["condition_id"],
                "model_id": model_cfg["model_id"],
                "prompting_mode": mode,
                "few_shot_n": few_shot_n,
                "temperature": model_cfg["temperature"],
                "max_tokens": model_cfg["max_tokens"],
            })

            all_scores: list[dict] = []
            for i, sample in enumerate(samples):
                persona = sample.get("persona", "chioma-base")
                system_prompt = _get_system_prompt(persona)
                response = run_inference(
                    client=client,
                    model_id=model_cfg["model_id"],
                    system_prompt=system_prompt,
                    user_message=sample["user"],
                    few_shot_examples=[],   # TODO Sprint 3: load from few-shot bank
                    max_tokens=model_cfg["max_tokens"],
                    temperature=model_cfg["temperature"],
                )
                result = evaluate_response(
                    user_message=sample["user"],
                    response=response,
                    reference=sample.get("reference"),
                )
                log_eval_to_mlflow(result, step=i)
                all_scores.append(result.to_dict())
                print(f"  [{mode}] sample {i+1}/{len(samples)} composite={result.composite_score:.3f}")

            # Log aggregate metrics
            if all_scores:
                for key in all_scores[0]:
                    avg = sum(s[key] for s in all_scores) / len(all_scores)
                    mlflow.log_metric(f"avg_{key}", avg)

            print(f"Run '{run_name}' complete. MLflow UI: http://localhost:5000")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    run(args.config)
