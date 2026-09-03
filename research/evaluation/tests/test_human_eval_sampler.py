"""Tests for the C5.1 human-eval blinded-packet sampler — fully offline."""
from __future__ import annotations

import csv
import json

from evaluation.human_eval_sampler import build_packet, collect_ratable_rows, write_packet

SAMPLE_COMPARATIVE_RESULTS = {
    "conditions": {
        "C1": {
            "aggregate": {"source": "live_groq"},
            "rows": [
                {"user_message": "How do I price my goods?", "response": "Start with cost + margin..."},
                {"user_message": "Should I take a loan?", "response": "Depends on the interest rate..."},
            ],
        },
        "C2": {
            "aggregate": {"source": "recorded_kaggle_run"},
            "rows": [],  # recorded, not live — no generated text to show a rater
        },
        "C3": {
            "aggregate": {"source": "estimated_dpo_extrapolation"},
            "rows": [],  # estimated — never ran, nothing to rate
        },
    }
}


def test_collect_ratable_rows_only_includes_rows_with_response_text():
    ratable = collect_ratable_rows(SAMPLE_COMPARATIVE_RESULTS)
    assert len(ratable) == 2
    assert all(r["condition"] == "C1" for r in ratable)


def test_collect_ratable_rows_skips_rows_missing_response():
    results = {"conditions": {"C1": {"rows": [{"user_message": "x", "response": ""}]}}}
    assert collect_ratable_rows(results) == []


def test_build_packet_blinds_condition_and_is_deterministic_given_seed():
    ratable = collect_ratable_rows(SAMPLE_COMPARATIVE_RESULTS)
    packet_rows, key = build_packet(ratable, seed=1)

    assert len(packet_rows) == 2
    assert len(key) == 2
    for row in packet_rows:
        assert "condition" not in row  # raters never see the condition
        assert key[row["sample_id"]] == "C1"

    # Same seed -> same assignment.
    packet_rows2, key2 = build_packet(ratable, seed=1)
    assert [r["sample_id"] for r in packet_rows] == [r["sample_id"] for r in packet_rows2]
    assert key == key2


def test_build_packet_includes_blank_rubric_columns():
    ratable = collect_ratable_rows(SAMPLE_COMPARATIVE_RESULTS)
    packet_rows, _ = build_packet(ratable, seed=1)
    row = packet_rows[0]
    for col in ("persona_adherence", "cultural_fluency", "anti_dependency",
                "financial_accuracy", "urgency", "overall_quality", "notes"):
        assert row[col] == ""


def test_write_packet_produces_matching_csv_and_key(tmp_path):
    ratable = collect_ratable_rows(SAMPLE_COMPARATIVE_RESULTS)
    packet_rows, key = build_packet(ratable, seed=1)
    packet_out = tmp_path / "packet.csv"
    key_out = tmp_path / "key.json"

    write_packet(packet_rows, key, packet_out, key_out)

    with open(packet_out, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert {r["sample_id"] for r in rows} == set(json.loads(key_out.read_text()).keys())
