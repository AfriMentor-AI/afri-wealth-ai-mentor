"""Condition C1 — Baseline Prompting experiment runner (card D2.4).

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
import logging
import os
import sys
from pathlib import Path

import importlib.util
import mlflow
import yaml
from openai import OpenAI

# Ensure research/ is on the path regardless of cwd
_RESEARCH_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_RESEARCH_ROOT))

from evaluation.metrics import EvalResult, evaluate_response, log_eval_to_mlflow  # noqa: E402

# Load few_shot_bank from the digit-prefixed directory via importlib
_fsb_spec = importlib.util.spec_from_file_location(
    "few_shot_bank",
    Path(__file__).parent / "few_shot_bank.py",
)
_fsb_mod = importlib.util.module_from_spec(_fsb_spec)  # type: ignore[arg-type]
_fsb_spec.loader.exec_module(_fsb_mod)  # type: ignore[union-attr]
load_few_shot_examples = _fsb_mod.load_few_shot_examples

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEFAULT_CONFIG = _RESEARCH_ROOT / "configs" / "c1_baseline_prompting.yaml"
SPLITS_DIR = _RESEARCH_ROOT / "datasets" / "splits"


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Persona system prompts ────────────────────────────────────────────────────

_TEMPLATE_MAP = {
    "chioma-base": "chioma_base.j2",
    "market-queen": "sub_market_queen.j2",
    "tech-founder": "sub_tech_founder.j2",
    "trader": "sub_trader.j2",
    "rural-hustler": "sub_rural_hustler.j2",
    "creative": "sub_creative.j2",
}

_FALLBACK_PROMPT = (
    "You are Chioma, an African financial mentor. Be direct, warm, and practical."
)


def _get_system_prompt(persona_slug: str) -> str:
    """Load rendered persona prompt from the D1.3 Jinja2 templates."""
    try:
        svc_path = _RESEARCH_ROOT.parent / "services" / "persona-prompt-service"
        sys.path.insert(0, str(svc_path))
        from app.renderer import render_persona_prompt
        return render_persona_prompt(_TEMPLATE_MAP.get(persona_slug, "chioma_base.j2"))
    except Exception:
        logger.warning("persona-prompt-service renderer unavailable — using fallback prompt")
        return _FALLBACK_PROMPT


# ── Inference ─────────────────────────────────────────────────────────────────

def run_inference(
    client: OpenAI,
    model_id: str,
    system_prompt: str,
    user_message: str,
    few_shot_examples: list[dict],
    max_tokens: int,
    temperature: float,
) -> str:
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
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

def load_eval_samples(sample_size: int) -> list[dict]:
    """Load test samples from sft_test.jsonl, normalised to {user, reference, persona}."""
    eval_file = SPLITS_DIR / "sft_test.jsonl"
    samples: list[dict] = []

    if eval_file.exists():
        with open(eval_file) as f:
            for line in f:
                record = json.loads(line)
                messages = record.get("messages", [])
                user_msg = next((m["content"] for m in messages if m["role"] == "user"), None)
                asst_msg = next((m["content"] for m in messages if m["role"] == "assistant"), None)
                if not user_msg:
                    continue
                samples.append({
                    "user": user_msg,
                    "reference": asst_msg,
                    "persona": record.get("persona_slug", "chioma-base"),
                    "sector": record.get("sector", "general"),
                    "country": record.get("country", "NG"),
                })
                if len(samples) >= sample_size:
                    break

    if not samples:
        # Synthetic fallback — one sample per persona so the runner always executes
        samples = [
            {"user": "How do I start saving as a market trader in Lagos?", "reference": None, "persona": "market-queen", "sector": "trader", "country": "NG"},
            {"user": "I want to launch a fintech app in Nairobi. Where do I start?", "reference": None, "persona": "tech-founder", "sector": "tech", "country": "KE"},
            {"user": "How do I manage forex risk when importing from China?", "reference": None, "persona": "trader", "sector": "trader", "country": "GH"},
            {"user": "My harvest income is seasonal. How do I budget for the lean months?", "reference": None, "persona": "rural-hustler", "sector": "agriculture", "country": "NG"},
            {"user": "I'm a photographer. How do I price my work properly?", "reference": None, "persona": "creative", "sector": "creative", "country": "NG"},
            {"user": "I keep spending all my salary before the month ends. What do I do?", "reference": None, "persona": "chioma-base", "sector": "general", "country": "NG"},
        ][:sample_size]

    return samples


# ── Aggregate helpers ─────────────────────────────────────────────────────────

def _avg_scores(scores: list[dict]) -> dict:
    if not scores:
        return {}
    keys = [k for k in scores[0] if isinstance(scores[0][k], (int, float))]
    return {k: sum(s[k] for s in scores) / len(scores) for k in keys}


# ── Main runner ───────────────────────────────────────────────────────────────

def run(config_path: str | Path = DEFAULT_CONFIG) -> dict:
    """Run C1 baseline experiment. Returns per-mode aggregate metrics dict."""
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    model_cfg = cfg["model"]
    eval_cfg = cfg["evaluation"]
    mlflow_cfg = cfg["mlflow"]

    mlflow.set_tracking_uri(
        os.getenv("MLFLOW_TRACKING_URI", "sqlite:///research/tracking/mlflow.db")
    )
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY", "no-key"),
        base_url=model_cfg["base_url"],
    )

    samples = load_eval_samples(eval_cfg["sample_size"])
    logger.info("Loaded %d eval samples", len(samples))

    run_results: dict[str, dict] = {}

    for mode in cfg["prompting"]["modes"]:
        few_shot_n = int(mode.split("_")[-1]) if "few_shot" in mode else 0
        run_name = f"{mlflow_cfg['run_name_prefix']}_{mode}"
        logger.info("Starting run: %s", run_name)

        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({
                "condition_id": exp_cfg["condition_id"],
                "model_id": model_cfg["model_id"],
                "prompting_mode": mode,
                "few_shot_n": few_shot_n,
                "temperature": model_cfg["temperature"],
                "max_tokens": model_cfg["max_tokens"],
                "eval_sample_size": len(samples),
            })

            all_scores: list[dict] = []

            for i, sample in enumerate(samples):
                persona = sample["persona"]
                system_prompt = _get_system_prompt(persona)
                few_shot_examples = (
                    load_few_shot_examples(persona, few_shot_n)
                    if few_shot_n > 0
                    else []
                )

                response = run_inference(
                    client=client,
                    model_id=model_cfg["model_id"],
                    system_prompt=system_prompt,
                    user_message=sample["user"],
                    few_shot_examples=few_shot_examples,
                    max_tokens=model_cfg["max_tokens"],
                    temperature=model_cfg["temperature"],
                )

                result = evaluate_response(
                    user_message=sample["user"],
                    response=response,
                    reference=sample.get("reference"),
                )
                log_eval_to_mlflow(result, step=i)

                score_row = {**result.to_dict(), "persona": persona, "composite_score": result.composite_score}
                all_scores.append(score_row)
                logger.info(
                    "  [%s] sample %d/%d persona=%-14s composite=%.3f",
                    mode, i + 1, len(samples), persona, result.composite_score,
                )

            # Log aggregate metrics for this mode
            agg = _avg_scores(all_scores)
            for key, val in agg.items():
                if key != "persona":
                    mlflow.log_metric(f"avg_{key}", val)

            # Per-persona breakdown
            personas_seen = {s["persona"] for s in all_scores}
            for p in personas_seen:
                p_scores = [s for s in all_scores if s["persona"] == p]
                p_agg = _avg_scores(p_scores)
                if "composite_score" in p_agg:
                    mlflow.log_metric(f"avg_composite_{p}", p_agg["composite_score"])

            run_results[mode] = agg
            logger.info(
                "Run '%s' complete — avg composite=%.3f",
                run_name,
                agg.get("composite_score", 0.0),
            )

    return run_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    results = run(args.config)
    print("\n=== C1 Baseline Results ===")
    for mode, agg in results.items():
        print(f"  {mode}: composite={agg.get('composite_score', 0.0):.3f}")
    print("\nMLflow UI: mlflow ui --backend-store-uri sqlite:///research/tracking/mlflow.db")
