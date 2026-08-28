# Mid-Pilot Quantitative Data Checkpoint — Card C4.5

## Overview

Pull all three of the pilot's required measures for both pilot arms at the
pilot's midpoint and hand the dataset to Grace for interim analysis. Extends the
O4.4 pilot-data export (`services/research-evaluation-service`) rather than
building a new pipeline:

- Adds a **study-arm** concept (Arm A / Arm B, per
  `docs/research/pilot-data-collection-plan-v0.md` §1) that did not exist
  anywhere in the codebase before this card, so the export can label and filter
  rows by which arm a participant was allocated to.
- Adds a **survey-score** concept (T0/T1, per pilot plan §6) so financial-
  knowledge and self-efficacy — both administered orally by the field team —
  can be recorded as computed scores and joined into the same export.
- Adds an `arm` filter and clarifies the existing `end_date` filter's use for a
  midpoint cut to `GET /api/v1/research/export/pilot-data.csv`.

## What this checkpoint delivers

The pilot plan (§5) specifies **three** required measures — all three are now
in the export:

| # | Measure | Source | In this export? |
| :--- | :--- | :--- | :---: |
| Engagement (§5.4/F4) | App telemetry — session length, message count (`SessionMetric`, card C3.5) | ✅ |
| Financial knowledge (§5.2) | Big-Three-adapted, administered **orally**, pre/post — scored 0–3, recorded via `SurveyScore` | ✅ |
| Financial self-efficacy (§5.3) | FSES-modified, administered **orally**, pre/post — scored 6–24, recorded via `SurveyScore`, the pilot's primary quantitative outcome | ✅ |

Financial-knowledge and self-efficacy are oral survey instruments administered
by the field team — this service does not run the survey itself. What it adds
is a place to enter the **computed scores** once the field team has them,
keyed by the same anonymized `user_hash` as engagement and arm data, the same
way `ArmAssignment` records the *result* of offline block-randomisation rather
than performing it. Whoever holds Grace's T0/T1 tracking sheet enters each
participant's scores via `POST /api/v1/research/survey-scores`; raw item-level
responses are not stored — only the scored 0–3 / 6–24 totals, per pilot plan
§5.2/§5.3's scoring rules.

**This checkpoint's dataset covers engagement, persona-consistency, financial
knowledge, and self-efficacy, for both arms, in one export.** A participant's
T1 columns are blank until their exit survey has been entered — expected for
still-enrolled participants at a mid-pilot (as opposed to final) checkpoint.

## Architecture

```
Pilot participants
  └─ enrolled offline; arm allocated via block-randomised sequence (plan §3.3)
       │
       ├─► POST /api/v1/research/arm-assignments   (admin, card C4.5)
       │      real user_id in → SHA256 hashed server-side → ArmAssignment row
       │
       └─ T0/T1 surveys administered orally by field team, scored, recorded:
              └─► POST /api/v1/research/survey-scores   (admin, card C4.5)
                     real user_id in → SHA256 hashed server-side → SurveyScore row
                     (one row per participant per wave: T0 or T1)

chat-orchestration-service
  └─ session.completed event → SessionMetric row (card C3.5, unchanged)

GET /api/v1/research/export/pilot-data.csv
  SessionMetric ⟕ ConsistencyRun          (on conversation_id, card O4.4)
                ⟕ ArmAssignment           (on user_hash, card C4.5)
                ⟕ SurveyScore(wave="T0")  (on user_hash, card C4.5)
                ⟕ SurveyScore(wave="T1")  (on user_hash, card C4.5)
  filtered by start_date / end_date / arm
```

## Implementation Details

### Model — `ArmAssignment` (`app/models/arm_assignment.py`)

```python
class ArmAssignment(Base):
    __tablename__ = "arm_assignments"
    user_hash: str    # PK — same SHA256(user_id + salt)[:16] as SessionMetric.user_hash
    arm: str           # "A" or "B"
    assigned_at: datetime
```

One row per participant, keyed by the same anonymized `user_hash` C3.5 already
uses — no new identifier scheme, and it joins to `SessionMetric` without a
cross-service foreign key. Upsert semantics: re-recording a `user_hash` updates
the arm rather than erroring, so re-loading a corrected enrolment sheet is safe.

### Model — `SurveyScore` (`app/models/survey_score.py`)

```python
class SurveyScore(Base):
    __tablename__ = "survey_scores"
    user_hash: str                        # PK part 1 — same hash as ArmAssignment
    wave: str                              # PK part 2 — "T0" or "T1"
    financial_knowledge_score: int | None  # 0-3, Big-Three-adapted (plan §5.2)
    self_efficacy_score: int | None        # 6-24, FSES-modified (plan §5.3)
    recorded_at: datetime
```

One row per participant **per wave** (composite PK), so T0 and T1 coexist
without overwriting each other. Scores only, never raw item responses — the
instruments are scored by the field team at administration time, per plan
§5.2/§5.3's scoring rules (Big-Three: count correct 0–3; FSES-modified:
reverse-score and sum 6–24). Upsert semantics on (`user_hash`, `wave`): safe to
re-run against a corrected tracking-sheet row.

### Endpoints (`app/main.py`, admin/researcher/lead_architect only — `_require_admin`)

#### `POST /api/v1/research/arm-assignments`

Record one or more participants' allocated arm. Accepts the **real** `user_id`
(never stored or echoed back) so whoever holds the offline allocation sequence
never has to compute the hash themselves:

```bash
curl -X POST http://localhost:8010/api/v1/research/arm-assignments \
  -H "X-User-Roles: admin" -H "Content-Type: application/json" \
  -d '{"assignments": [
        {"user_id": "participant-real-id-1", "arm": "A"},
        {"user_id": "participant-real-id-2", "arm": "B"}
      ]}'
```

#### `GET /api/v1/research/arm-assignments`

Roster + per-arm counts — use this to confirm both arms have coverage before
pulling the checkpoint export.

#### `POST /api/v1/research/survey-scores`

Record one or more participants' T0 or T1 survey scores. Accepts the **real**
`user_id` (never stored or echoed back), same pattern as arm-assignments:

```bash
curl -X POST http://localhost:8010/api/v1/research/survey-scores \
  -H "X-User-Roles: admin" -H "Content-Type: application/json" \
  -d '{"scores": [
        {"user_id": "participant-real-id-1", "wave": "T0",
         "financial_knowledge_score": 2, "self_efficacy_score": 15},
        {"user_id": "participant-real-id-2", "wave": "T0",
         "financial_knowledge_score": 1, "self_efficacy_score": 12}
      ]}'
```

`financial_knowledge_score` is 0–3; `self_efficacy_score` is 6–24 (both
validated server-side). Either may be omitted (`null`) if that instrument
wasn't completed for the wave.

#### `GET /api/v1/research/survey-scores`

Roster + per-wave (T0/T1) counts — use this to confirm T0 coverage before the
use period starts, and T1 coverage before pulling a checkpoint that needs
pre/post data for a participant.

#### `GET /api/v1/research/export/pilot-data.csv` (extended)

New `arm` query param (`A`, `B`, or omitted for both), a new `arm` CSV column,
and four new survey-score columns (`financial_knowledge_t0/t1`,
`self_efficacy_t0/t1`), left-joined from `SurveyScore` on `user_hash` and
`wave`. `end_date` is the mechanism for a midpoint cut — no separate
"midpoint" parameter; pass the pilot's actual midpoint date.

```bash
# Standard mid-pilot checkpoint: both arms, everything up to the midpoint date.
curl "http://localhost:8010/api/v1/research/export/pilot-data.csv?end_date=2026-09-01" \
  -H "X-User-Roles: researcher" -o mid-pilot-checkpoint.csv

# One arm only, for a quick per-arm sanity check.
curl ".../pilot-data.csv?end_date=2026-09-01&arm=A" -H "X-User-Roles: researcher"
```

CSV columns: `user_hash, arm, session_date, session_duration_seconds,
message_count, persona_id, prompt_to_line, line_to_line, qa_consistency,
aggregate, consistency_delta_pct, financial_knowledge_t0,
financial_knowledge_t1, self_efficacy_t0, self_efficacy_t1`.

## Testing

```bash
cd services/research-evaluation-service
pytest tests/test_arm_assignments.py tests/test_survey_scores.py tests/test_pilot_data_export.py -v
```

Covers: role-gating, hash-not-raw-id on both record and export, upsert
idempotency (including per-wave for survey scores, which T0 and T1 must not
overwrite each other), per-arm and per-wave counts, arm filtering, range
validation on survey scores, and that the export returns all 3 required
measures for both groups (the acceptance criterion) with blank T1 columns for
participants who haven't exited yet.

## Next Steps

- `docs/research/pilot-data-collection-plan-v0.md` is still **Draft v0,
  pending Grace's review**, with an open, blocking question (Q4: ethics board
  + data-protection jurisdiction) — confirm pilot data collection is actually
  authorized to proceed before running a real export against live participant
  data.
- Q5 (Big Three vs. OECD/INFE financial-knowledge subset) is still open for
  the **full study**; `financial_knowledge_score`'s 0–3 range assumes the
  Big-Three-adapted instrument stays as-is for this pilot.

## References

- `docs/research/pilot-data-collection-plan-v0.md` — pilot design, arms, measures (§1, §5)
- `docs/implementation/C3_5_session_metrics.md` — engagement telemetry this export reads
- Card O4.4 — original pilot-data export this card extends
