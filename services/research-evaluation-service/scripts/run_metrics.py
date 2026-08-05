#!/usr/bin/env python3
"""Run the personality-consistency metric suite v0 over toy dialogues (card C1.3).

Satisfies the C1.3 acceptance criterion: scoring scripts run on >= 3 toy dialogue
examples and output a numeric report.

Usage::

    python scripts/run_metrics.py                        # score bundled toy dialogues
    python scripts/run_metrics.py --format json          # machine-readable
    python scripts/run_metrics.py --out report.json      # write to file
    python scripts/run_metrics.py --dialogues path/ --probes probes.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.metrics.profile import load_profile  # noqa: E402
from app.metrics.report import score_dialogue, score_dialogues  # noqa: E402
from app.metrics.schemas import Dialogue, ProbeResponse  # noqa: E402
from app.metrics.trait_fit import score_probe_traits  # noqa: E402

DEFAULT_DIALOGUE_DIR = SERVICE_ROOT / "data" / "toy_dialogues"
DEFAULT_PROBE_PATH = SERVICE_ROOT / "data" / "toy_probes.json"


def load_dialogues(directory: Path) -> list[Dialogue]:
    """Load every ``*.json`` in ``directory`` as a Dialogue, sorted by filename."""
    if not directory.is_dir():
        raise NotADirectoryError(f"dialogue directory not found: {directory}")
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"no .json dialogue files in {directory}")
    return [
        Dialogue.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in paths
    ]


def load_probes(path: Path) -> list[ProbeResponse]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ProbeResponse.model_validate(item) for item in data]


def _bar(value: float, width: int = 20) -> str:
    filled = max(0, min(width, round(value * width)))
    return "#" * filled + "." * (width - filled)


def render_text(bundle, probe_result=None) -> str:
    """Human-readable console report."""
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add("AfriMentor AI — Personality-Consistency Metric Suite v0 (card C1.3)")
    add("=" * 78)

    first = bundle.reports[0]
    add(f"Target profile : {first.profile_id} {first.profile_version}")
    add(f"Scoring backend: {first.scorer}")
    add(f"Dialogues      : {len(bundle.reports)}")
    add("")

    for report in bundle.reports:
        add("-" * 78)
        add(f"[{report.dialogue_id}]  composite {report.composite_score:.3f}  {_bar(report.composite_score)}")
        add("-" * 78)

        tf = report.trait_fit
        add(f"  Trait fit      cosine {tf.cosine_similarity:.4f}   MAE {tf.mean_absolute_error:.4f}")
        add(f"    {'trait':<22}{'target':>8}{'observed':>10}{'delta':>9}{'evid':>6}")
        for trait in tf.per_trait:
            add(
                f"    {trait.trait:<22}{trait.target_value:>8.2f}{trait.observed_value:>10.2f}"
                f"{trait.delta:>+9.2f}{trait.evidence_count:>6}"
            )
        worst = tf.worst_trait
        if worst is not None:
            add(f"    largest gap: {worst.trait} ({worst.delta:+.2f})")

        c = report.consistency
        add("")
        add(f"  Consistency    aggregate {c.aggregate:.4f}")
        add(f"    prompt-to-line  {c.prompt_to_line:.4f}  {_bar(c.prompt_to_line)}  (n={c.n_prompt_to_line})")
        add(f"    line-to-line    {c.line_to_line:.4f}  {_bar(c.line_to_line)}  (n={c.n_line_to_line})")
        add(f"    qa-consistency  {c.qa_consistency:.4f}  {_bar(c.qa_consistency)}  (n={c.n_qa_pairs})")

        if report.warnings:
            add("")
            for warning in report.warnings:
                add(f"  ! {warning}")
        add("")

    add("=" * 78)
    add("CORPUS AGGREGATE")
    add(f"  mean composite    {bundle.mean_composite:.4f}")
    add(f"  mean trait cosine {bundle.mean_trait_cosine:.4f}")
    add(f"  mean consistency  {bundle.mean_consistency:.4f}")

    if probe_result is not None:
        add("")
        add("PROBE-BASED TRAIT FIT (BFI/TRAIT-style, administered separately)")
        add(f"  cosine {probe_result.cosine_similarity:.4f}   MAE {probe_result.mean_absolute_error:.4f}")
        for trait in probe_result.per_trait:
            add(
                f"    {trait.trait:<22}{trait.target_value:>8.2f}{trait.observed_value:>10.2f}"
                f"{trait.delta:>+9.2f}"
            )
        add("  note: probe-based and dialogue-based estimates are reported separately")
        add("        by design — self-report and behaviour diverge (Han et al. 2025).")
    add("=" * 78)
    return "\n".join(lines)


def render_json(bundle, probe_result=None) -> str:
    payload = {
        "suite_version": "v0",
        "card": "C1.3",
        "dialogue_count": len(bundle.reports),
        "aggregate": {
            "mean_composite": bundle.mean_composite,
            "mean_trait_cosine": bundle.mean_trait_cosine,
            "mean_consistency": bundle.mean_consistency,
        },
        "summary_rows": bundle.summary_rows(),
        "reports": [json.loads(r.model_dump_json()) for r in bundle.reports],
    }
    if probe_result is not None:
        payload["probe_trait_fit"] = json.loads(probe_result.model_dump_json())
    return json.dumps(payload, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dialogues", type=Path, default=DEFAULT_DIALOGUE_DIR)
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBE_PATH)
    parser.add_argument("--profile", type=Path, default=None, help="CHIOMA profile JSON")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--out", type=Path, default=None, help="write report to file")
    parser.add_argument("--no-probes", action="store_true")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    dialogues = load_dialogues(args.dialogues)
    bundle = score_dialogues(dialogues, profile=profile)

    probe_result = None
    if not args.no_probes and args.probes.is_file():
        probe_result = score_probe_traits(load_probes(args.probes), profile=profile)

    rendered = (
        render_json(bundle, probe_result)
        if args.format == "json"
        else render_text(bundle, probe_result)
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {args.format} report to {args.out}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
