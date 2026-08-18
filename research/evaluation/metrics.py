from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
import mlflow
from openai import OpenAI

_judge_client: OpenAI | None = None

def _get_judge() -> OpenAI:
    global _judge_client
    if _judge_client is None:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
        _judge_client = OpenAI(api_key=api_key, base_url=base_url)
    return _judge_client

# Configured for openai/gpt-oss-120b
_JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "openai/gpt-oss-120b")

@dataclass
class EvalResult:
    persona_adherence: float = 0.0
    cultural_fluency: float = 0.0
    anti_dependency: float = 0.0
    financial_accuracy: float = 0.0
    urgency: float = 0.0
    rouge_l: float = 0.0
    bert_score_f1: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "persona_adherence": self.persona_adherence,
            "cultural_fluency": self.cultural_fluency,
            "anti_dependency": self.anti_dependency,
            "financial_accuracy": self.financial_accuracy,
            "urgency": self.urgency,
            "rouge_l": self.rouge_l,
            "bert_score_f1": self.bert_score_f1,
            **self.metadata,
        }

    @property
    def composite_score(self) -> float:
        return (
            self.persona_adherence * 0.25
            + self.cultural_fluency * 0.20
            + self.anti_dependency * 0.20
            + self.financial_accuracy * 0.20
            + self.urgency * 0.15
        )

_COMBINED_EVAL_PROMPT = """You are an expert evaluator assessing an AI financial mentor response (Persona: Chioma) for African founders and individuals.
Evaluate the AI response across these 5 dimensions on a scale from 0.0 (completely fails) to 1.0 (fully meets):

1. persona_adherence: Warm but direct, gives specific actionable advice with numbers, acknowledges before advising, ends with a single sharp question/next action rather than generic advice.
2. cultural_fluency: Genuine understanding of African financial realities (informal markets, mobile money, SACCOs/chamas/esusu, local context).
3. anti_dependency: Teaches underlying frameworks and principles rather than merely handing over generic lists.
4. financial_accuracy: Factually realistic and sensible numbers/guidance for African markets.
5. urgency: Surfaces the concrete cost of inaction or realistic timelines.

User query: {user_message}
AI output: {response}

Output format: Return ONLY a JSON object with float scores (between 0.0 and 1.0) for:
"persona_adherence", "cultural_fluency", "anti_dependency", "financial_accuracy", "urgency"."""

def score_all_dimensions(user_message: str, response: str) -> dict[str, float]:
    prompt = _COMBINED_EVAL_PROMPT.format(
        user_message=user_message,
        response=response,
    )
    
    defaults = {
        "persona_adherence": 0.0,
        "cultural_fluency": 0.0,
        "anti_dependency": 0.0,
        "financial_accuracy": 0.0,
        "urgency": 0.0,
    }

    client = _get_judge()
    if not client.api_key:
        print("[ERROR] LLM API key missing for judge client.", flush=True)
        return defaults

    for attempt in range(3):
        try:
            res = client.chat.completions.create(
                model=_JUDGE_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512,
                temperature=0.0,
            )

            msg = res.choices[0].message
            raw_text = (msg.content or getattr(msg, "reasoning_content", "") or "").strip()

            # Robust JSON extraction from raw content
            json_match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return {
                    k: min(max(float(parsed.get(k, 0.0)), 0.0), 1.0)
                    for k in defaults.keys()
                }

            print(f"[Judge Warning] Could not find JSON block in output: {repr(raw_text)}", flush=True)
            break
        except Exception as e:
            time.sleep(1.5 * (attempt + 1))
            if attempt == 2:
                print(f"[Judge API Error with {_JUDGE_MODEL}]: {e}", flush=True)

    return defaults

def score_rouge_l(response: str, reference: str) -> float:
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        return scorer.score(reference, response)["rougeL"].fmeasure
    except ImportError:
        return 0.0

def score_bert(response: str, reference: str) -> float:
    try:
        from bert_score import score as bert_score
        _, _, f1 = bert_score([response], [reference], lang="en", verbose=False)
        return float(f1[0])
    except ImportError:
        return 0.0

def evaluate_response(
    user_message: str,
    response: str,
    reference: str | None = None,
) -> EvalResult:
    scores = score_all_dimensions(user_message, response)

    result = EvalResult(
        persona_adherence=scores["persona_adherence"],
        cultural_fluency=scores["cultural_fluency"],
        anti_dependency=scores["anti_dependency"],
        financial_accuracy=scores["financial_accuracy"],
        urgency=scores["urgency"],
    )

    if reference:
        result.rouge_l = score_rouge_l(response, reference)
        result.bert_score_f1 = score_bert(response, reference)
        
    return result

def log_eval_to_mlflow(result: EvalResult, step: int | None = None) -> None:
    mlflow.log_metrics(result.to_dict(), step=step)
    mlflow.log_metric("composite_score", result.composite_score, step=step)