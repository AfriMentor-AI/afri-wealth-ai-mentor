"""Render the C4.3 safety report from ``safety_results.json``.

Reads the JSON written by ``safety_eval.py`` and produces a Markdown safety
report (``safety_report.md``) for the research console / paper appendix. Kept
deliberately simple and honest: conditions the environment could not generate
render as **pending**, never as numbers.

Usage:
    python research/evaluation/safety_table.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = _RESEARCH_ROOT / "evaluation" / "results" / "safety_results.json"
DEFAULT_MD_OUT = _RESEARCH_ROOT / "evaluation" / "results" / "safety_report.md"

CONDITION_LABELS = {
    "C0": "C0: Unaligned baseline",
    "C1": "C1: Baseline Prompting",
    "C2": "C2: Supervised Fine-Tuning",
    "C3": "C3: Contrastive Learning (DPO)",
    "C4": "C4: RLHF / Preference Opt.",
}


def _pct(rate) -> str:
    return "—" if rate is None else f"{float(rate) * 100:.1f}%"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_markdown(results: dict) -> str:
    meta = results.get("meta", {})
    inst = results.get("instrument_validation") or {}
    conditions = results.get("conditions", {})
    reg = results.get("regression", {})

    lines: list[str] = []
    lines.append("# C4.3 — Safety / Harmlessness Report")
    lines.append("")
    lines.append(f"Red-team corpus: `{meta.get('corpus', '?')}` "
                 f"({meta.get('attacks_input', '?')} risky + {meta.get('controls_input', '?')} "
                 f"control inputs, {meta.get('output_surface_rows', '?')} output-surface rows).  ")
    lines.append(f"Harm scorer: {meta.get('harm_scorer', '?')} (rules `{meta.get('rules_version', '?')}`).  ")
    lines.append(f"Generated at: {meta.get('generated_at', '?')}.")
    lines.append("")
    lines.append(f"> {meta.get('note', '')}")
    lines.append("")
    lines.append(f"> **Bias scope.** {meta.get('bias_scope', '')}")
    lines.append("")

    # ── 1. Instrument validation ──────────────────────────────────────────────
    lines.append("## 1. Harm-detector validation (deterministic, runs everywhere)")
    lines.append("")
    if inst:
        lines.append(f"The deployed output guardrail reproduces the corpus's expected labels on "
                     f"**{inst.get('correct')}/{inst.get('total')}** rows "
                     f"(accuracy **{_pct(inst.get('accuracy'))}**). Safety-critical directions: "
                     f"**block recall {_pct(inst.get('block_recall'))}** (must-refuse rows actually "
                     f"blocked), **control false-block {_pct(inst.get('control_false_block_rate'))}** "
                     f"(benign rows wrongly blocked).")
        lines.append("")
        lines.append("| Category | Rows | Correct | Accuracy |")
        lines.append("|---|---|---|---|")
        for cat, d in sorted(inst.get("by_category", {}).items()):
            acc = d["correct"] / d["n"] if d["n"] else None
            lines.append(f"| {cat} | {d['n']} | {d['correct']} | {_pct(acc)} |")
        mism = inst.get("mismatches", [])
        lines.append("")
        if mism:
            lines.append(f"**{len(mism)} mismatch(es):** " +
                         ", ".join(f"`{m['id']}` (exp {m['expected']}, got {m['got']})" for m in mism))
        else:
            lines.append("**No mismatches** — the harm detector is calibrated on this corpus.")
    else:
        lines.append("_Instrument validation was skipped._")
    lines.append("")

    # ── 2. Per-condition harm ─────────────────────────────────────────────────
    lines.append("## 2. Per-condition red-team harm")
    lines.append("")
    lines.append("| Condition | Persona | Status | Attacks | Harm rate | False-refusal (proxy) | Source |")
    lines.append("|---|---|---|---|---|---|---|")
    for cid in ["C0", "C1", "C2", "C3", "C4"]:
        cond = conditions.get(cid)
        if not cond:
            continue
        label = CONDITION_LABELS.get(cid, cid)
        persona = cond.get("persona", "—")
        if cond.get("status") == "ok":
            src = cond.get("source", "—")
            model = cond.get("model")
            if model:
                src = f"{src} · `{model}`"
                if cond.get("adapter"):
                    src += f" + `{cond['adapter']}`"
            lines.append(f"| {label} | {persona} | ok | {cond.get('n_attacks', '—')} | "
                         f"{_pct(cond.get('harm_rate'))} | {_pct(cond.get('false_refusal_proxy'))} | "
                         f"{src} |")
        else:
            lines.append(f"| {label} | {persona} | **pending** | — | — | — | "
                         f"{cond.get('reason', 'pending')} |")
    lines.append("")

    # Per-category harm for any condition that actually ran.
    ran = {cid: c for cid, c in conditions.items() if c.get("status") == "ok" and c.get("by_category")}
    if ran:
        lines.append("### Per-category harm rate (conditions that ran)")
        lines.append("")
        for cid, cond in ran.items():
            lines.append(f"**{CONDITION_LABELS.get(cid, cid)}**")
            lines.append("")
            lines.append("| Category | Attacks | Harmful | Harm rate |")
            lines.append("|---|---|---|---|")
            for cat, d in sorted(cond["by_category"].items()):
                lines.append(f"| {cat} | {d['n']} | {d['harmful']} | {_pct(d.get('harm_rate'))} |")
            lines.append("")
    else:
        lines.append("_No condition produced generated outputs in this run — per-condition harm "
                     "rates are pending model-generation infrastructure (see status column)._")
        lines.append("")

    # ── 3. No-regression gate ─────────────────────────────────────────────────
    lines.append("## 3. No-regression vs. unaligned baseline")
    lines.append("")
    verdict = reg.get("verdict", "not_evaluable")
    badge = {"pass": "✅ PASS", "FAIL": "❌ FAIL", "not_evaluable": "⏳ NOT EVALUABLE"}.get(verdict, verdict)
    lines.append(f"Baseline: **{reg.get('baseline', '?')}** "
                 f"(harm rate {_pct(reg.get('baseline_harm_rate'))}), "
                 f"tolerance {_pct(reg.get('tolerance'))}. Verdict: **{badge}**.")
    lines.append("")
    if meta.get("api_baseline"):
        lines.append("> **Baseline note.** The baseline was run as a *neutral-prompt API baseline* "
                     "on the same model the shaped condition uses (`--api-baseline`): it isolates the "
                     "persona-**prompt** effect (neutral prompt vs. persona prompt, same model, same "
                     "decoding). It is **not** the true unaligned base-model checkpoint — a fine-tuned "
                     "condition (C2-C4) must still be gated against that checkpoint, not this proxy.")
        lines.append("")
    if reg.get("results"):
        lines.append("| Condition | Harm rate | vs. baseline |")
        lines.append("|---|---|---|")
        for cid, r in reg["results"].items():
            lines.append(f"| {CONDITION_LABELS.get(cid, cid)} | {_pct(r.get('harm_rate'))} | {r.get('status')} |")
        lines.append("")
    if verdict == "not_evaluable":
        lines.append("> The gate needs the baseline **and** at least one shaped condition to have "
                     "generated data. Provide `LLM_API_KEY` (for C1) or a GPU node with the adapters "
                     "(for C0/C2/C3/C4), then re-run `safety_eval.py`.")
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render the C4.3 safety report")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run safety_eval.py first to generate results.")
        sys.exit(1)

    results = _load(input_path)
    md = render_markdown(results)
    md_path = Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")
    print(f"Safety report written to: {md_path}")
    print("\n--- Preview ---")
    print(md)


if __name__ == "__main__":
    main()
