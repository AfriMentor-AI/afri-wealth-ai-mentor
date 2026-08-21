"""Generate the comparative results table for the paper's Results section.

Reads the JSON output from ``comparative_eval.py`` and produces:
  1. A Markdown table (for quick review / docs)
  2. A LaTeX ``tabular`` block (for the paper)

Usage:
    python research/evaluation/results_table.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = _RESEARCH_ROOT / "evaluation" / "results" / "comparative_results.json"
DEFAULT_MD_OUT = _RESEARCH_ROOT / "evaluation" / "results" / "comparative_results.md"
DEFAULT_TEX_OUT = _RESEARCH_ROOT / "afrimentor-Research-paper" / "sections" / "results_table.tex"

METRIC_LABELS = {
    "persona_adherence": "Persona Adherence",
    "cultural_fluency": "Cultural Fluency",
    "anti_dependency": "Anti-Dependency",
    "financial_accuracy": "Financial Accuracy",
    "urgency": "Urgency",
    "rouge_l": "ROUGE-L",
    "bert_score_f1": "BERTScore F1",
    "composite_score": "Composite",
}

CONDITION_LABELS = {
    "C1": "C1: Baseline Prompting",
    "C2": "C2: Supervised Fine-Tuning",
    "C3": "C3: Contrastive Learning (DPO)",
    "C4": "C4: RLHF / Preference Opt.",
}

# Source → footnote marker mapping for table provenance transparency
SOURCE_MARKERS: dict[str, str] = {
    "estimated_dpo_extrapolation": "†",
    "estimated_rlhf_extrapolation": "†",
    "simulated_groq_proxy": "‡",
}

FOOTNOTE_LEGEND = (
    "† Estimated from C2 baseline + literature-calibrated alignment gains "
    "(DPO: Rafailov et al., 2023; RLHF: Ouyang et al., 2022). "
    "To be replaced by live checkpoint scores after GPU training."
)


def _fmt(value, marker: str = "") -> str:
    if value is None:
        return "--"
    return f"{float(value):.3f}{marker}"



def _load_results(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_markdown(results: dict) -> str:
    lines = [
        "| Condition | Persona Adherence | Cultural Fluency | Anti-Dependency | "
        "Financial Accuracy | Urgency | ROUGE-L | BERTScore F1 | Composite | Source |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cond_id in ["C1", "C2", "C3", "C4"]:
        cond = results.get("conditions", {}).get(cond_id)
        if not cond:
            continue
        agg = cond.get("aggregate", {})
        label = CONDITION_LABELS.get(cond_id, cond_id)
        source = agg.get("source", "unknown")
        marker = SOURCE_MARKERS.get(source, "")
        values = [_fmt(agg.get(m), marker) for m in METRIC_LABELS.keys()]
        lines.append(f"| {label} | " + " | ".join(values) + f" | {source} |")
    if any(
        SOURCE_MARKERS.get(results.get("conditions", {}).get(c, {}).get("aggregate", {}).get("source", ""), "")
        for c in ["C1", "C2", "C3", "C4"]
    ):
        lines.append(f"\n_{FOOTNOTE_LEGEND}_")
    return "\n".join(lines) + "\n"


def render_latex(results: dict) -> str:
    lines = [
        "\\begin{table}[ht]",
        "\\centering",
        "\\caption{Comparative evaluation of the four alignment conditions "
        "across the shared metric suite. Scores are means over the held-out "
        "test set (\\texttt{sft\\_test.jsonl}). Composite is the weighted sum "
        "of the five rubric dimensions.}",
        "\\label{tab:comparative-results}",
        "\\small",
        "\\begin{tabular}{lcccccccc}",
        "\\toprule",
        "Condition & Persona & Cultural & Anti-Dep. & Financial & Urgency & "
        "ROUGE-L & BERTScore & Composite \\\\",
        "& Adherence & Fluency & & Accuracy & & & F1 & \\\\",
        "\\midrule",
    ]
    for cond_id in ["C1", "C2", "C3", "C4"]:
        cond = results.get("conditions", {}).get(cond_id)
        if not cond:
            continue
        agg = cond.get("aggregate", {})
        label = CONDITION_LABELS.get(cond_id, cond_id)
        source = agg.get("source", "unknown")
        marker = SOURCE_MARKERS.get(source, "")
        # Escape † for LaTeX as $\dagger$
        tex_marker = "$\\dagger$" if marker == "†" else ("$\\ddagger$" if marker == "‡" else "")
        values = [_fmt(agg.get(m), tex_marker) for m in METRIC_LABELS.keys()]
        lines.append(f"{label} & " + " & ".join(values) + " \\\\")
    has_estimated = any(
        SOURCE_MARKERS.get(results.get("conditions", {}).get(c, {}).get("aggregate", {}).get("source", ""), "")
        for c in ["C1", "C2", "C3", "C4"]
    )
    footnote_tex = (
        "\\footnotesize $\\dagger$ Estimated from C2 baseline + literature-calibrated "
        "alignment gains (DPO: Rafailov et al., 2023; RLHF: Ouyang et al., 2022). "
        "To be replaced by live checkpoint scores after GPU training."
    )
    lines += [
        "\\bottomrule",
        "\\end{tabular}",
    ]
    if has_estimated:
        lines.append(f"\\vspace{{2pt}}\\par {footnote_tex}")
    lines.append("\\end{table}")
    return "\n".join(lines) + "\n"



def main() -> None:
    parser = argparse.ArgumentParser(description="Generate comparative results table")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--tex-out", default=str(DEFAULT_TEX_OUT))
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run comparative_eval.py first to generate results.")
        sys.exit(1)

    results = _load_results(input_path)
    md = render_markdown(results)
    tex = render_latex(results)

    md_path = Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")

    tex_path = Path(args.tex_out)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tex, encoding="utf-8")

    print(f"Markdown table written to: {md_path}")
    print(f"LaTeX table written to:   {tex_path}")
    print("\n--- Markdown Preview ---")
    print(md)


if __name__ == "__main__":
    main()