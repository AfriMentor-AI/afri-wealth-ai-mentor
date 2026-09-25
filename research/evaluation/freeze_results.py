"""Freeze evaluation results as the paper's canonical dataset (card C5.1).

Snapshots the current ``comparative_eval.py`` (and, if present, ``safety_eval.py``)
JSON outputs into an immutable, versioned directory under
``evaluation/results/canonical/``, with a manifest recording git provenance and
— critically — whether every condition's numbers are genuinely measured or a
literature-extrapolated placeholder.

This tool never upgrades a result's honesty: it reads the ``source`` field
``comparative_eval.py`` already stamps on every condition (``live_*`` / a named
``recorded_*`` run = real measurement, ``estimated_*`` = literature
extrapolation — see that module and ``results_table.py``'s footnote-marker
convention) and reports what it finds. A freeze is only ``PUBLICATION_READY``
when every condition is real; anything else is ``PARTIAL_CONTAINS_ESTIMATES``
and the manifest says so loudly, because "final results" for a paper cannot
include estimated placeholders presented as measured ones.

Usage:
    python research/evaluation/freeze_results.py --version v1
    python research/evaluation/freeze_results.py --version v1 --tag   # also git tag (local only)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _RESEARCH_ROOT.parent
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

RESULTS_DIR = _RESEARCH_ROOT / "evaluation" / "results"
CANONICAL_DIR = RESULTS_DIR / "canonical"

# Every condition source comparative_eval.py can currently stamp, and how each
# classifies. Unrecognised sources are treated as non-live (fail closed).
_LIVE_PREFIXES = ("live_",)
_REAL_RECORDED_PREFIXES = ("recorded_",)  # a genuine past run, not extrapolated

DEFAULT_INPUTS = {
    "comparative": RESULTS_DIR / "comparative_results.json",
    "safety": RESULTS_DIR / "safety_results.json",
    "human_eval": RESULTS_DIR / "human_eval_results.json",
}


def _display_path(path: Path) -> str:
    """Path relative to the repo root when possible, else the path as given.

    Falls back rather than raising so a caller passing a path outside
    ``_REPO_ROOT`` (e.g. a test fixture under ``tmp_path``) still gets a
    usable manifest instead of a crash.
    """
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return None


def _condition_provenance(comparative_results: dict) -> dict[str, dict]:
    """Per-condition {source, is_real} for every condition in a comparative_eval.py output."""
    provenance: dict[str, dict] = {}
    for cond_id, cond in comparative_results.get("conditions", {}).items():
        source = cond.get("aggregate", {}).get("source", "unknown")
        is_real = source.startswith(_LIVE_PREFIXES) or source.startswith(_REAL_RECORDED_PREFIXES)
        provenance[cond_id] = {"source": source, "is_real": is_real}
    return provenance


def _human_eval_provenance(human_results: dict, real_conditions: set[str]) -> dict[str, dict]:
    """Per-condition human-rating status, for conditions with real automatic data.

    A condition that never ran live (no ratable response text exists — see
    human_eval_rubric.md) is out of scope for human rating entirely, not a gap.
    """
    conditions = human_results.get("conditions", {})
    provenance: dict[str, dict] = {}
    for cond_id in real_conditions:
        cond = conditions.get(cond_id)
        n_ratings = cond.get("n_ratings", 0) if cond else 0
        provenance[cond_id] = {
            "n_ratings": n_ratings,
            "status": "rated" if n_ratings > 0 else "pending_human_ratings",
        }
    return provenance


def build_manifest(
    version: str,
    inputs: dict[str, Path] = DEFAULT_INPUTS,
) -> dict:
    """Assemble the freeze manifest without writing anything (pure, testable)."""
    input_records = []
    provenance: dict[str, dict] = {}
    human_eval_provenance: dict[str, dict] = {}
    human_eval_present = False

    for name, path in inputs.items():
        exists = path.exists()
        input_records.append({
            "name": name,
            "path": _display_path(path) if exists else str(path),
            "exists": exists,
            "sha256": _sha256(path),
        })
        if name == "comparative" and exists:
            provenance = _condition_provenance(json.loads(path.read_text(encoding="utf-8")))
        if name == "human_eval" and exists:
            human_eval_present = True

    real_conditions = {c for c, v in provenance.items() if v["is_real"]}
    estimated_conditions = [c for c, v in provenance.items() if not v["is_real"]]

    if human_eval_present:
        human_results = json.loads(inputs["human_eval"].read_text(encoding="utf-8"))
        human_eval_provenance = _human_eval_provenance(human_results, real_conditions)
    else:
        human_eval_provenance = {
            c: {"n_ratings": 0, "status": "pending_human_ratings"} for c in real_conditions
        }

    pending_human = [
        c for c, v in human_eval_provenance.items() if v["status"] == "pending_human_ratings"
    ]

    if not provenance:
        status = "NO_COMPARATIVE_RESULTS"
    elif estimated_conditions and pending_human:
        status = "PARTIAL_ESTIMATES_AND_MISSING_HUMAN_EVAL"
    elif estimated_conditions:
        status = "PARTIAL_CONTAINS_ESTIMATES"
    elif pending_human:
        status = "PARTIAL_MISSING_HUMAN_EVAL"
    else:
        status = "PUBLICATION_READY"

    status_notes = {
        "PUBLICATION_READY": (
            "Every condition is real (live-scored or a recorded past run) and has "
            "human ratings on file — safe to cite as final results."
        ),
        "PARTIAL_CONTAINS_ESTIMATES": (
            "One or more conditions are literature-extrapolated estimates, not "
            "measurements. This freeze documents the current state for "
            "reproducibility but MUST NOT be cited as final paper results until "
            "re-frozen with every condition real."
        ),
        "PARTIAL_MISSING_HUMAN_EVAL": (
            "All conditions are real, but one or more has no human ratings on "
            "file yet (see human_eval_rubric.md). Automatic metrics alone are "
            "not the 'automatic + human' evaluation this card requires."
        ),
        "PARTIAL_ESTIMATES_AND_MISSING_HUMAN_EVAL": (
            "Some conditions are estimated placeholders AND human ratings are "
            "outstanding for the real conditions. Not close to publication-ready."
        ),
        "NO_COMPARATIVE_RESULTS": "No comparative_results.json found — run comparative_eval.py first.",
    }

    return {
        "version": version,
        "frozen_at": datetime.now(tz=UTC).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "inputs": input_records,
        "condition_provenance": provenance,
        "estimated_conditions": estimated_conditions,
        "human_eval_provenance": human_eval_provenance,
        "pending_human_eval_conditions": pending_human,
        "status": status,
        "status_note": status_notes[status],
    }


def freeze(version: str, inputs: dict[str, Path] = DEFAULT_INPUTS, *, tag: bool = False) -> dict:
    manifest = build_manifest(version, inputs)

    version_dir = CANONICAL_DIR / version
    if version_dir.exists():
        raise FileExistsError(
            f"{version_dir} already exists — freezes are immutable, use a new --version"
        )
    version_dir.mkdir(parents=True)

    for record in manifest["inputs"]:
        if record["exists"]:
            recorded_path = Path(record["path"])
            source = recorded_path if recorded_path.is_absolute() else _REPO_ROOT / recorded_path
            shutil.copy2(source, version_dir / recorded_path.name)

    manifest_path = version_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if tag:
        tag_name = f"eval-freeze-{version}"
        subprocess.run(
            ["git", "tag", "-a", tag_name, "-m",
             f"C5.1 evaluation freeze {version}: status={manifest['status']}"],
            cwd=_REPO_ROOT, check=True,
        )
        manifest["git_tag"] = tag_name

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze evaluation results (card C5.1)")
    parser.add_argument("--version", required=True, help="Freeze version label, e.g. v1")
    parser.add_argument("--comparative", default=None, help="comparative_eval.py output to freeze (default: results/comparative_results.json)")
    parser.add_argument("--human-eval", default=None, help="human_eval_aggregate.py output to freeze (default: results/human_eval_results.json)")
    parser.add_argument("--safety", default=None, help="safety_eval.py output to freeze")
    parser.add_argument("--tag", action="store_true",
                         help="Also create a local git tag eval-freeze-<version> (not pushed)")
    args = parser.parse_args()

    inputs = dict(DEFAULT_INPUTS)
    for name, val in (("comparative", args.comparative), ("human_eval", args.human_eval), ("safety", args.safety)):
        if val:
            inputs[name] = Path(val)
    manifest = freeze(args.version, inputs, tag=args.tag)

    print(f"\n=== Freeze {args.version}: {manifest['status']} ===")
    print(manifest["status_note"])
    for cond_id, prov in manifest["condition_provenance"].items():
        marker = "✓ real" if prov["is_real"] else "✗ ESTIMATED"
        print(f"  {cond_id}: {prov['source']}  [{marker}]")
    if manifest["human_eval_provenance"]:
        print("  Human eval:")
        for cond_id, prov in manifest["human_eval_provenance"].items():
            marker = f"✓ {prov['n_ratings']} ratings" if prov["status"] == "rated" else "✗ PENDING"
            print(f"    {cond_id}: [{marker}]")
    if manifest.get("git_tag"):
        print(f"\nTagged: {manifest['git_tag']} (local only — push explicitly if intended)")
    print(f"\nManifest: {CANONICAL_DIR / args.version / 'manifest.json'}")


if __name__ == "__main__":
    main()
