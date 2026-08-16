# Deploying the frontend for free (Vercel)

Companion to `docs/deployment/oracle-free-tier.md` — that one gets the backend live on a
free Oracle VM; this gets the Next.js frontend live on Vercel's free (Hobby) tier, wired
to it.

## The problem this has to solve first

The Oracle VM serves `api-gateway` over plain HTTP (`http://<vm-ip>:8000` — see that
doc's "What's still missing" section). Vercel serves your frontend over HTTPS. If the
frontend called the gateway directly from the browser, two things would break it:

- **Mixed content**: browsers silently block an HTTPS page from calling an HTTP endpoint.
- **CORS**: `services/api-gateway/app/main.py` hardcodes `allow_origins` to
  `localhost:3000`/`3001` — it doesn't know about your Vercel domain, and always-changing
  Vercel preview URLs make listing them by hand impractical anyway.

Fixing this by adding HTTPS to the VM (the "later" section of the Oracle doc) is one
option, but it means running and renewing a certificate. The simpler fix, already wired
into `frontend/next.config.js`/`.mjs`: a Next.js `rewrites()` rule that proxies
`/api/v1/*` through Vercel's own servers to the Oracle gateway. The **browser only ever
talks to your Vercel domain** — same origin, HTTPS, no CORS involved — and Vercel makes
the plain-HTTP hop to the gateway server-side, where mixed-content and CORS don't apply
(both are browser-only rules). `frontend/lib/session.ts` already calls relative paths
(`${API_BASE}${path}` with `API_BASE` empty), so no frontend code changes are needed —
just two environment variables, set below.

## 1. Get the backend live first

Follow `docs/deployment/oracle-free-tier.md` end to end and confirm
`curl http://<vm-ip>:8000/health` works from your own machine. You need that IP for step
3 below.

## 2. Import the project into Vercel

1. Sign in to [vercel.com](https://vercel.com) with your GitHub account (free, no card).
2. **Add New** → **Project** → select `AfriMentor-AI/afri-wealth-ai-mentor`.
3. **Root Directory**: click *Edit* and set it to `frontend` — the Next.js app lives
   there, not at the repo root. Vercel should auto-detect the Next.js framework preset
   once you do.
4. Don't deploy yet — set the environment variables first (step 3).

## 3. Set environment variables

Project → **Settings** → **Environment Variables**, for the **Production** environment
(and **Preview** too, if you want preview deployments to also hit the live backend):

| Name | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | *(leave the value empty)* |
| `BACKEND_ORIGIN` | `http://<your-oracle-vm-public-ip>:8000` |

`NEXT_PUBLIC_API_BASE_URL` empty (not unset) makes `lib/session.ts` build relative
`/api/v1/...` URLs instead of falling back to `http://localhost:8000`.
`BACKEND_ORIGIN` is read only by `next.config.js`'s `rewrites()` at build time — it's
never sent to the browser, so your VM's IP doesn't end up in the client bundle.

## 4. Deploy

Trigger the first deploy from the Vercel dashboard (**Deploy** button), or just push to
the branch Vercel is tracking — it redeploys automatically on every push from here on.

## 5. Verify

Open the deployed URL, open your browser's DevTools → Network tab, and reload. You
should see a request to `/api/v1/auth/signup` (the device-session bootstrap in
`lib/session.ts`) return `200`, same-origin, no CORS or mixed-content error — that
confirms the proxy is working end to end: browser → Vercel (HTTPS) → Oracle VM (HTTP,
server-to-server) → `api-gateway` → `auth-user-service`.

If it 502s or times out instead: re-check the Oracle VM's firewall (both layers, per the
Oracle doc's step 4) and that `BACKEND_ORIGIN` has no trailing slash.

## Redeploying after changing `BACKEND_ORIGIN`

Because the rewrite destination is baked into the build at build time (confirmed by
inspecting `.next/routes-manifest.json` locally), changing the env var alone doesn't
retroactively update a live deployment — trigger a new deploy (**Deployments** →
**Redeploy**, or push a commit) any time you change the VM's IP.

## What's still mock data

Same caveat as the Azure/Oracle backend docs: `frontend/lib/api.ts` mostly still returns
mock data. This deploy makes the device-session bootstrap (`lib/session.ts`, used for
every authenticated `apiFetch` call) hit the real backend — goals/chat/library pages
still show mock content until `lib/api.ts`'s individual functions are rewired to fetch
from the gateway, which is separate follow-up app work.
