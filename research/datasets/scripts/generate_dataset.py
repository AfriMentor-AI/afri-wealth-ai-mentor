"""Generate the v2 evaluation/training dataset (papers-revision track).

Why this exists: the v1 dataset was ~22 curated SFT pairs and 72 preference pairs
in which *every* pair was labelled ``preferred: "a"`` — so the test set could not
exceed N=5 and the C4 reward probe was a constant classifier. This script builds
a larger set with honest structure:

  * prompts are generated per (persona x country x topic) scenario, deduplicated;
  * ``chosen`` = teacher response under the CHIOMA persona system prompt;
  * ``rejected`` = teacher response under an explicit *defect* prompt drawn from
    the rejection taxonomy in configs/dataset.yaml;
  * A/B positions are randomised (seeded), so ``preferred`` carries both classes;
  * splits are by *prompt*, so no prompt appears in more than one split.

The data is synthetic (teacher-generated). Papers must say so. Teacher must not
be one of the evaluated models; a human spot-check sample is exported for review.

Resumable: every LLM call is cached in ``<out>/cache.jsonl`` keyed by its inputs,
so a rate-limit/quota stop can be continued by re-running the same command.

Usage:
    GEN_API_KEY=... GEN_BASE_URL=https://openrouter.ai/api/v1 GEN_MODEL=<teacher> \
      python research/datasets/scripts/generate_dataset.py --n-prompts 300
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import random
import sys
import time
from collections.abc import Callable
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[2]
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

DEFAULT_OUT = _RESEARCH_ROOT / "datasets" / "splits_v2"

PERSONAS = ["chioma-base", "market-queen", "tech-founder", "trader", "rural-hustler", "creative"]
COUNTRIES = {
    "NG": "Nigeria", "GH": "Ghana", "KE": "Kenya", "ZA": "South Africa",
    "ET": "Ethiopia", "SN": "Senegal", "RW": "Rwanda",
}
TOPICS = [
    "pricing goods when supplier costs rise", "separating business and personal money",
    "saving with a rotating savings group (esusu/susu/chama/stokvel)", "taking a loan or supplier credit",
    "mobile money for business payments", "managing inventory and stock-outs",
    "surviving a seasonal income slump", "foreign-exchange risk on imported stock",
    "registering the business formally", "hiring the first employee",
    "record-keeping when everything is in your head", "a family member asking to borrow business money",
    "deciding whether to expand to a second location", "digital marketing on a tiny budget",
    "insurance and protecting against loss", "escaping a debt trap from a digital lender",
    "co-founder disagreement over equity", "pricing creative or service work",
    "paying yourself a salary from the business", "a risky 'double your money' investment offer",
]
# Same taxonomy as configs/dataset.yaml -> formats.dpo_pairs.rejection_reasons
DEFECTS = {
    "generic_response": "You are a generic, cautious assistant. Give bland, non-committal, "
                        "generic advice with no specific numbers and no clear next step.",
    "culturally_misaligned": "You are a Western personal-finance assistant. Give advice that assumes "
                             "formal banking, credit scores, 401k/retirement accounts and stock brokerage "
                             "access, ignoring informal-market realities.",
    "dependency_creating": "You are an assistant that tells the user exactly what to do and never explains "
                           "the reasoning, encouraging them to keep asking you before every decision.",
    "factually_incorrect": "You are an overconfident assistant. Give confident advice containing a "
                           "plausible-sounding but financially wrong claim (e.g. bad interest arithmetic "
                           "or a guaranteed-return promise).",
}

ChatFn = Callable[[str, str, float], str]  # (system, user, temperature) -> text


def _key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


class CachedLLM:
    """Wraps a ChatFn with an append-only jsonl cache so runs are resumable."""

    def __init__(self, chat_fn: ChatFn, cache_path: Path):
        self.chat_fn = chat_fn
        self.cache_path = cache_path
        self.cache: dict[str, str] = {}
        if cache_path.exists():
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.cache[rec["k"]] = rec["v"]

    def __call__(self, system: str, user: str, temperature: float, salt: str = "") -> str:
        k = _key(system, user, f"{temperature}", salt)
        if k in self.cache:
            return self.cache[k]
        text = self.chat_fn(system, user, temperature).strip()
        self.cache[k] = text
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"k": k, "v": text}) + "\n")
        return text


def make_openai_chat_fn(api_key: str, base_url: str, model: str, max_tokens: int = 900) -> ChatFn:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(system: str, user: str, temperature: float) -> str:
        last: Exception | None = None
        for attempt in range(6):
            try:
                resp = client.chat.completions.create(
                    model=model, temperature=temperature, max_tokens=max_tokens,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:  # noqa: BLE001 — rate limits/timeouts: back off and retry
                last = exc
                time.sleep(min(60, 2 ** attempt * 3))
        raise RuntimeError(f"LLM call failed after retries: {last}")

    return chat


# ── prompt generation ───────────────────────────────────────────────────────────

def sample_scenarios(n: int, rng: random.Random) -> list[dict]:
    grid = [
        {"persona_slug": p, "country_code": c, "country": cn, "topic": t}
        for p in PERSONAS for c, cn in COUNTRIES.items() for t in TOPICS
    ]
    rng.shuffle(grid)
    return grid[: n * 2]  # oversample: some prompts are dropped as near-duplicates


def normalise(text: str) -> str:
    return " ".join(text.lower().split())


def is_near_duplicate(text: str, seen: list[str], threshold: float = 0.82) -> bool:
    t = normalise(text)
    return any(difflib.SequenceMatcher(None, t, s).ratio() >= threshold for s in seen)


def generate_prompts(llm: CachedLLM, n: int, rng: random.Random) -> list[dict]:
    system = ("You write realistic first-person messages that a young African micro-entrepreneur "
              "would send to an AI business mentor. One message, 1-3 sentences, concrete details "
              "(numbers, local context), no greeting, no mention of an AI or a persona name. "
              "Output only the message text.")
    out: list[dict] = []
    seen: list[str] = []
    for sc in sample_scenarios(n, rng):
        if len(out) >= n:
            break
        user = (f"Country: {sc['country']}. Topic: {sc['topic']}. "
                f"The person is a {sc['persona_slug'].replace('-', ' ')} type of entrepreneur.")
        text = llm(system, user, 0.95, salt=str(len(out)))
        if len(text) < 20 or is_near_duplicate(text, seen):
            continue
        seen.append(normalise(text))
        out.append({**sc, "prompt": text})
    return out


# ── response / preference generation ──────────────────────────────────────────────

def build_records(llm: CachedLLM, prompts: list[dict], persona_prompt_fn: Callable[[str], str],
                  rng: random.Random) -> list[dict]:
    records = []
    for i, p in enumerate(prompts):
        chosen = llm(persona_prompt_fn(p["persona_slug"]), p["prompt"], 0.7)
        reason = rng.choice(sorted(DEFECTS))
        rejected = llm(DEFECTS[reason], p["prompt"], 0.7)
        chosen_is_a = rng.random() < 0.5
        a, b = (chosen, rejected) if chosen_is_a else (rejected, chosen)
        records.append({
            "pair_id": f"g{i:04d}", "persona_slug": p["persona_slug"],
            "country": p["country_code"], "topic": p["topic"], "prompt": p["prompt"],
            "chosen": chosen, "rejected": rejected, "rejection_reason": reason,
            "response_a": a, "response_b": b, "preferred": "a" if chosen_is_a else "b",
        })
    return records


def split_by_prompt(records: list[dict], test_frac: float, val_frac: float,
                    rng: random.Random) -> dict[str, list[dict]]:
    recs = list(records)
    rng.shuffle(recs)
    n = len(recs)
    n_test, n_val = int(n * test_frac), int(n * val_frac)
    return {"test": recs[:n_test], "val": recs[n_test:n_test + n_val], "train": recs[n_test + n_val:]}


def write_splits(splits: dict[str, list[dict]], out: Path, system_prompt_fn: Callable[[str], str]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    stats: dict = {}
    for name, recs in splits.items():
        sft = [{
            "conversation_id": r["pair_id"], "persona_slug": r["persona_slug"], "country": r["country"],
            "sector": r["topic"],
            "messages": [
                {"role": "system", "content": system_prompt_fn(r["persona_slug"])},
                {"role": "user", "content": r["prompt"]},
                {"role": "assistant", "content": r["chosen"]},
            ],
        } for r in recs]
        dpo = [{k: r[k] for k in ("pair_id", "persona_slug", "prompt", "chosen", "rejected", "rejection_reason")}
               for r in recs]
        rlhf = [{k: r[k] for k in ("pair_id", "persona_slug", "prompt", "response_a", "response_b",
                                   "preferred", "rejection_reason")} for r in recs]
        for prefix, rows in (("sft", sft), ("dpo", dpo), ("rlhf", rlhf)):
            with open(out / f"{prefix}_{name}.jsonl", "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        stats[name] = {
            "n": len(recs),
            "preferred_a": sum(r["preferred"] == "a" for r in recs),
            "preferred_b": sum(r["preferred"] == "b" for r in recs),
        }
    return stats


def export_review_sample(records: list[dict], out: Path, k: int, rng: random.Random) -> None:
    sample = rng.sample(records, min(k, len(records)))
    with open(out / "human_review_sample.jsonl", "w", encoding="utf-8") as f:
        for r in sample:
            f.write(json.dumps({"pair_id": r["pair_id"], "prompt": r["prompt"], "chosen": r["chosen"],
                                "rejected": r["rejected"], "reviewer_ok": None, "reviewer_notes": ""},
                               ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n-prompts", type=int, default=300)
    ap.add_argument("--test-frac", type=float, default=0.20)
    ap.add_argument("--val-frac", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--review-sample", type=int, default=30)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    key = os.getenv("GEN_API_KEY") or os.getenv("LLM_API_KEY", "")
    base = os.getenv("GEN_BASE_URL") or os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.getenv("GEN_MODEL", "openai/gpt-oss-120b")
    if not key:
        raise SystemExit("Set GEN_API_KEY (and GEN_BASE_URL / GEN_MODEL) — no API key found.")

    from evaluation.checkpoint_eval import render_system_prompt

    out = Path(args.out)
    rng = random.Random(args.seed)
    llm = CachedLLM(make_openai_chat_fn(key, base, model), out / "cache.jsonl")

    prompts = generate_prompts(llm, args.n_prompts, rng)
    records = build_records(llm, prompts, render_system_prompt, rng)
    splits = split_by_prompt(records, args.test_frac, args.val_frac, rng)
    stats = write_splits(splits, out, render_system_prompt)
    export_review_sample(records, out, args.review_sample, rng)

    manifest = {"dataset_version": "2.0", "synthetic": True, "teacher_model": model, "teacher_base_url": base,
                "seed": args.seed, "n_prompts_requested": args.n_prompts, "n_records": len(records),
                "splits": stats}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
