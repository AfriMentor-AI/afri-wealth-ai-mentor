# Incident runbook (card O4.5)

Scope: what to do when something in staging (or, once it exists, production)
is broken. Written for the current reality — no cloud environment yet, no
alerting pipeline wired to a pager, a 4-person team — not aspirational
enterprise process. Update this as those things change.

## Detection

Nothing pages anyone automatically yet. Today, an incident is noticed by one
of:

- A team member hitting an error while using staging/dev.
- The observability stack (`docs/observability.md`) — Grafana dashboards,
  or a service's `/health` endpoint failing — if someone is actively looking.
- A load-test or deploy script failing (`scripts/deploy-staging.sh`'s smoke
  test, or `scripts/load-test/run_pilot_load_test.py`).

**Gap, tracked for Sprint 5:** no automated alerting (e.g. Grafana → Slack/
email) exists yet. Until it does, the on-call rotation
(`on-call-rotation.md`) is a *point of contact*, not a guarantee someone
gets paged — closing this gap is real Sprint 5 production-hardening work,
not something to fake here.

## Triage

1. **Identify blast radius.** One service, or the whole stack? Check:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml -p afrimentor-staging ps
   ```
   Look for containers not in a `healthy` state.
2. **Check the logs of the unhealthy service first**, not the whole stack:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml -p afrimentor-staging logs <service> --tail 100
   ```
3. **Check whether it's a known class of issue before assuming it's new** —
   these have all been hit for real during this sprint's work and are cheap
   to rule out first:
   - *Container recreated but stuck "unhealthy" or unreachable from other
     containers*: a stale Docker network attachment. Fix:
     `docker compose ... up -d --force-recreate <service>` (confirmed to
     resolve it during O4.2/O4.3 testing — a container can come up
     "healthy" per its own healthcheck but still be missing from the
     compose network, so peers can't reach it by hostname).
   - *`QueuePool limit ... reached, connection timed out`* in a service's
     logs under load: SQLAlchemy connection pool exhaustion, not a code
     bug — see O4.3's load test report
     (`docs/deployment/o4-3-pilot-load-test-report.md`) for the exact fix
     pattern (explicit `pool_size`/`max_overflow`, guarded to Postgres
     only).
   - *A service crash-loops immediately on a fresh build* with
     `ModuleNotFoundError`: a missing pin in that service's
     `requirements.txt` relative to what `app/observability.py` actually
     imports — check the other services' `requirements.txt` for the same
     import as a reference.
   - *Sessions/tokens all invalid after a restart, in dev*: expected before
     the O4.5-era auth fix; after it, `auth-user-service`'s dev-mode signing
     key persists across restarts via the `auth_dev_keys` volume — if this
     regresses, check that volume is actually mounted.

## Rollback

No image registry is wired to staging yet (`ci.yml` only pushes on merge to
`main`), so rollback today means checking out the previous known-good commit
and redeploying — see `docs/deployment/staging.md`'s own Rollback section
for the exact commands. Once a registry-backed release process exists
(tracked as Sprint 5 production-hardening work), prefer rolling back to a
pinned image tag over a git checkout.

## Data-loss incidents

If the incident involves losing or corrupting data (not just a service being
down), see `docs/deployment/backup-strategy.md` for the restore procedure —
it's been tested with a real drill, not just documented. Restore into a
disposable instance first to confirm the backup is good before touching the
affected database.

## Communication

- Post in the team's usual channel (not yet decided beyond this repo's own
  history — the team was AfriMentor-AI on GitHub; no dedicated incident
  channel exists yet) what's broken, blast radius, and who's on it.
- Once resolved, a short postmortem note (what broke, why, what fixed it) —
  doesn't need to be formal, but should exist somewhere findable (this repo's
  `docs/` is the obvious place) so the same class of issue doesn't get
  re-diagnosed from scratch next time. The "known issues" list in Triage
  above is exactly this pattern — add to it.

## What this runbook deliberately doesn't cover yet

- Paging/on-call tooling (PagerDuty-equivalent) — no such tool is in use.
- Production incident response — there is no production yet.
- SLAs/SLOs — not defined yet; premature before pilot usage data exists.

These are real Sprint 5 gaps, not oversights in this document.
