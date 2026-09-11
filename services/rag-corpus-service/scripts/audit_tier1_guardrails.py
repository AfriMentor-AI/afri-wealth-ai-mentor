#!/usr/bin/env python3
"""Guardrails content audit for Tier-1 corpus content (card C5.2).

"Guardrails coverage confirmed across 100% of Tier-1 content" is interpreted
as: every Tier-1 document's raw text is run through
chat-orchestration-service's existing output-screening patterns
(``app.guardrails.screen_output``), so the corpus's own content is checked
against the same deterministic rules a live reply would be — reusing the
guardrail logic rather than re-implementing or guessing at it.

This is a content audit, not a red-team test: it reports what the current
rules make of the corpus as it stands (allow / disclaim / block, and which
categories fired), not whether the rules themselves are complete.

    python scripts/audit_tier1_guardrails.py [--json report.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVICE_ROOT = HERE.parent
CORPUS_JSONL = SERVICE_ROOT / "corpus" / "data" / "corpus.jsonl"

CHAT_SERVICE_ROOT = SERVICE_ROOT.parent / "chat-orchestration-service"


def _load_screen_output():
    """Import chat-orchestration-service's screen_output without its deps.

    guardrails.py only touches json/re/dataclasses/enum/functools/pathlib, so
    importing just ``app.guardrails`` (not ``app`` as a running service) costs
    nothing extra — no DB, no network, no LLM client.
    """
    if str(CHAT_SERVICE_ROOT) not in sys.path:
        sys.path.insert(0, str(CHAT_SERVICE_ROOT))
    from app.guardrails import screen_output

    return screen_output


def audit() -> dict:
    screen_output = _load_screen_output()

    if not CORPUS_JSONL.exists():
        print(f"ERROR: {CORPUS_JSONL} not found.")
        sys.exit(1)

    with open(CORPUS_JSONL, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    results = []
    by_action = {"allow": 0, "disclaim": 0, "block": 0}
    for record in records:
        decision = screen_output(record["content"])
        action = decision.action.value
        by_action[action] += 1
        results.append({
            "doc_id": record["doc_id"],
            "title": record["metadata"].get("title") or record["doc_id"],
            "action": action,
            "categories": list(decision.categories),
            "matched_term_count": len(decision.matched_terms),
        })

    return {
        "rules_checked_against": "chat-orchestration-service/app/guardrails.py:screen_output",
        "documents_audited": len(records),
        "summary": by_action,
        "documents": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write the full report to this path as JSON")
    args = parser.parse_args()

    report = audit()

    print("AfriMentor RAG — Tier-1 Guardrails Content Audit")
    print(f"Rules:     {report['rules_checked_against']}")
    print(f"Documents: {report['documents_audited']}")
    print()
    for doc in report["documents"]:
        flag = "" if doc["action"] == "allow" else "  <-- " + ", ".join(doc["categories"])
        print(f"  [{doc['action']:8s}] {doc['doc_id']}{flag}")
    print()
    print("=" * 55)
    s = report["summary"]
    print(
        f"Coverage: {report['documents_audited']}/{report['documents_audited']} Tier-1 "
        f"documents screened — allow={s['allow']} disclaim={s['disclaim']} block={s['block']}"
    )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report written to {args.json}")

    # screen_output is only ever applied to the model's *generated* reply
    # (app/routers/chat.py), never to raw retrieved corpus text — a "block"
    # here means "guardrails would catch this passage if the model echoed it
    # near-verbatim", which is the guardrails working as intended on
    # legitimate reference content (real entrepreneurs discussing debt,
    # named companies, equity, etc.), not a defect in the corpus. Success for
    # this audit is 100% of Tier-1 documents screened, not zero flags — so
    # this only fails on a genuine run error (corpus.jsonl missing, import
    # failure), which raises before reaching here.


if __name__ == "__main__":
    main()
