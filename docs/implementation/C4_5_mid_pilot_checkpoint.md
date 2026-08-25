# Mid-Pilot Quantitative Data Checkpoint — Card C4.5

## Overview

Pull engagement and persona-consistency measures for both pilot arms at the
pilot's midpoint and hand the dataset to Grace for interim analysis. Extends the
O4.4 pilot-data export (`services/research-evaluation-service`) rather than
building a new pipeline:

- Adds a **study-arm** concept (Arm A / Arm B, per
  `docs/research/pilot-data-collection-plan-v0.md` §1) that did not exist
  anywhere in the codebase before this card, so the export can label and filter
  rows by which arm a participant was allocated to.
- Adds an `arm` filter and clarifies the existing `end_date` filter's use for a
  midpoint cut to `GET /api/v1/research/export/pilot-data.csv`.

## What this checkpoint delivers — and what it does not

The pilot plan (§5) specifies **three** required measures. Only one is
computable from data this service holds today:

| # | Measure | Source | In this export? |
| :--- | :--- | :--- | :---: |
| Engagement (§5.4/F4) | App telemetry — session length, message count (`SessionMetric`, card C3.5) | ✅ |
| Financial knowledge (§5.2) | Big-Three-adapted, administered **orally**, pre/post | ❌ |
| Financial self-efficacy (§5.3) | FSES-modified, administered **orally**, pre/post — *the pilot's primary quantitative outcome* | ❌ |

Financial-knowledge and self-efficacy are oral survey instruments with no
digital ingestion path into this service — there is no database table for them
anywhere in the repo. Building one is a separate, materially larger piece of
work (a scored-response model, an intake/data-entry path, likely tied to
however Grace's field team is already recording T0/T1 survey answers) and was
explicitly deferred out of this card's scope.

**This checkpoint's dataset covers engagement + persona-consistency scoring
only, for both arms.** Grace merges it with her separate Big-Three/FSES
tracking sheet (keyed by participant code, per pilot plan §7) for the full
interim picture.

## Architecture

```
Pilot participants
  └─ enrolled offline; arm allocated via block-randomised sequence (plan §3.3)
       │
       ├─► POST /api/v1/research/arm-assignments   (admin, card C4.5)
       │      real user_id in → SHA256 hashed server-side → ArmAssignment row
       │
chat-orchestration-service
  └─ session.completed event → SessionMetric row (card C3.5, unchanged)

GET /api/v1/research/export/pilot-data.csv
  SessionMetric ⟕ ConsistencyRun (on conversation_id, card O4.4)
                ⟕ ArmAssignment  (on user_hash, card C4.5)
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

#### `GET /api/v1/research/export/pilot-data.csv` (extended)

New `arm` query param (`A`, `B`, or omitted for both) and a new `arm` CSV
column. `end_date` is the mechanism for a midpoint cut — no separate "midpoint"
parameter; pass the pilot's actual midpoint date.

```bash
# Standard mid-pilot checkpoint: both arms, everything up to the midpoint date.
curl "http://localhost:8010/api/v1/research/export/pilot-data.csv?end_date=2026-09-01" \
  -H "X-User-Roles: researcher" -o mid-pilot-checkpoint.csv

# One arm only, for a quick per-arm sanity check.
curl ".../pilot-data.csv?end_date=2026-09-01&arm=A" -H "X-User-Roles: researcher"
```

CSV columns: `user_hash, arm, session_date, session_duration_seconds,
message_count, persona_id, prompt_to_line, line_to_line, qa_consistency,
aggregate, consistency_delta_pct`.

## Testing

```bash
cd services/research-evaluation-service
pytest tests/test_arm_assignments.py tests/test_pilot_data_export.py -v
```

Covers: role-gating, hash-not-raw-id on both record and export, upsert
idempotency, per-arm counts, arm filtering, and that omitting `arm` returns
rows for both groups (the acceptance criterion).

## Next Steps

- Decide and build a financial-knowledge/self-efficacy ingestion path before
  the **full study** (not required for this pilot checkpoint) — see the pilot
  plan's Q5 (instrument choice) and the note above.
- `docs/research/pilot-data-collection-plan-v0.md` is still **Draft v0,
  pending Grace's review**, with an open, blocking question (Q4: ethics board
  + data-protection jurisdiction) — confirm pilot data collection is actually
  authorized to proceed before running a real export against live participant
  data.

## References

- `docs/research/pilot-data-collection-plan-v0.md` — pilot design, arms, measures (§1, §5)
- `docs/implementation/C3_5_session_metrics.md` — engagement telemetry this export reads
- Card O4.4 — original pilot-data export this card extends
