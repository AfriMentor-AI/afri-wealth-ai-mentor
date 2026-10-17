"""v3 dataset: best-of-N teacher answers ranked by a judge (rejection-sampling SFT + quality-contrast DPO pairs).

v2's preference pairs differed in *form* (chosen ends with a question 98% / rejected 1%), so DPO reached 100%
accuracy by learning the template and carried no quality signal; 210 examples were also too few. v3:

  * N teacher samples per prompt, all under the same persona prompt + format instruction + length band;
  * a SELECTION judge scores each sample (must differ from the judges used for evaluation);
  * SFT target  = best sample (rejection sampling) — only if its score clears a floor;
  * DPO pair    = best vs worst, only if the score gap is real and the lengths are comparable, so the contrast is
                  quality, not length or template;
  * training/inference system prompt = the ~30-token minimal prompt (the fine-tuned model must carry the persona).

Synthetic, and judge-selected: the paper must say so, and results must be confirmed by held-out judges + humans.
Resumable (teacher + judge caches). Usage:
    GEN_API_KEY=... GEN_BASE_URL=https://openrouter.ai/api/v1 GEN_MODEL=qwen/qwen-2.5-72b-instruct \
    SELECT_JUDGE_MODEL=deepseek/deepseek-chat-v3.1 python research/datasets/scripts/generate_dataset_v3.py --n-prompts 1700
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import statistics as st
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RESEARCH = _HERE.parents[1]
if str(_RESEARCH) not in sys.path:
    sys.path.insert(0, str(_RESEARCH))

from evaluation.style_prompts import CHOSEN_STYLE, minimal_system_prompt  # noqa: E402

_spec = importlib.util.spec_from_file_location("generate_dataset", _HERE / "generate_dataset.py")
gd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gd)

DIMS = ("persona_adherence", "cultural_fluency", "anti_dependency", "financial_accuracy", "urgency")
WEIGHTS = (0.25, 0.20, 0.20, 0.20, 0.15)
WORD_BAND = (60, 150)          # a sample outside this band is not a candidate
MIN_BEST_SCORE = 0.55          # SFT target must clear this
MIN_GAP = 0.10                 # best - worst for a DPO pair
MAX_LEN_RATIO = 1.35           # words(best)/words(worst) must lie in [1/1.35, 1.35]


COUNTRIES_V3 = {"NG": "Nigeria", "GH": "Ghana", "KE": "Kenya", "ZA": "South Africa", "ET": "Ethiopia",
                "SN": "Senegal", "RW": "Rwanda", "UG": "Uganda", "TZ": "Tanzania", "CI": "Cote d'Ivoire"}
TOPICS_V3 = gd.TOPICS + [
    "keeping a loyal customer who keeps asking for credit", "saving for school fees without touching the business",
    "buying in bulk to get a discount but tying up cash", "dealing with a late-paying customer",
    "a supplier who wants full payment upfront", "deciding between two business ideas", "pricing in a currency that keeps falling",
    "a partner who is not pulling their weight", "scaling from home to a rented shop", "an unexpected tax or council levy",
    "using a motorbike or van for deliveries", "selling on WhatsApp or Instagram", "joining a cooperative or trade association",
    "protecting savings from inflation", "handling a bad month without borrowing", "firing or disciplining a worker",
    "a relative who works for you and underperforms", "knowing when to say no to a big order", "keeping records with only a phone",
    "preparing for a festival or seasonal rush", "equipment breaking down at the worst time", "pivoting after a product stops selling",
    "mixing business with a side job", "negotiating rent with a landlord", "opening a bank or mobile-money account for the business",
    "a customer dispute over quality", "reinvesting profit vs. paying yourself", "starting with almost no capital",
    "hiring family vs. strangers", "growing a one-person service into a team", "managing a loan from a cooperative",
    "competing with a cheaper rival", "paying for transport that eats the margin", "buying second-hand equipment",
    "planning for a slow rainy season", "an investor or 'angel' offering money for a share", "a government grant or NGO programme",
    "learning a skill versus hiring someone who has it", "adding a new product line", "what to do with a sudden windfall",
    "a theft or fraud loss", "weighing a partnership with a bigger company", "keeping a business going while studying",
    "supplier quality problems", "export or cross-border trade paperwork", "digital bookkeeping tools",
]
STYLES_V3 = ["Write it short and blunt.", "Write it sounding worried and a little emotional.",
             "Include two or three specific numbers.", "Ask two related questions in one message.",
             "Write it casually, the way people really text.", "Mention one thing they already tried that did not work."]


def composite(scores: dict) -> float:
    return sum(scores[d] * w for d, w in zip(DIMS, WEIGHTS))


def eligible(samples: list[tuple[str, float]]) -> list[tuple[str, float]]:
    lo, hi = WORD_BAND
    return [(t, s) for t, s in samples if lo <= len(t.split()) <= hi]


def pick(samples: list[tuple[str, float]]) -> dict | None:
    """samples = [(text, judge_composite)]. Returns {'best','worst'|None,...} or None if nothing usable."""
    pool = eligible(samples)
    if not pool:
        return None
    best = max(pool, key=lambda x: x[1])
    if best[1] < MIN_BEST_SCORE:
        return None
    worst = None
    for t, s in sorted(pool, key=lambda x: x[1]):
        ratio = len(best[0].split()) / max(1, len(t.split()))
        if best[1] - s >= MIN_GAP and 1 / MAX_LEN_RATIO <= ratio <= MAX_LEN_RATIO:
            worst = (t, s)
            break
    return {"best": best, "worst": worst, "spread": max(s for _, s in pool) - min(s for _, s in pool)}


def _shingles(text: str, k: int = 3) -> set:
    w = gd.normalise(text).split()
    return {" ".join(w[i:i + k]) for i in range(max(1, len(w) - k + 1))}


def near_duplicate(sh: set, pool: list[set], threshold: float = 0.5) -> bool:
    """Token-shingle Jaccard (fast; difflib was O(n^2) with a heavy constant and stalled at ~1k prompts)."""
    return any(len(sh & o) / max(1, len(sh | o)) >= threshold for o in pool)


def make_prompts(llm, n: int, rng: random.Random, workers: int, held_texts: list[str] = ()) -> list[dict]:
    system = ("You write realistic first-person messages that a young African micro-entrepreneur would send to an "
              "AI business mentor. One message, 1-4 sentences, concrete local detail, no greeting, no mention of an "
              "AI or a persona name. Output only the message text.")
    grid = [{"persona_slug": p, "country_code": c, "country": cn, "topic": t, "style": st_}
            for p in gd.PERSONAS for c, cn in COUNTRIES_V3.items() for t in TOPICS_V3 for st_ in STYLES_V3]
    rng.shuffle(grid)
    scenarios = grid[: int(n * 1.3)]

    def one(i_sc):
        i, sc = i_sc
        kind = gd.PERSONA_BLURB.get(sc["persona_slug"], "small-business owner")
        user = (f"Country: {sc['country']}. Topic: {sc['topic']}. The person is a {kind}. {sc['style']}")
        return llm(system, user, 0.95, salt=str(i))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        texts = list(pool.map(one, enumerate(scenarios)))
    pool_sh = [_shingles(h) for h in held_texts]
    out = []
    for sc, text in zip(scenarios, texts):
        if len(out) >= n:
            break
        if len(text) < 20 or any(f in text.lower() for f in gd.FORBIDDEN_IN_PROMPTS):
            continue
        sh = _shingles(text)
        if near_duplicate(sh, pool_sh):
            continue
        pool_sh.append(sh)
        out.append({**{k: sc[k] for k in ("persona_slug", "country_code", "country", "topic")}, "prompt": text})
    return out


def generate(llm, judge, persona_prompt_fn, prompts: list[dict], n_samples: int, workers: int) -> list[dict]:
    def one(p):
        outs = []
        for k in range(n_samples):
            text = llm(persona_prompt_fn(p["persona_slug"]), p["prompt"] + CHOSEN_STYLE, 0.9, salt=f"s{k}")
            outs.append((text, composite(judge(p["prompt"], text))))
        return p, outs

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return [{"prompt": p, "samples": outs} for p, outs in pool.map(one, prompts)]


def to_records(generated: list[dict]) -> list[dict]:
    recs = []
    for i, g in enumerate(generated):
        r = pick(g["samples"])
        if r is None:
            continue
        p = g["prompt"]
        recs.append({
            "pair_id": f"v3_{i:05d}", "persona_slug": p["persona_slug"], "country": p["country_code"],
            "topic": p["topic"], "prompt": p["prompt"], "chosen": r["best"][0], "chosen_score": r["best"][1],
            "rejected": r["worst"][0] if r["worst"] else None, "rejected_score": r["worst"][1] if r["worst"] else None,
            "spread": r["spread"], "n_candidates": len(eligible(g["samples"])),
        })
    return recs


def write_splits(recs: list[dict], out: Path, n_test: int, n_val: int, seed: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    recs = list(recs)
    random.Random(seed).shuffle(recs)
    splits = {"test": recs[:n_test], "val": recs[n_test:n_test + n_val], "train": recs[n_test + n_val:]}
    for name, rows in splits.items():
        sft = [{"conversation_id": r["pair_id"], "persona_slug": r["persona_slug"], "country": r["country"],
                "sector": r["topic"],
                "messages": [{"role": "system", "content": minimal_system_prompt(r["persona_slug"])},
                             {"role": "user", "content": r["prompt"]},
                             {"role": "assistant", "content": r["chosen"]}]} for r in rows]
        dpo = [{"pair_id": r["pair_id"], "persona_slug": r["persona_slug"],
                "prompt": [{"role": "system", "content": minimal_system_prompt(r["persona_slug"])},
                           {"role": "user", "content": r["prompt"]}],
                "chosen": [{"role": "assistant", "content": r["chosen"]}],
                "rejected": [{"role": "assistant", "content": r["rejected"]}],
                "chosen_score": r["chosen_score"], "rejected_score": r["rejected_score"]}
               for r in rows if r["rejected"] is not None]
        for prefix, data in (("sft", sft), ("dpo", dpo)):
            with open(out / f"{prefix}_{name}.jsonl", "w", encoding="utf-8") as f:
                for d in data:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return {k: {"n_prompts": len(v), "n_dpo_pairs": sum(r["rejected"] is not None for r in v)} for k, v in splits.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n-prompts", type=int, default=1700)
    ap.add_argument("--n-samples", type=int, default=4)
    ap.add_argument("--n-test", type=int, default=120)
    ap.add_argument("--n-val", type=int, default=100)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(_RESEARCH / "datasets" / "splits_v3"))
    ap.add_argument("--exclude-prompts-from", nargs="*", default=[], help="jsonl files whose prompts must not reappear")
    args = ap.parse_args()

    key, base = os.environ["GEN_API_KEY"], os.environ["GEN_BASE_URL"]
    gen_model = os.getenv("GEN_MODEL", "qwen/qwen-2.5-72b-instruct")
    sel_model = os.getenv("SELECT_JUDGE_MODEL", "deepseek/deepseek-chat-v3.1")
    # The selection judge is configured through the same env the metrics module reads.
    os.environ.update({"LLM_API_KEY": key, "LLM_BASE_URL": base, "EVAL_JUDGE_MODEL": sel_model})
    os.environ.setdefault("JUDGE_CACHE", str(Path(args.out) / "select_judge_cache.jsonl"))
    from evaluation.checkpoint_eval import render_system_prompt
    from evaluation.metrics import score_all_dimensions

    out = Path(args.out)
    rng = random.Random(args.seed)
    llm = gd.CachedLLM(gd.make_openai_chat_fn(key, base, gen_model, max_tokens=400), out / "teacher_cache.jsonl")

    held = []
    for f in args.exclude_prompts_from:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            held.append(r["prompt"] if isinstance(r.get("prompt"), str) else r["messages"][1]["content"])
    prompts = make_prompts(llm, args.n_prompts, rng, args.workers, held)

    def judge(u, r):
        s = score_all_dimensions(u, r)
        if s.get("_judge_failed"):
            raise RuntimeError("selection judge failed; refusing to select on a zero score")
        return s

    generated = generate(llm, judge, render_system_prompt, prompts, args.n_samples, args.workers)
    recs = to_records(generated)
    spreads = [r["spread"] for r in recs]
    stats = write_splits(recs, out, args.n_test, args.n_val, args.seed)
    manifest = {"dataset_version": "3.0", "synthetic": True, "teacher_model": gen_model, "selection_judge": sel_model,
                "n_prompts": len(prompts), "n_samples_per_prompt": args.n_samples, "n_kept_for_sft": len(recs),
                "mean_within_prompt_spread": round(st.mean(spreads), 3) if spreads else None,
                "word_band": WORD_BAND, "min_best_score": MIN_BEST_SCORE, "min_gap": MIN_GAP,
                "max_len_ratio": MAX_LEN_RATIO, "seed": args.seed, "splits": stats}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
