"""Shared checkpoint-evaluation harness for the fine-tuning conditions (card C3.1).

Conditions C2/C3/C4 each *produce a model*. To compare them against C1 (and each
other), the trained checkpoint must be scored on the **same** metric suite that
C1 uses — the 5-dimension LLM-as-judge rubric in :mod:`evaluation.metrics`,
plus ROUGE-L / BERTScore when reference responses exist.

This module supplies that post-training step:

  * :func:`load_eval_samples` — the shared held-out set (``sft_test.jsonl``),
    normalised to ``{user, reference, persona, ...}`` with a synthetic fallback.
  * :func:`evaluate_checkpoint` — generate a response per sample, score it with
    the shared suite, log per-sample + aggregate metrics to the active MLflow run
    using the **same metric keys as C1**, and return the aggregate.
  * :class:`HFCheckpointGenerator` — the real generator (base model + PEFT
    adapter). GPU-node only; torch/transformers/peft are imported lazily so this
    module imports fine on a CPU / bare environment.

Generation is decoupled behind the ``GenerateFn`` callable seam, so the scoring
pipeline is fully testable offline without loading a 7B model.
"""
from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# research/ root (this file is research/evaluation/checkpoint_eval.py)
_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
SPLITS_DIR = _RESEARCH_ROOT / "datasets" / "splits"

#: A generator maps (system_prompt, user_message) -> assistant response text.
GenerateFn = Callable[[str, str], str]


# ── Persona system prompts (shared with C1's approach) ─────────────────────────

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


def render_system_prompt(persona_slug: str) -> str:
    """Render a persona system prompt from the D1.3 templates, else a fallback.

    The fine-tuned model still receives the persona prompt at inference, exactly
    as production does — fine-tuning reinforces the persona, it does not replace
    the prompt.
    """
    try:
        svc_path = _RESEARCH_ROOT.parent / "services" / "persona-prompt-service"
        if str(svc_path) not in sys.path:
            sys.path.insert(0, str(svc_path))
        from app.renderer import render_persona_prompt

        return render_persona_prompt(_TEMPLATE_MAP.get(persona_slug, "chioma_base.j2"))
    except Exception:
        logger.warning("persona-prompt-service renderer unavailable — using fallback prompt")
        return _FALLBACK_PROMPT


# ── Eval dataset ───────────────────────────────────────────────────────────────

# One sample per persona so the harness always has something to score, even
# before the DVC data pipeline has produced real splits.
_SYNTHETIC_SAMPLES: list[dict] = [
    {"user": "How do I start saving as a market trader in Lagos?",
     "reference": None, "persona": "market-queen", "sector": "trader", "country": "NG"},
    {"user": "I want to launch a fintech app in Nairobi. Where do I start?",
     "reference": None, "persona": "tech-founder", "sector": "tech", "country": "KE"},
    {"user": "How do I manage forex risk when importing from China?",
     "reference": None, "persona": "trader", "sector": "trader", "country": "GH"},
    {"user": "My harvest income is seasonal. How do I budget for the lean months?",
     "reference": None, "persona": "rural-hustler", "sector": "agriculture", "country": "NG"},
    {"user": "I'm a photographer. How do I price my work properly?",
     "reference": None, "persona": "creative", "sector": "creative", "country": "NG"},
    {"user": "I keep spending all my salary before the month ends. What do I do?",
     "reference": None, "persona": "chioma-base", "sector": "general", "country": "NG"},
]


def load_eval_samples(
    sample_size: int,
    splits_dir: Path | str = SPLITS_DIR,
    eval_file: str = "sft_test.jsonl",
) -> list[dict]:
    """Load up to ``sample_size`` held-out samples, normalised for scoring.

    Reads the same ``sft_test.jsonl`` split C1 evaluates on so the two conditions
    are measured on identical inputs. Falls back to one synthetic sample per
    persona when the split has not been generated yet, so the harness always runs.
    """
    splits_dir = Path(splits_dir)
    if not splits_dir.is_absolute():
        splits_dir = _RESEARCH_ROOT.parent / splits_dir  # config paths are repo-root relative
    eval_path = splits_dir / eval_file
    samples: list[dict] = []

    if eval_path.exists():
        with open(eval_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
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
        samples = _SYNTHETIC_SAMPLES[:sample_size]

    return samples


# ── Aggregation ────────────────────────────────────────────────────────────────

def avg_scores(rows: list[dict]) -> dict:
    """Mean of every numeric field across ``rows`` (non-numeric fields ignored).

    Rows with ``judge_failed=True`` (the LLM judge errored, timed out, or hit
    a quota wall — see :func:`evaluation.metrics.score_all_dimensions`) are
    excluded rather than averaged in as genuine zeros: a diluted mean here
    looks identical to a real quality drop unless failures are dropped
    explicitly. When any are dropped, ``n_judge_failed``/``n_samples_scored``
    record it in the aggregate rather than hiding it.
    """
    valid_rows = [r for r in rows if not r.get("judge_failed")]
    if not valid_rows:
        return {}
    numeric_keys = [
        k for k, v in valid_rows[0].items()
        if isinstance(v, (int, float)) and k != "judge_failed"
    ]
    agg = {k: sum(r[k] for r in valid_rows) / len(valid_rows) for k in numeric_keys}
    n_failed = len(rows) - len(valid_rows)
    if n_failed:
        agg["n_judge_failed"] = n_failed
        agg["n_samples_scored"] = len(valid_rows)
    return agg


# ── Evaluation pipeline ──────────────────────────────────────────────────────

def evaluate_checkpoint(
    generate_fn: GenerateFn,
    samples: list[dict],
    system_prompt_fn: Callable[[str], str] | None = None,
    log_to_mlflow: bool = True,
) -> dict:
    """Score a trained checkpoint against the shared metric suite.

    For each sample: render the persona prompt, generate a response via
    ``generate_fn``, and score it with :func:`evaluation.metrics.evaluate_response`.
    Per-sample metrics and run-level ``avg_*`` aggregates (including per-persona
    composites) are logged to the active MLflow run — the **same keys C1 logs**,
    so the two conditions line up directly in the tracker.

    Returns the aggregate metric dict. ``generate_fn`` is injectable so the whole
    pipeline can be exercised offline without loading a model.
    """
    # Imported lazily: evaluation.metrics pulls in the OpenAI judge client, which
    # need not be present just to import this module.
    from evaluation.metrics import evaluate_response, log_eval_to_mlflow

    sp_fn = system_prompt_fn or render_system_prompt
    rows: list[dict] = []

    for i, sample in enumerate(samples):
        system_prompt = sp_fn(sample["persona"])
        response = generate_fn(system_prompt, sample["user"])
        result = evaluate_response(
            user_message=sample["user"],
            response=response,
            reference=sample.get("reference"),
        )
        if log_to_mlflow:
            log_eval_to_mlflow(result, step=i)
        rows.append({
            **result.to_dict(),
            "persona": sample["persona"],
            "composite_score": result.composite_score,
        })
        if result.metadata.get("judge_failed"):
            logger.warning(
                "  sample %d/%d persona=%-14s JUDGE FAILED — composite=0.000 is not"
                " a real score, excluded from the aggregate",
                i + 1, len(samples), sample["persona"],
            )
        else:
            logger.info(
                "  sample %d/%d persona=%-14s composite=%.3f",
                i + 1, len(samples), sample["persona"], result.composite_score,
            )

    agg = avg_scores(rows)
    if agg.get("n_judge_failed"):
        logger.warning(
            "  %d/%d samples excluded from this aggregate (judge failures) —"
            " scored on %d.", agg["n_judge_failed"], len(rows), agg["n_samples_scored"],
        )

    if log_to_mlflow and rows:
        import mlflow

        for key, val in agg.items():
            if key != "persona":
                mlflow.log_metric(f"avg_{key}", val)
        for persona in {r["persona"] for r in rows}:
            persona_agg = avg_scores([r for r in rows if r["persona"] == persona])
            if "composite_score" in persona_agg:
                mlflow.log_metric(f"avg_composite_{persona}", persona_agg["composite_score"])

    return agg


# ── Harmony (gpt-oss) output handling ───────────────────────────────────────────

_HARMONY_FINAL = "<|channel|>final<|message|>"
_HARMONY_TRAILERS = ("<|return|>", "<|end|>", "<|start|>", "<|endoftext|>", "<|call|>")


def extract_final_response(raw: str) -> tuple[str, bool]:
    """Pull the user-visible answer out of a gpt-oss "harmony" generation.

    gpt-oss emits a hidden ``analysis`` channel (chain-of-thought) before the
    ``final`` channel. Scoring the raw decode would judge the reasoning trace, not
    the answer — the same failure that once corrupted the Qwen baseline. Returns
    ``(text, truncated)``; ``truncated`` is True when generation stopped before a
    final channel appeared (token budget spent on reasoning), in which case the
    text is empty and the caller must count it, not score it as a real answer.
    """
    if _HARMONY_FINAL in raw:
        text = raw.rsplit(_HARMONY_FINAL, 1)[1]
        for t in _HARMONY_TRAILERS:
            text = text.split(t, 1)[0]
        return text.strip(), False
    if "<|channel|>" in raw:  # analysis started, final never reached
        return "", True
    return raw.strip(), False  # not a harmony transcript at all


# ── Real generator (GPU node) ──────────────────────────────────────────────────

class HFCheckpointGenerator:
    """Generate responses from a base model + PEFT adapter checkpoint.

    GPU-node only. torch / transformers / peft are imported lazily inside
    :meth:`_ensure_loaded`, so importing this class costs nothing on CPU and the
    surrounding harness stays testable without the training stack installed.
    """

    def __init__(
        self,
        base_model_id: str,
        adapter_path: str | None = None,
        *,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        load_in_4bit: bool = True,
    ) -> None:
        self.base_model_id = base_model_id
        self.adapter_path = adapter_path
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.load_in_4bit = load_in_4bit
        self._model = None
        self._tokenizer = None
        self.harmony = "gpt-oss" in base_model_id.lower()
        self.last_truncated = False
        self.n_truncated = 0

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        kwargs: dict = {"device_map": "auto"}
        if self.load_in_4bit:
            from transformers import BitsAndBytesConfig

            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                # float16, not bfloat16: BF16 tensor-core acceleration needs
                # Ampere (SM 8.0+); a T4 (Turing, SM 7.5) errors out on this.
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )

        model = AutoModelForCausalLM.from_pretrained(self.base_model_id, **kwargs)
        if self.adapter_path:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, self.adapter_path)
        model.eval()

        tokenizer = AutoTokenizer.from_pretrained(self.base_model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        self._model, self._tokenizer = model, tokenizer

    def __call__(self, system_prompt: str, user_message: str) -> str:
        self._ensure_loaded()
        import torch

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        template_kwargs = {"reasoning_effort": "low"} if self.harmony else {}
        inputs = self._tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", **template_kwargs
        ).to(self._model.device)

        with torch.no_grad():
            output = self._model.generate(
                inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=self.temperature > 0,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        generated = output[0][inputs.shape[-1]:]
        if self.harmony:
            raw = self._tokenizer.decode(generated, skip_special_tokens=False)
            text, self.last_truncated = extract_final_response(raw)
            self.n_truncated += int(self.last_truncated)
            return text
        self.last_truncated = False
        return self._tokenizer.decode(generated, skip_special_tokens=True).strip()
