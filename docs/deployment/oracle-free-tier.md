# Deploying the backend for free (Oracle Cloud Always Free VM)

`docs/deployment/azure.md` covers a paid (credit-funded) path on Azure Container Apps.
This is the **zero-cost** path: a single Oracle Cloud "Always Free" VM running the same
lean-MVP service set — `api-gateway`, `auth-user-service`, `chat-orchestration-service`,
`persona-prompt-service`, `rag-corpus-service` — via the same `docker-compose.yml` +
`docker-compose.staging.yml` you already have, plus one new overlay
(`docker-compose.oracle.yml`) that locks down everything except the gateway.

**Why this platform and not the others:** PythonAnywhere's free tier doesn't support
ASGI/FastAPI at all and blocks outbound calls to anything not on its allowlist (which
would block your Groq LLM calls); Fly.io dropped its free tier in 2024 (card required
now); Render's free web services sleep after 15 minutes idle and its **free Postgres is
deleted 30 days after creation** — bad for a backend that has to keep user data. Oracle's
Always Free Ampere A1 VM is a real, forever-free VM (no trial, no expiry) currently sized
at 2 OCPU / 12 GB RAM (Oracle quietly halved this from 4/24 in June 2026 — still enough
for this stack). It's a real machine, so it runs your existing Docker Compose setup
almost unchanged, instead of you re-architecting around five different free tiers
stitched together.

**The tradeoff you're accepting:** you're now the ops team. No auto-restart-on-crash
beyond what Compose's `restart: unless-stopped` gives you, no managed backups, and you
patch the OS yourself. Fine for a portfolio/demo deployment; revisit before this holds
real users.

## 1. Create the Oracle Cloud account

1. Go to [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) and sign up. You'll
   need a phone number and a card for identity verification — Oracle does **not** charge
   it for Always Free resources; it's only there to stop bot signups and to charge if you
   later, deliberately, upgrade to paid resources.
2. Pick your **home region** carefully during signup — Always Free resources are pinned
   to whichever region you choose here and you generally can't move them later. Pick one
   geographically close to you or your users.

## 2. Create the VM

Console → **Compute** → **Instances** → **Create instance**.

1. **Name**: anything, e.g. `afrimentor-vm`.
2. **Image**: Canonical Ubuntu (22.04 or 24.04), **aarch64/ARM** build.
3. **Shape**: click *Change shape* → **Ampere** → `VM.Standard.A1.Flex` → set
   **2 OCPUs / 12 GB memory** (the full remaining Always Free allowance as of the June
   2026 tier cut — using less just leaves capacity unused).
4. **Networking**: let it create a new VCN with the defaults (this also creates a
   Security List that allows inbound SSH — you'll add one more rule to it in step 4).
5. **SSH keys**: let Oracle generate a key pair and **download the private key** (or
   paste in your own public key if you already have one you prefer).
6. Create. If you get **"Out of host capacity"** — this is a very common, well-known
   Always Free issue, not something wrong with your account. Just retry (Oracle's
   console has a "keep retrying" option), or try a different Availability Domain if your
   region has more than one.

Note the instance's **public IP address** once it's running.

## 3. Connect

```bash
chmod 600 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<public-ip>
```

## 4. Open the firewall — two layers, both required

This is the single most common thing people get stuck on with OCI. A request has to get
through **both**:

**a) The OCI Security List** (the cloud firewall): Console → **Networking** → **Virtual
Cloud Networks** → your VCN → **Security Lists** → **Default Security List** → **Add
Ingress Rules**:
- Source CIDR: `0.0.0.0/0`, IP Protocol: TCP, Destination Port Range: `8000`

**b) The VM's own iptables** (Oracle's Ubuntu images ship with a restrictive iptables
ruleset active *inside* the VM, on top of the cloud firewall — opening the Security List
alone does nothing until you also do this):

```bash
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save   # if that command doesn't exist:
sudo sh -c "iptables-save > /etc/iptables/rules.v4"
```

Use `-I INPUT` (insert at the top), not `-A` (append) — Oracle's default ruleset ends
with a catch-all reject rule that would otherwise shadow an appended rule.

Only port 8000 (`api-gateway`) needs to be open. Every other service stays
internal-only via `docker-compose.oracle.yml` — don't open their ports even temporarily,
they have no auth of their own (the gateway is the only thing that verifies JWTs).

## 5. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker
```

Log out and back in (or `newgrp docker`) for the group change to take effect, then
confirm:

```bash
docker run --rm hello-world
```

## 6. Clone the repo and configure secrets

```bash
git clone https://github.com/AfriMentor-AI/afri-wealth-ai-mentor.git
cd afri-wealth-ai-mentor

cp .env.example .env
nano .env   # set LLM_API_KEY to your Groq key

mkdir -p infra/keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out infra/keys/jwt_private_key.pem
openssl rsa -pubout -in infra/keys/jwt_private_key.pem -out infra/keys/jwt_public_key.pem
```

(Same RS256 key generation as `docs/deployment/staging.md` — a real persistent keypair
instead of the ephemeral dev fallback, so restarting the container doesn't invalidate
every issued token.)

One more export, even though Grafana isn't part of this deploy: `docker-compose.staging.yml`
requires `GF_SECURITY_ADMIN_PASSWORD` to be set before Compose will interpolate the merged
config *at all* — it fails the same way `scripts/deploy-staging.sh` would without it, even
though `deploy-oracle.sh` never actually starts Grafana. Any value works here:

```bash
export GF_SECURITY_ADMIN_PASSWORD="$(openssl rand -base64 18)"
```

Put that line in `~/.bashrc` on the VM (or re-export it each session) so it's set before
every future `scripts/deploy-oracle.sh` run too.

## 7. Deploy

```bash
scripts/deploy-oracle.sh
```

This builds and starts the 5 lean-MVP services plus their datastores (Postgres, Redis,
RabbitMQ, ChromaDB), waits for health checks, and runs the same signup/login smoke test
as `scripts/deploy-staging.sh`. **First run builds 5 Docker images from source on a
2-core VM — expect 10-15 minutes**, not the couple of minutes it takes on a dev laptop.

## 8. Verify from outside the VM

From your own machine (not the VM):

```bash
curl http://<public-ip>:8000/health
```

If that hangs or connection-refuses, re-check step 4 — it's almost always one of the two
firewall layers.

### Debugging the services `docker-compose.oracle.yml` locked down

Postgres, Redis, RabbitMQ and the four backend services other than `api-gateway` no
longer publish ports on the VM at all — that's the point. To poke at one during
debugging (e.g. the RabbitMQ management UI, or `psql` against Postgres), tunnel over SSH
instead of opening a port: it never touches the OCI Security List or iptables, since the
traffic rides inside the SSH connection.

```bash
ssh -i ~/Downloads/ssh-key-*.key -L 15672:localhost:15672 ubuntu@<public-ip>
# then browse http://localhost:15672 on your own machine
```

## Keeping it running

- Every service already has `restart: unless-stopped` (`docker-compose.yml`), so a
  crashed container restarts on its own.
- Make Docker itself survive a VM reboot: `sudo systemctl enable docker` (already done in
  step 5) — Compose then brings the stack back up automatically because of the same
  restart policy.
- Free-tier VMs get reclaimed by Oracle if **idle** for too long by some accounts' terms
  — a running Docker stack handling any traffic counts as active, but if you're not
  touching it for weeks, log in occasionally so it doesn't get flagged.

## Updating after a code change

```bash
cd afri-wealth-ai-mentor
git pull
scripts/deploy-oracle.sh
```

Re-running the script rebuilds only what changed (Docker layer caching) and restarts
those containers; Postgres data in the `pgdata_staging` volume is untouched.

## Tearing down

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.oracle.yml -p afrimentor-staging down
# add -v to also drop the pgdata_staging volume
```

Or just terminate the VM from the OCI console if you're done with it entirely — Always
Free resources cost nothing while they exist, but there's no reason to leave one running
unattended indefinitely.

## What's still missing for a fully public demo

- **HTTPS**: the gateway is plain HTTP on port 8000 right now. Fine for `curl`/Postman
  testing; if you later put a real frontend on a domain with HTTPS in front of this,
  browsers will block calling an HTTP API from an HTTPS page (mixed content). Adding a
  free reverse proxy with automatic Let's Encrypt certs (Caddy is the simplest — one
  container, one line of config) is a natural next step once you have a domain name
  pointed at this VM's IP.
- The frontend itself isn't part of this guide — it wasn't in scope for "the backend."
  It can run anywhere (Vercel's free tier is a natural fit for a Next.js app) and just
  needs `NEXT_PUBLIC_API_BASE_URL` pointed at `http://<public-ip>:8000` (or the HTTPS
  domain, once that exists).
