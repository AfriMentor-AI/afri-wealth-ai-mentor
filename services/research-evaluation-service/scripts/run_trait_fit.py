#!/usr/bin/env python3
"""
C2.3 — Trait-level fit metric end-to-end.
Administers the BFI/TRAIT probe set, scores against the CHIOMA target profile,
and stores the report in Postgres as a baseline experiment run.

Usage:
    python scripts/run_trait_fit.py
    python scripts/run_trait_fit.py --model-id baseline-lexical --name my-run
    python scripts/run_trait_fit.py --out report.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from the service root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal, engine
from app.llm import (
    LLMConfig,
    ProbeAdministrationError,
    administer_probes,
    fetch_system_prompt,
)
from app.metrics.profile import load_profile
from app.metrics.report import score_dialogue
from app.metrics.schemas import Dialogue, ProbeResponse, Speaker, Turn
from app.metrics.trait_fit import score_probe_traits
from app.models.audit import Base, ExperimentRun, ExperimentStatus, TraitFitReport

DEFAULT_PROBE_PATH = Path(__file__).resolve().parents[1] / "data" / "toy_probes.json"
DEFAULT_DIALOGUE_DIR = Path(__file__).resolve().parents[1] / "data" / "toy_dialogues"


def load_probes(path: Path) -> list[ProbeResponse]:
    """Load probe instrument (questions + metadata) from JSON.

    When ``toy_probes.json`` has pre-written answers, those are read but never
    scored — :func:`run_experiment` replaces them with the model's own answers
    before scoring, so the baseline actually measures the persona-prompted model.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [ProbeResponse(**r) for r in raw]


def load_dialogues(directory: Path) -> list[Dialogue]:
    dialogues = []
    for f in sorted(directory.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        dialogues.append(Dialogue(**data))
    return dialogues


def run_experiment(
    model_id: str = "baseline-lexical-v0",
    name: str | None = None,
    probe_path: Path = DEFAULT_PROBE_PATH,
    dialogue_dir: Path = DEFAULT_DIALOGUE_DIR,
    profile_path: Path | None = None,
    out_path: Path | None = None,
    live: bool | None = None,
    llm_config: LLMConfig | None = None,
) -> dict:
    """Run the full trait-fit evaluation and store results.

    ``live`` controls where probe answers come from:

    * ``True``  — administer the probe set to the persona-prompted baseline model.
      This is the C2.3 measurement.
    * ``False`` — score the fixture answers in ``probe_path``. Plumbing check only;
      the resulting numbers describe the fixtures, not any model.
    * ``None``  — auto: live when ``LLM_API_KEY`` is set, fixtures otherwise.

    The mode is recorded on the run (``model_id`` is suffixed for fixture runs) so a
    stored report can never be mistaken for a real baseline.

    ``profile_path`` defaults (via :func:`load_profile`) to the CHIOMA target
    profile. Card C4.4 passes KWAME's profile here to run the identical scoring
    code — ``score_probe_traits`` / ``score_dialogue`` — against a second persona;
    :func:`~app.llm.fetch_system_prompt` then fetches that persona's own prompt
    from persona-prompt-service, keyed off ``profile.profile_id``.
    """
    Base.metadata.create_all(bind=engine)
    profile = load_profile(profile_path)

    config = llm_config or LLMConfig.from_env()
    if live is None:
        live = config.is_live
    if live and not config.is_live:
        raise ProbeAdministrationError(
            "--live requested but LLM_API_KEY is not set; export it or pass --fixtures"
        )

    # A fixture run is not a measurement of any model. Tag it in the stored
    # identifier rather than only in a log line nobody reads later.
    effective_model_id = model_id if live else f"{model_id}+fixture-answers"
    run_name = name or f"{effective_model_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"

    system_prompt, prompt_provenance = ("", "not-applicable")
    if live:
        system_prompt, prompt_provenance = fetch_system_prompt(profile)

    db = SessionLocal()
    run = ExperimentRun(
        name=run_name,
        model_id=effective_model_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        scorer="LexicalScorer",
        status=ExperimentStatus.running,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        probe_set = load_probes(probe_path)
        dialogues = load_dialogues(dialogue_dir)
        run.probe_count = len(probe_set)

        # Administer the probe set to the model under evaluation, replacing the
        # fixture answers. This is the step that makes the report a baseline.
        administered = None
        if live:
            def _progress(index: int, total: int, probe_id: str) -> None:
                print(f"  [{index}/{total}] administering {probe_id}…", flush=True)

            print(f"Administering {len(probe_set)} probes to {config.model}")
            administered = administer_probes(
                probe_set, system_prompt, config=config, on_progress=_progress
            )
            probes = [p.to_response() for p in administered]
        else:
            print("No LLM_API_KEY — scoring fixture answers (not a model baseline)")
            probes = probe_set

        # Score probe-based trait fit
        probe_result = score_probe_traits(probes, profile=profile)
        probe_warnings: list[str] = []
        if not live:
            probe_warnings.append(
                "answers are fixtures, not model output — not a valid model baseline"
            )
        if administered:
            truncated = [p.probe_id for p in administered if p.truncated]
            if truncated:
                probe_warnings.append(
                    "answers truncated at token limit (trait estimates biased low): "
                    + ", ".join(truncated)
                )
        probe_report = TraitFitReport(
            run_id=run.id,
            source="probes",
            cosine_similarity=probe_result.cosine_similarity,
            mean_absolute_error=probe_result.mean_absolute_error,
            worst_trait=probe_result.worst_trait.trait if probe_result.worst_trait else None,
            per_trait_json=json.dumps([t.model_dump() for t in probe_result.per_trait]),
            warnings_json=json.dumps(probe_warnings),
        )
        db.add(probe_report)

        # Score dialogue-based trait fit and consistency
        dialogue_reports = []
        for dialogue in dialogues:
            eval_report = score_dialogue(dialogue, profile=profile)
            d_report = TraitFitReport(
                run_id=run.id,
                source="dialogue",
                cosine_similarity=eval_report.trait_fit.cosine_similarity,
                mean_absolute_error=eval_report.trait_fit.mean_absolute_error,
                composite_score=eval_report.composite_score,
                worst_trait=(
                    eval_report.trait_fit.worst_trait.trait
                    if eval_report.trait_fit.worst_trait else None
                ),
                per_trait_json=json.dumps([t.model_dump() for t in eval_report.trait_fit.per_trait]),
                warnings_json=json.dumps(eval_report.warnings),
            )
            db.add(d_report)
            dialogue_reports.append(eval_report)

        run.status = ExperimentStatus.completed
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        result = {
            "run_id": run.id,
            "run_name": run.name,
            "model_id": effective_model_id,
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            # Provenance: without these a stored cosine is uninterpretable — you
            # cannot tell which model, prompt, or answer source produced it.
            "answer_source": "model" if live else "fixtures",
            "llm_model": config.model if live else None,
            "llm_temperature": config.temperature if live else None,
            "system_prompt_source": prompt_provenance,
            "probe_trait_fit": {
                "cosine_similarity": probe_result.cosine_similarity,
                "mean_absolute_error": probe_result.mean_absolute_error,
                "worst_trait": probe_result.worst_trait.trait if probe_result.worst_trait else None,
                "per_trait": [t.model_dump() for t in probe_result.per_trait],
                "warnings": probe_warnings,
            },
            "administered_probes": [
                {
                    "probe_id": p.probe_id,
                    "trait": p.trait,
                    "question": p.question,
                    "answer": p.answer,
                    "reverse_scored": p.reverse_scored,
                    "latency_ms": p.latency_ms,
                    "truncated": p.truncated,
                }
                for p in (administered or [])
            ],
            "dialogue_reports": [
                {
                    "dialogue_id": r.dialogue_id,
                    "composite_score": r.composite_score,
                    "trait_cosine": r.trait_fit.cosine_similarity,
                    "consistency_aggregate": r.consistency.aggregate,
                    "warnings": r.warnings,
                }
                for r in dialogue_reports
            ],
            "status": "completed",
        }

        if out_path:
            out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"Report written to {out_path}")

        return result

    except Exception as exc:
        run.status = ExperimentStatus.failed
        run.error_message = str(exc)[:500]
        db.commit()
        raise
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run C2.3 trait-fit baseline experiment",
        epilog=(
            "By default, probe answers come from the live model (requires LLM_API_KEY). "
            "Pass --fixtures to score the canned answers in toy_probes.json instead "
            "(plumbing check; not a valid model baseline)."
        ),
    )
    parser.add_argument("--model-id", default="baseline-lexical-v0")
    parser.add_argument("--name", default=None, help="Unique run name; auto-generated if omitted")
    parser.add_argument("--out", type=Path, default=None, help="Write JSON report to this path")
    parser.add_argument(
        "--profile-path",
        type=Path,
        default=None,
        help=(
            "Target profile JSON to score against (card C4.4). Defaults to the "
            "CHIOMA profile; pass persona-prompt-service/data/kwame_profile.v1.json "
            "to run this same suite against KWAME."
        ),
    )
    parser.add_argument(
        "--dialogue-dir",
        type=Path,
        default=DEFAULT_DIALOGUE_DIR,
        help="Directory of toy dialogue JSON files to score (default: CHIOMA's).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--live",
        action="store_true",
        default=None,
        help="Force live model call (fails if LLM_API_KEY unset)",
    )
    mode.add_argument(
        "--fixtures",
        action="store_true",
        default=None,
        help="Score fixture answers only (no model call; not a baseline)",
    )
    args = parser.parse_args(argv)

    live_arg = True if args.live else (False if args.fixtures else None)

    try:
        result = run_experiment(
            model_id=args.model_id,
            name=args.name,
            dialogue_dir=args.dialogue_dir,
            profile_path=args.profile_path,
            out_path=args.out,
            live=live_arg,
        )
    except ProbeAdministrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Run ID      : {result['run_id']}")
    print(f"Model       : {result['model_id']}")
    print(f"Profile     : {result['profile_id']} {result['profile_version']}")
    print(f"Answer src  : {result['answer_source']}")
    if result["answer_source"] == "model":
        print(f"LLM model   : {result['llm_model']}")
        print(f"Temperature : {result['llm_temperature']}")
        print(f"Prompt src  : {result['system_prompt_source']}")
    print(f"Probe cosine: {result['probe_trait_fit']['cosine_similarity']:.4f}")
    print(f"Probe MAE   : {result['probe_trait_fit']['mean_absolute_error']:.4f}")
    if result["probe_trait_fit"].get("warnings"):
        for warning in result["probe_trait_fit"]["warnings"]:
            print(f"  ! {warning}")
    print(f"Dialogues   : {len(result['dialogue_reports'])}")
    for d in result["dialogue_reports"]:
        print(
            f"  {d['dialogue_id']}: composite={d['composite_score']:.3f} "
            f"consistency={d['consistency_aggregate']:.3f}"
        )
    print(f"Status      : {result['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
