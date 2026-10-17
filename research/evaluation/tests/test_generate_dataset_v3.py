import importlib.util
import json
from pathlib import Path

_P = Path(__file__).resolve().parents[2] / "datasets" / "scripts" / "generate_dataset_v3.py"
_s = importlib.util.spec_from_file_location("gen_v3", _P)
g = importlib.util.module_from_spec(_s)
_s.loader.exec_module(g)


def w(n):  # n-word text
    return " ".join(["word"] * n)


def test_pick_chooses_best_and_a_comparable_worst_with_a_real_gap():
    r = g.pick([(w(100), 0.80), (w(110), 0.55), (w(95), 0.70), (w(105), 0.40)])
    assert r["best"][1] == 0.80 and r["worst"][1] == 0.40 and r["spread"] == 0.40 - 0 + 0.0 or r["spread"] > 0.39


def test_pick_refuses_a_pair_when_the_gap_is_noise_or_the_length_differs():
    close = g.pick([(w(100), 0.70), (w(100), 0.66), (w(100), 0.65)])
    assert close["best"] and close["worst"] is None            # gap < 0.10 -> SFT only, no DPO pair
    lengthy = g.pick([(w(140), 0.80), (w(70), 0.40)])           # 2x length ratio -> contrast would be length
    assert lengthy["worst"] is None


def test_pick_drops_out_of_band_and_low_quality():
    assert g.pick([(w(300), 0.9), (w(20), 0.9)]) is None       # outside the 60-150 word band
    assert g.pick([(w(100), 0.50), (w(100), 0.45)]) is None     # best below the floor


def test_records_and_splits_use_the_minimal_prompt_and_conversational_dpo(tmp_path):
    prompts = [{"persona_slug": "trader", "country_code": "NG", "topic": "t", "prompt": f"question number {i} about stock"}
               for i in range(8)]
    seq = iter([0.8, 0.5, 0.7, 0.4] * 8)
    llm = lambda sys_, user, t, salt="": f"answer {salt} " + w(100)  # noqa: E731
    gen = g.generate(llm, lambda u, r: dict.fromkeys(g.DIMS, next(seq)), lambda slug: "FULL", prompts, 4, 1)
    recs = g.to_records(gen)
    assert len(recs) == 8 and all(r["rejected"] for r in recs)
    stats = g.write_splits(recs, tmp_path, n_test=2, n_val=1, seed=1)
    sft = json.loads((tmp_path / "sft_train.jsonl").read_text().splitlines()[0])
    assert sft["messages"][0]["content"].startswith("You are Chioma") and len(sft["messages"][0]["content"]) < 200
    dpo = json.loads((tmp_path / "dpo_train.jsonl").read_text().splitlines()[0])
    assert dpo["prompt"][0]["role"] == "system" and dpo["chosen"][0]["role"] == "assistant"
    assert dpo["chosen_score"] > dpo["rejected_score"]
    assert stats["test"]["n_prompts"] == 2


def test_scenario_grid_is_big_enough_and_dedupe_is_fast(tmp_path):
    import random as _r
    import time
    assert len(g.gd.PERSONAS) * len(g.COUNTRIES_V3) * len(g.TOPICS_V3) * len(g.STYLES_V3) > 10_000   # v2's grid was 840
    calls = []

    def llm(system, user, t, salt=""):
        calls.append(salt)
        import hashlib
        h = hashlib.sha256(salt.encode()).hexdigest()
        return f"Ask {h[:6]} regarding {h[6:12]} and {h[12:18]} because {h[18:24]} happened near {h[24:30]} recently"

    t0 = time.time()
    out = g.make_prompts(llm, 150, _r.Random(1), 1)
    assert time.time() - t0 < 5 and len(out) >= 100


def test_near_duplicates_and_held_out_prompts_are_removed():
    a = g._shingles("my supplier raised the price of flour by fifteen percent and my customers are complaining loudly")
    b = g._shingles("my supplier raised the price of flour by fifteen percent and my customers are complaining a lot")
    c = g._shingles("i want to hire a second employee but i worry about paying wages during the slow rainy season")
    assert g.near_duplicate(b, [a]) and not g.near_duplicate(c, [a])
