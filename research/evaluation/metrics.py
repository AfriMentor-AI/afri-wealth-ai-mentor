"""Shared evaluation harness for all 4 alignment conditions (card D1.4).

Computes the AfriMentor evaluation suite against a model response:
  - PersonaAdherenceScore   : does the response sound like Chioma?
  - CulturalFluencyScore    : African context, vernacular, local references
  - AntiDependencyScore     : teaches frameworks, not just answers
  - FinancialAccuracyScore  : factual correctness of financial advice
  - UrgencyScore            : surfaces cost of inaction
  - ROUGE-L                 : surface-level overlap with reference responses
  - BERTScore               : semantic similarity to reference responses

All scorers return a float in [0.0, 1.0].
LLM-based scorers use the same OpenAI-compatible API as the chat service.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import mlflow
from openai import OpenAI

# ── LLM judge client ──────────────────────────────────────────────────────────
_judge_client: OpenAI | None = None


def _get_judge() -> OpenAI:
    global _judge_client
    if _judge_client is None:
        _judge_client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        )
    return _judge_client


_JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "llama-3.1-8b-instant")

# ── Score dataclass ───────────────────────────────────────────────────────────

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
        """Weighted composite — persona + cultural + anti-dependency weighted higher."""
        return (
            self.persona_adherence * 0.25
            + self.cultural_fluency * 0.20
            + self.anti_dependency * 0.20
            + self.financial_accuracy * 0.20
            + self.urgency * 0.15
        )


# ── LLM-as-judge scorers ──────────────────────────────────────────────────────

_RUBRIC_TEMPLATE = """You are an expert evaluator for an African financial mentorship AI.
Score the following AI response on the dimension: {dimension}

Definition: {definition}

User message: {user_message}
AI response: {response}

Score from 0.0 to 1.0 where:
  0.0 = completely fails this dimension
  0.5 = partially meets this dimension
  1.0 = fully and excellently meets this dimension

Reply with ONLY a single float number between 0.0 and 1.0. No explanation."""


def _llm_score(dimension: str, definition: str, user_message: str, response: str) -> float:
    prompt = _RUBRIC_TEMPLATE.format(
        dimension=dimension,
        definition=definition,
        user_message=user_message,
        response=response,
    )
    try:
        result = _get_judge().chat.completions.create(
            model=_JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.0,
        )
        return float(result.choices[0].message.content.strip())
    except (ValueError, Exception):
        return 0.0


def score_persona_adherence(user_message: str, response: str) -> float:
    return _llm_score(
        dimension="Persona Adherence (Chioma)",
        definition=(
            "The response sounds like Chioma: warm but direct, uses African context, "
            "gives specific actionable advice with numbers, acknowledges before advising, "
            "and ends with a single sharp question or next action — not generic encouragement."
        ),
        user_message=user_message,
        response=response,
    )


def score_cultural_fluency(user_message: str, response: str) -> float:
    return _llm_score(
        dimension="Cultural Fluency",
        definition=(
            "The response demonstrates genuine understanding of African financial realities: "
            "informal markets, mobile money, rotating savings groups (ajo/esusu/chama), "
            "family financial obligations, local business terminology, and regional context. "
            "It does not impose Western personal-finance frameworks without adaptation."
        ),
        user_message=user_message,
        response=response,
    )


def score_anti_dependency(user_message: str, response: str) -> float:
    return _llm_score(
        dimension="Anti-Dependency",
        definition=(
            "The response builds the user's financial thinking rather than creating "
            "dependence. It explains reasoning, teaches a framework or principle, "
            "and asks what the user thinks before or alongside giving advice. "
            "It does not just hand over an answer without transferring understanding."
        ),
        user_message=user_message,
        response=response,
    )


def score_financial_accuracy(user_message: str, response: str) -> float:
    return _llm_score(
        dimension="Financial Accuracy",
        definition=(
            "The financial advice is factually correct, the numbers are realistic for "
            "African markets, and no harmful or misleading financial guidance is given. "
            "Calculations (margins, savings rates, costs) are accurate."
        ),
        user_message=user_message,
        response=response,
    )


def score_urgency(user_message: str, response: str) -> float:
    return _llm_score(
        dimension="Urgency",
        definition=(
            "The response surfaces the cost of financial inaction in concrete terms — "
            "specific numbers, timelines, or opportunity costs. It makes the future "
            "feel close and real, not abstract."
        ),
        user_message=user_message,
        response=response,
    )


# ── Reference-based scorers ───────────────────────────────────────────────────

def score_rouge_l(response: str, reference: str) -> float:
    """ROUGE-L F1 score against a reference response."""
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        return scorer.score(reference, response)["rougeL"].fmeasure
    except ImportError:
        return 0.0


def score_bert(response: str, reference: str) -> float:
    """BERTScore F1 against a reference response."""
    try:
        from bert_score import score as bert_score
        _, _, f1 = bert_score([response], [reference], lang="en", verbose=False)
        return float(f1[0])
    except ImportError:
        return 0.0


# ── Full evaluation pipeline ──────────────────────────────────────────────────

def evaluate_response(
    user_message: str,
    response: str,
    reference: str | None = None,
) -> EvalResult:
    """Run the full evaluation suite on a single (user_message, response) pair."""
    result = EvalResult(
        persona_adherence=score_persona_adherence(user_message, response),
        cultural_fluency=score_cultural_fluency(user_message, response),
        anti_dependency=score_anti_dependency(user_message, response),
        financial_accuracy=score_financial_accuracy(user_message, response),
        urgency=score_urgency(user_message, response),
    )
    if reference:
        result.rouge_l = score_rouge_l(response, reference)
        result.bert_score_f1 = score_bert(response, reference)
    return result


def log_eval_to_mlflow(result: EvalResult, step: int | None = None) -> None:
    """Log all eval metrics to the active MLflow run."""
    mlflow.log_metrics(result.to_dict(), step=step)
    mlflow.log_metric("composite_score", result.composite_score, step=step)
