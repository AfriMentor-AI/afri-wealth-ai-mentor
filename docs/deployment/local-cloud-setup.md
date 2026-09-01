# Personal Cloud-Hybrid Development Setup

This guide explains how to run AfriMentor AI using managed free-tier cloud services (**Supabase**, **Qdrant Cloud**, **Groq**, **Vercel**) alongside lightweight local Python microservices via `docker-compose.cloud.yml`.

This setup leaves the team's standard `docker-compose.yml` completely untouched.

---

## Architecture Overview

```
Frontend (Vercel or Local Port 3000)
       │
       ▼
Local API Gateway (Port 8000)
       │
       ├─► Local FastAPI Microservices (Auth, Chat, Persona, RAG, Goals, etc.)
       │        │
       │        ├─► Supabase Cloud (PostgreSQL via Supavisor Pooler)
       │        ├─► Qdrant Cloud (Managed Vector DB for RAG)
       │        └─► Groq Cloud (Ultra-fast LLM LPUs)
       │
       └─► Local Lightweight Brokers (Redis + RabbitMQ)
```

---

## 1. Cloud Accounts & Free Tier Setup

### A. Groq (LLM Inference)
1. Go to [console.groq.com](https://console.groq.com/) and sign in.
2. Under **API Keys**, click **Create API Key**.
3. Copy your key (starts with `gsk_...`).

### B. Supabase (PostgreSQL Database)
1. Go to [supabase.com](https://supabase.com/) and create a new project.
2. Go to **Project Settings** → **Database**.
3. Under **Connection String**, select **URI** and choose **Mode: Session (or Transaction)** on port `6543` (Supavisor pooler).
4. Copy the connection string and replace `[YOUR-PASSWORD]` with your database password:
   ```text
   postgresql+psycopg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require
   ```

### C. Qdrant Cloud (Vector Database)
1. Go to [cloud.qdrant.io](https://cloud.qdrant.io/) and create a free tier cluster (1GB RAM, always free).
2. Note your **Cluster URL** (e.g. `https://[CLUSTER-ID].[REGION].gcp.cloud.qdrant.io:6333`).
3. Under **Data Access Control** / **API Keys**, create an API key.

---

## 2. Configure Environment

1. Copy the template:
   ```powershell
   cp .env.cloud.example .env.cloud
   ```
2. Open `.env.cloud` in your editor and paste your credentials:
   - `SUPABASE_DATABASE_URL`
   - `QDRANT_URL` and `QDRANT_API_KEY`
   - `LLM_API_KEY`

---

## 3. Running the Stack

### Option 1: Ultra-Lean Core MVP (Recommended for Fast Local Dev)
Boots only the 5 core AI/mentoring services + local brokers (~300MB RAM total):
```powershell
docker compose -f docker-compose.cloud.yml --env-file .env.cloud up -d `
  redis rabbitmq api-gateway auth-user-service chat-orchestration-service persona-prompt-service rag-corpus-service
```

### Option 2: Full 13-Service Stack
Boots all capability services:
```powershell
docker compose -f docker-compose.cloud.yml --env-file .env.cloud up -d
```

### Checking Status
```powershell
docker compose -f docker-compose.cloud.yml ps
curl http://localhost:8000/health
```

---

## 4. Connecting the Frontend

### Method A: Local Frontend (`localhost:3000`)
In another terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser. It automatically proxies `/api/v1/*` to `http://localhost:8000`.

### Method B: Vercel Frontend + Local Backend
If your frontend is deployed on Vercel:
1. Expose your local gateway via a free Cloudflare Quick Tunnel (no account required):
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
2. Copy the generated public HTTPS URL (e.g. `https://random-words.trycloudflare.com`).
3. In Vercel Project Settings → **Environment Variables**, set:
   * `BACKEND_ORIGIN` = `https://random-words.trycloudflare.com`
4. Redeploy the Vercel project.

---

## 5. Stopping the Stack
```powershell
docker compose -f docker-compose.cloud.yml down
```

