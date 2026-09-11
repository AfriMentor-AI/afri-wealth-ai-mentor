# Persona Consistency Dashboard Final Tuning — Card C5.3

## Overview

Tune drift-alert thresholds using real pilot drift data and check/adjust the
false-positive rate of the manual-audit flagging (card C4.2). Acceptance
criterion: **false-positive rate on drift flags measured and reduced to an
agreed acceptable level.**

That criterion cannot be met yet, and this doc says exactly why rather than
claiming otherwise: no real pilot review data exists (confirmed before
starting this card), and no target rate has been agreed with product. What
this card actually delivers is the **capability to measure it** — nothing in
the codebase could produce that number before this card, real pilot data or
not.

## The gap this card found

`evaluate_review_flag` (`app/drift.py`, card C4.2) auto-flags a session for
human review when it's below an absolute floor (`CONSISTENCY_REVIEW_FLOOR`)
or its deviation from the persona's rolling baseline crosses
`DRIFT_THRESHOLD_PCT`. A reviewer can mark a flagged session `"reviewed"` via
`POST /audit-sessions/{id}/review` — but that endpoint, and the mirroring
`DriftAlert` acknowledge endpoint, only ever recorded **that** a human looked,
never **what they concluded**. There was no field anywhere to say "this flag
was right" vs. "this flag was noise." Without that, "false-positive rate" is
not a number that exists in this system — it has to be built before it can be
measured, let alone tuned against.

## What this card adds

### 1. Reviewer verdict — `ReviewVerdict` (`app/models/consistency_run.py`)

New nullable `ConsistencyRun.review_verdict` column (`true_positive` /
`false_positive`), added via the service's existing additive-migration path
(`_CONSISTENCY_ADDED_COLUMNS` in `app/main.py` — `ADD COLUMN IF NOT EXISTS`,
no Alembic in this service). `POST /audit-sessions/{id}/review` now accepts
an optional JSON body `{"verdict": "true_positive" | "false_positive"}`;
omitting it leaves `review_verdict` null, distinguishable from an explicit
verdict — a reviewer who just clicks "mark reviewed" without judging the flag
must not be silently counted as either outcome.

### 2. Measurement — `compute_false_positive_rate` (`app/drift.py`)

Reads only rows with `review_status="reviewed"` **and** a non-null
`review_verdict` — ground truth, not every flagged session. Returns an
overall rate and a breakdown by `review_reason` (`below_floor` / `drift` /
`below_floor+drift`), because the floor and the drift-deviation threshold are
two independently tunable knobs (`CONSISTENCY_REVIEW_FLOOR` /
`DRIFT_THRESHOLD_PCT`) — an overall rate alone can't say which one needs
tightening or loosening. An empty bucket reports `rate: null`, never `0.0` —
no reviewed sessions is a different fact from "zero were false positives",
and collapsing them would make an unexercised threshold look validated-clean.

Exposed via `GET /api/v1/research/audit-sessions/false-positive-rate`
(optional `?persona_id=`), admin-gated like every other research-console
endpoint, for the dashboard to actually surface this to Grace/product once
real data exists.

### 3. Reviewer UI — `apps/admin-research-console/app/dashboard/page.tsx`

The API alone wasn't reviewer-usable: nothing in the Research Console let a
human actually record a verdict. The single "Mark reviewed" button is now two
(**✓ Correct** / **✗ False positive**) that submit the verdict in the same
click that closes the review — no separate step a reviewer could skip.
Reviewed rows show their recorded verdict inline. A new panel above the audit
table reads `GET .../false-positive-rate` and shows the overall rate plus the
per-reason breakdown, `"no data yet"` (not `0%`) until real verdicts exist —
this is the mechanism for actually seeing the number Grace/product would set
a target against, not a guess rendered as data.

### 4. Tests

9 new tests in `tests/test_manual_audit.py`: verdict persists through the
review endpoint, an omitted verdict stays null (not fabricated), an invalid
verdict value 422s, `compute_false_positive_rate`'s null-vs-zero distinction,
its exclusion of unreviewed/verdictless rows, its overall + per-reason
breakdown math, its persona filter, and the endpoint's admin gate + wiring.
Full suite: 157 passed (148 pre-existing + 9 new), all offline (SQLite
in-memory, no Postgres/pilot data needed).

## What's still blocking the actual acceptance criterion

1. **Real pilot review data.** Confirmed before starting: no pilot instance
   with real `ConsistencyRun` rows exists yet. The `review_verdict` field
   only has data once reviewers start using it during real manual-audit
   passes on real flagged sessions — this card ships the capability, it
   cannot backfill history that was never recorded.
2. **An agreed acceptable rate.** Confirmed before starting: no target exists
   yet. "Reduced to an agreed acceptable level" needs that agreement from
   Grace/product before "reduced" is even a meaningful claim — there is
   nothing to reduce *to*.
3. Once both exist: call `GET /audit-sessions/false-positive-rate`
   periodically against real reviewed-and-verdicted sessions, compare against
   the agreed target, and if too high, adjust `CONSISTENCY_REVIEW_FLOOR`
   and/or `DRIFT_THRESHOLD_PCT` (whichever the `by_reason` breakdown points
   at) and re-measure. That loop is now possible; running it isn't something
   this session can do without real reviewers and real sessions.

## References

- `app/drift.py` — `evaluate_review_flag` (C4.2), `evaluate_drift_and_alert`
  (O4.1), this card's `compute_false_positive_rate`
- `app/models/consistency_run.py` — `ReviewStatus` (existing), `ReviewVerdict`
  (this card)
- `app/config.py` — `consistency_review_floor`, `drift_threshold_pct`, the two
  knobs a real measurement would tune
