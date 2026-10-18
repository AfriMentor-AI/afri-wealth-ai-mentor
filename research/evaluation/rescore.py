"""Re-judge the saved responses of a comparative_eval results file with a *different* judge model.

Training/selection used one judge family; a result that only holds under that judge is not evidence of better
advice. This reuses the stored (user_message, response) pairs — no regeneration, no GPU — and reports per-condition
composites plus paired bootstrap CIs under the new judge.

    EVAL_JUDGE_MODEL=deepseek/deepseek-chat-v3.1 LLM_BASE_URL=https://openrouter.ai/api/v1 LLM_API_KEY=... \
    JUDGE_CACHE=research/evaluation/results/judge_cache_deepseek.jsonl \
    python research/evaluation/rescore.py research/evaluation/results/comparative_llama31_8b_v2b.json
"""
from __future__ import annotations

import json
import os
import random
import statistics as st
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DIMS = ("persona_adherence", "cultural_fluency", "anti_dependency", "financial_accuracy", "urgency")
WEIGHTS = (0.25, 0.20, 0.20, 0.20, 0.15)  # identical to metrics.EvalResult.composite_score


def composite(scores: dict) -> float:
    return sum(scores[d] * w for d, w in zip(DIMS, WEIGHTS))


def paired_ci(a: dict[str, float], b: dict[str, float], n: int = 5000, seed: int = 1) -> tuple[int, float, float, float]:
    ks = [k for k in a if k in b]
    diff = [a[k] - b[k] for k in ks]
    if not diff:
        return 0, float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    means = sorted(st.mean(rng.choices(diff, k=len(diff))) for _ in range(n))
    return len(ks), st.mean(diff), means[int(0.025 * n)], means[int(0.975 * n) - 1]


def rescore(results: dict, workers: int = 8, judge=None) -> dict:
    """Returns {cond: {prompt: {dim scores..., composite}}}; judge-failed rows are dropped, never zeroed."""
    if judge is None:
        from evaluation.metrics import score_all_dimensions as judge
    out: dict = {}
    for cid, cond in results["conditions"].items():
        rows = [r for r in cond.get("rows", []) if r.get("response")]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            scored = list(pool.map(lambda r: judge(r["user_message"], r["response"]), rows))
        out[cid] = {}
        for r, s in zip(rows, scored):
            if s.get("_judge_failed"):
                continue
            out[cid][r["user_message"]] = {**{d: s[d] for d in DIMS}, "composite": composite(s)}
    return out


def main() -> None:
    path = sys.argv[1]
    res = json.load(open(path, encoding="utf-8"))
    model = os.getenv("EVAL_JUDGE_MODEL", "openai/gpt-oss-120b")
    scored = rescore(res, workers=int(os.getenv("RESCORE_WORKERS", "8")))
    total = {cid: sum(1 for r in c.get("rows", []) if r.get("response")) for cid, c in res["conditions"].items()}
    short = {cid: f"{len(rows)}/{total[cid]}" for cid, rows in scored.items() if len(rows) < 0.95 * total[cid]}
    if short:
        print(f"\nWARNING: judge failures dropped rows ({short}). Re-run (failures are not cached) before reading anything into this.")
    print(f"\n=== re-judged with {model} ===")
    print(f"{'cond':5}{'n':>4}  " + "  ".join(f"{d[:8]:>8}" for d in DIMS) + "  composite  (original judge)")
    for cid, rows in scored.items():
        if not rows:
            continue
        m = {d: st.mean(r[d] for r in rows.values()) for d in DIMS}
        comp = st.mean(r["composite"] for r in rows.values())
        orig = res["conditions"][cid]["aggregate"].get("composite_score", float("nan"))
        print(f"{cid:5}{len(rows):4}  " + "  ".join(f"{m[d]:8.3f}" for d in DIMS) + f"  {comp:9.3f}  ({orig:.3f})")
    comps = {c: {k: v["composite"] for k, v in rows.items()} for c, rows in scored.items()}
    ids = list(comps)
    print("\npaired composite differences (A - B), 95% bootstrap CI over prompts")
    for a in ids:
        for b in ids:
            if a < b or a == b:
                continue
            n, m, lo, hi = paired_ci(comps[a], comps[b])
            if n == 0:
                print(f"{a:4} - {b:4}: no prompts scored in both conditions")
                continue
            flag = "  <-- excludes 0" if lo > 0 or hi < 0 else ""
            print(f"{a:4} - {b:4}: {m:+.3f}  [{lo:+.3f}, {hi:+.3f}]  n={n}{flag}")
    outp = Path(path).with_name(Path(path).stem + f"_rescored_{model.replace('/', '_')}.json")
    outp.write_text(json.dumps({"judge": model, "scores": scored}, indent=1), encoding="utf-8")
    print("\nwritten:", outp)


if __name__ == "__main__":
    main()
