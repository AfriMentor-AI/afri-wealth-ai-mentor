# Production cutover record — O5.3

Execution record for the runbooks in `docs/deployment/oracle-free-tier.md` (backend) and
`docs/deployment/vercel-frontend.md` (frontend). This is a real cutover against live
Oracle Cloud and Vercel accounts — not a simulation. Where the live execution deviated
from either runbook, that's called out explicitly below rather than silently glossed
over.

## What's deployed, and where

| Component | Platform | Address | Status |
|---|---|---|---|
| Backend (`api-gateway` + lean-MVP services) | Oracle Cloud Always Free VM (Ampere A1, 2 OCPU / 12 GB RAM) | `http://129.146.27.138:8000` | Live |
| Frontend (Next.js) | Vercel (Hobby tier) | `https://afri-wealth-ai-mentor.vercel.app` | Live |

Backend health check, run at cutover verification time:

```
$ curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" http://129.146.27.138:8000/health
HTTP 200 in 0.563098s
```

## Deviation 1: Oracle Linux 9, not Ubuntu

`docs/deployment/oracle-free-tier.md` step 2 specifies a Canonical Ubuntu image. The
instance-creation wizard's image selector would not persist an Ubuntu selection across
several attempts (clicking Ubuntu in the image-picker drawer, the wizard's underlying
state stayed on Oracle Linux 9 regardless) — a wizard bug, not a capacity or eligibility
issue. Rather than keep fighting the console, the VM was created on **Oracle Linux 9**
instead, which is equally covered by the Always Free tier and equally capable of running
the same Docker Compose stack. Two runbook steps needed adapting as a result:

- **SSH user**: `opc`, not `ubuntu` (`ssh -i <key> opc@129.146.27.138`).
- **Host firewall**: Oracle Linux uses `firewalld`, not the raw `iptables` commands in
  the runbook's step 4b. The equivalent:
  ```bash
  sudo firewall-cmd --permanent --add-port=8000/tcp
  sudo firewall-cmd --reload
  ```
- **Docker install**: `get.docker.com` doesn't support Oracle Linux
  (`Unsupported distribution 'ol'`). Installed instead via Docker's RHEL-compatible repo:
  ```bash
  sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
  sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  ```

Everything downstream of the OS (the two-layer firewall model, the Compose stack, the
health-check/smoke-test flow) matches the runbook unchanged. `docs/deployment/oracle-free-tier.md`
still documents the Ubuntu path since it's the simpler default for a fresh reader; this
is recorded here as the actual deviation taken for this specific cutover.

## Deviation 2: source transfer without deploy keys

The runbook assumes `git clone` on the VM. The `AfriMentor-AI` org has deploy keys
disabled org-wide (`gh repo deploy-key add` → `422: Deploy keys are disabled for this
repository`), and placing a personal GitHub credential on the VM wasn't worth the
tradeoff for a single-shot deploy. Instead, code was transferred without ever putting a
GitHub credential on the VM:

```bash
git archive --format=tar.gz HEAD -o afrimentor-src.tar.gz   # from the clean local tree
scp afrimentor-src.tar.gz opc@129.146.27.138:~/
ssh opc@129.146.27.138 "mkdir -p afri-wealth-ai-mentor && tar -xzf afrimentor-src.tar.gz -C afri-wealth-ai-mentor"
```

Future updates (runbook's "Updating after a code change" section, which assumes
`git pull`) will need the same archive+scp treatment, or a deploy-key exception, until
someone reverses the org policy.

## Deviation 3: JWT key file permissions

`scripts/deploy-oracle.sh`'s signup/login smoke test initially failed with HTTP 500 →
`PermissionError: [Errno 13] Permission denied: '/run/secrets/jwt_private_key.pem'`. The
key file was generated with mode `600` per the runbook, but the container's app user
(UID 10001) doesn't match the host `opc` user that owns the file — a standard
Docker-bind-mount UID mismatch. Fixed by relaxing the mounted key to `644`
(confirmed with the user before applying, since it's a permissions change to a live
secret file):

```bash
chmod 644 infra/keys/jwt_private_key.pem
docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.oracle.yml \
  -p afrimentor-staging restart auth-user-service
```

After the fix, the smoke test passed and external verification confirmed the same:

```
$ curl -s http://129.146.27.138:8000/health
{"status":"ok"}
```

Full signup/login round trip re-verified during this record's own write-up (see
"Frontend verification" below) — real RS256-signed JWTs issued from the live VM.

## Deviation 4: Vercel dashboard Git-import couldn't link the repo — deployed via CLI instead

`docs/deployment/vercel-frontend.md` step 2 assumes importing straight from the Vercel
dashboard's GitHub picker. That path was blocked by a genuine Vercel-side bug, confirmed
and isolated rather than assumed:

- GitHub's own org installation settings
  (`github.com/organizations/AfriMentor-AI/settings/installations/158083338`) show the
  Vercel GitHub App installed with **"All repositories"** access, no pending requests.
- Vercel's dashboard repo picker, scoped to the `AfriMentor-AI` org, only ever showed a
  stale unrelated `demo-repository` — never `afri-wealth-ai-mentor`, even after
  re-selecting the scope and clearing search filters.
- Both the dashboard's picker-based import and the "paste repo URL directly" workaround
  reached the project-configuration screen fine (repo directory structure, including
  `frontend/`, resolved correctly — so read access clearly worked), but clicking
  **Deploy** consistently failed. Intercepting the actual network response (via an
  injected `fetch` wrapper, since the UI only ever showed a generic banner) surfaced the
  real error:
  ```json
  {"error":{"code":"bad_request","message":"To link a GitHub repository, you need to
  install the GitHub integration first. ...","action":"Install GitHub App",
  "link":"https://github.com/apps/vercel"}}
  ```
  Following that link confirmed, again, that the app *is* installed with full access —
  this is Vercel's backend not recognizing a linkage that GitHub's side genuinely has.

Rather than keep fighting a platform-side sync bug, the frontend was deployed directly
via the Vercel CLI from the local `frontend/` directory, which uploads build output
without depending on the Git-integration linkage at all:

```bash
cd frontend
npx vercel login              # device-code OAuth, confirmed via browser
npx vercel link --yes --project afri-wealth-ai-mentor
npx vercel env add BACKEND_ORIGIN production   # http://129.146.27.138:8000
npx vercel env add BACKEND_ORIGIN preview      # same value
npx vercel --prod --yes
```

`vercel link` itself attempted the same GitHub auto-connect and hit the identical error —
confirming this is a project-to-repo linking bug, not specific to the dashboard UI — but
project creation and the CLI deploy both succeeded regardless, since neither depends on
that linkage.

`NEXT_PUBLIC_API_BASE_URL` was deliberately **not set** (left unset rather than set to an
empty string) — `frontend/lib/session.ts` treats an unset value identically to an empty
one (`process.env.NEXT_PUBLIC_API_BASE_URL?.trim()`), so this matches the runbook's
intent without needing an explicit empty-string env var entry.

**Practical consequence:** because the Vercel project isn't Git-linked, pushes to
`develop` will **not** auto-deploy the frontend right now, unlike the runbook's step 4
assumption. Until Vercel's sync bug clears (or the project is manually re-linked once it
does — `vercel git connect` was offered as a next step in the CLI's own output),
frontend updates need a manual `cd frontend && npx vercel --prod --yes` from a machine
with the repo checked out. This is a real, currently-live gap worth tracking as
follow-up, not a one-time footnote.

## Frontend verification

Per `docs/deployment/vercel-frontend.md` step 5 — confirming the proxy chain
(browser → Vercel HTTPS → Oracle VM HTTP, server-to-server → `api-gateway` →
`auth-user-service`) works with no CORS or mixed-content errors:

```js
// executed in the deployed page's own context
await fetch('/api/v1/auth/signup', { method: 'POST', headers: {...}, body: JSON.stringify({...}) });
// → 201, url: https://afri-wealth-ai-mentor.vercel.app/api/v1/auth/signup, real JWT returned

await fetch('/api/v1/auth/login', { method: 'POST', headers: {...}, body: JSON.stringify({...}) });
// → 200, same-origin, real JWT returned
```

Both requests resolved same-origin against the Vercel domain — no CORS preflight
failures, no mixed-content blocking, confirming `next.config.js`'s `rewrites()` proxy is
doing its job in production. Console error log for the page was also checked and is
clean.

## Rollback dry-run (local staging, before touching the real VM)

Per the AC's explicit requirement and matching O4.5's restore-drill discipline, a
rollback was rehearsed locally before the Oracle cutover, using the exact procedure
`docs/operations/operational-runbooks.md §2.1` documents for a production rolling
restart:

```bash
docker compose -f docker-compose.yml -p afrimentor-staging build persona-prompt-service
docker compose -f docker-compose.yml -p afrimentor-staging up -d --no-deps persona-prompt-service
docker compose -f docker-compose.yml -p afrimentor-staging ps persona-prompt-service
```

Sequence rehearsed: build and deploy a "bad" revision of `persona-prompt-service` →
confirm it's running (`Recreated` → `Started`) → rebuild and redeploy the prior "good"
revision (the rollback) → confirm it's running again. Both builds and both
recreate/restart cycles completed cleanly (real `docker compose build` + `up -d --no-deps`
output captured), demonstrating the single-service rolling-update path the runbook
documents works as a rollback mechanism.

**Honest caveat:** an earlier, more ambitious attempt at this drill tried bringing up the
*entire* 13-container staging stack a second time on remapped ports (`18000`+ range,
alongside the already-running stack) to rehearse a full-stack rollback in isolation. That
attempt hit real Docker Desktop engine instability on this machine (`502 Bad Gateway`
from the `dockerDesktopLinuxEngine` pipe, and a port-already-allocated conflict from the
first port-remap try) — a local tooling limitation, not a failure of the rollback logic
itself. That approach was abandoned in favor of the single-service drill above, which
directly matches the procedure the operational runbook actually prescribes for
production and completed without issue.

## Post-cutover monitoring status

No dedicated observability stack (Grafana/Prometheus) is deployed alongside the Oracle
backend — `docker-compose.staging.yml`'s Grafana service is deliberately not started by
`scripts/deploy-oracle.sh` (per `docs/deployment/oracle-free-tier.md`'s own note on
`GF_SECURITY_ADMIN_PASSWORD`). Current monitoring is limited to:

- `GET /health` on the gateway, confirmed reachable from the public internet.
- Docker's own `restart: unless-stopped` policy on every service.
- Manual `docker compose ps`/`logs` over SSH.

This matches the Oracle runbook's stated scope ("Fine for a portfolio/demo deployment;
revisit before this holds real users") and is not a regression from what was planned.

## Outstanding follow-ups

1. Reconnect the Vercel project to GitHub (`vercel git connect`, or retry the dashboard
   import) once Vercel's App-installation sync bug clears, to restore auto-deploy on
   push. Until then, frontend deploys are manual.
2. HTTPS on the Oracle gateway itself (both runbooks' "still missing" section) — not
   needed today since the Vercel rewrite proxy sidesteps mixed-content entirely, but
   worth doing before this VM serves anything beyond the proxied frontend.
3. `frontend/lib/api.ts`'s remaining mock-data functions, tracked separately (O5.1's
   BUG-06 fix covers `createGoal`/`fetchGoals`/`fetchMilestonesByGoal`; anything not
   covered there is still mock).
