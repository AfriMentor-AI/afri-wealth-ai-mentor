"""Tests for the C5.1 human-eval aggregator — fully offline."""
from __future__ import annotations

import csv

from evaluation.human_eval_aggregate import aggregate, load_rater_csv

KEY = {"S001": "C1", "S002": "C1", "S003": "C2"}


def _write_rater_csv(tmp_path, name: str, rows: list[dict]):
    path = tmp_path / name
    fieldnames = ["sample_id", "user_message", "response", "persona_adherence",
                  "cultural_fluency", "anti_dependency", "financial_accuracy",
                  "urgency", "overall_quality", "notes"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({**dict.fromkeys(fieldnames, ""), **row})
    return path


def test_load_rater_csv_unblinds_and_skips_unscored_rows(tmp_path):
    path = _write_rater_csv(tmp_path, "rater1.csv", [
        {"sample_id": "S001", "overall_quality": "4"},
        {"sample_id": "S002"},  # left blank — rater skipped it
    ])
    rows = load_rater_csv(path, KEY)
    assert len(rows) == 1
    assert rows[0]["condition"] == "C1"
    assert rows[0]["overall_quality"] == 4.0


def test_load_rater_csv_ignores_unknown_sample_ids(tmp_path):
    path = _write_rater_csv(tmp_path, "rater1.csv", [
        {"sample_id": "S999", "overall_quality": "3"},
    ])
    assert load_rater_csv(path, KEY) == []


def test_aggregate_computes_per_condition_means():
    rows = [
        {"sample_id": "S001", "condition": "C1", "rater_file": "r1.csv",
         "overall_quality": 4.0, "persona_adherence": 0.8, "cultural_fluency": None,
         "anti_dependency": None, "financial_accuracy": None, "urgency": None},
        {"sample_id": "S001", "condition": "C1", "rater_file": "r2.csv",
         "overall_quality": 2.0, "persona_adherence": 0.6, "cultural_fluency": None,
         "anti_dependency": None, "financial_accuracy": None, "urgency": None},
        {"sample_id": "S003", "condition": "C2", "rater_file": "r1.csv",
         "overall_quality": 5.0, "persona_adherence": 0.9, "cultural_fluency": None,
         "anti_dependency": None, "financial_accuracy": None, "urgency": None},
    ]
    results = aggregate(rows)

    assert results["conditions"]["C1"]["n_ratings"] == 2
    assert results["conditions"]["C1"]["n_raters"] == 2
    assert results["conditions"]["C1"]["aggregate"]["overall_quality"] == 3.0
    assert results["conditions"]["C1"]["aggregate"]["persona_adherence"] == 0.7
    assert results["conditions"]["C2"]["n_ratings"] == 1


def test_aggregate_flags_disagreement_above_threshold():
    rows = [
        {"sample_id": "S001", "condition": "C1", "rater_file": "r1.csv",
         "overall_quality": 5.0, **{k: None for k in
             ("persona_adherence", "cultural_fluency", "anti_dependency",
              "financial_accuracy", "urgency")}},
        {"sample_id": "S001", "condition": "C1", "rater_file": "r2.csv",
         "overall_quality": 1.0, **{k: None for k in
             ("persona_adherence", "cultural_fluency", "anti_dependency",
              "financial_accuracy", "urgency")}},
    ]
    results = aggregate(rows)
    assert len(results["flagged_disagreements"]) == 1
    assert results["flagged_disagreements"][0]["sample_id"] == "S001"
    assert results["flagged_disagreements"][0]["spread"] == 4.0


def test_aggregate_does_not_flag_small_disagreement():
    rows = [
        {"sample_id": "S001", "condition": "C1", "rater_file": "r1.csv",
         "overall_quality": 4.0, **{k: None for k in
             ("persona_adherence", "cultural_fluency", "anti_dependency",
              "financial_accuracy", "urgency")}},
        {"sample_id": "S001", "condition": "C1", "rater_file": "r2.csv",
         "overall_quality": 3.0, **{k: None for k in
             ("persona_adherence", "cultural_fluency", "anti_dependency",
              "financial_accuracy", "urgency")}},
    ]
    results = aggregate(rows)
    assert results["flagged_disagreements"] == []
