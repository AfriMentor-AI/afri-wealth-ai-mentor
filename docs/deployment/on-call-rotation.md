# On-call rotation (card O4.5)

Lightweight by design — a 4-person team ahead of a pilot, not an enterprise
on-call program. No paging tool is wired up yet (see
`incident-runbook.md`'s "what this deliberately doesn't cover" section), so
this is a **point of contact**, not a guaranteed-response pager rotation.

## Rotation

Weekly, one primary contact at a time, in a fixed order (matches
`docs/backlog-grooming.md`'s roster):

| Week starting (Mon) | Primary | Backup |
|---|---|---|
| 2026-08-24 | Olusegun | Daniel |
| 2026-08-31 | Daniel | Chukwuebuka |
| 2026-09-07 | Chukwuebuka | Grace |
| 2026-09-14 | Grace | Olusegun |
| (repeats) | | |

The **primary** is the first point of contact for anything raised per
`incident-runbook.md`'s Detection section. The **backup** picks it up if the
primary is unreachable — this is a 4-person team, so "unreachable" should be
rare and short.

## Responsibilities while on-call

- Be reachable during normal working hours for the week (no overnight/
  weekend expectation at this stage — there's no production traffic yet to
  justify it).
- Triage anything reported per `incident-runbook.md`.
- If you can't resolve it yourself, pull in whoever owns that service area
  (see the roster in `docs/backlog-grooming.md` — e.g. Chukwuebuka for RAG/
  eval, Daniel for chat).
- Add anything genuinely new to the runbook's "known issues" list once
  resolved, so the next person doesn't re-diagnose it from scratch.

## Swapping

Direct swap between two people, announced in the team's usual channel — no
formal process needed at this scale. Update the table above so it stays the
source of truth.

## Revisit before Sprint 5 production hardening

This rotation is intentionally minimal for the pilot phase. Before real
production traffic exists, revisit:
- Actual paging (not just "primary contact")
- Off-hours coverage, once there's traffic outside working hours to justify it
- Formal incident severity levels and response-time expectations
