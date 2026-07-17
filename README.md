# Personal Finance Copilot — Backend

An AI-powered Personal Finance Copilot backend. It ingests a user's financial
documents (bank statements, credit-card statements, salary slips, investment and
loan statements), runs them through a **linear multi-agent pipeline**
(`parse → categorize → analyze → recommend`), and assembles a financial profile,
metrics dashboard, and grounded chat assistant from the results.

- **Stack:** FastAPI · Supabase (Postgres + Storage) · Groq LLMs · Pydantic
- **Auth:** none for the MVP — onboarding returns a `user_id` the client stores
  and passes on later requests.
- **Currency:** all money values are INR (₹).

---

## Table of contents

1. [Architecture at a glance](#1-architecture-at-a-glance)
2. [Prerequisites](#2-prerequisites)
3. [Setup — step by step](#3-setup--step-by-step)
4. [Environment variables](#4-environment-variables)
5. [Running the server](#5-running-the-server)
6. [Trying it end to end](#6-trying-it-end-to-end)
7. [Running the tests](#7-running-the-tests)
8. [Project structure](#8-project-structure)
9. [Deployment (Render)](#9-deployment-render)
10. [Troubleshooting](#10-troubleshooting)
11. [Further reading](#11-further-reading)

---

## 1. Architecture at a glance

A user onboards, uploads documents, then triggers a **run**. One run processes
**all** of that user's uploaded documents through four agents in order, each
reading its input from the database (keyed by `run_id`) and writing its output
back — the agents never call each other directly.

```
POST /onboarding    →  user_id
POST /documents     →  upload one file at a time (stored, not processed)
POST /pipeline/runs →  run_id  (202; pipeline runs in the background)
        │
        ├─ 1. parse       Document Parser   → transactions + financial_facts
        ├─ 2. categorize  Categorizer       → category + recurring/subscription flags
        ├─ 3. analyze     Financial Analysis→ metrics snapshot (pure math, no LLM)
        └─ 4. recommend   Recommendation    → summary + prioritized action cards
        │
GET  /pipeline/runs/{run_id}  →  poll status until "done"
GET  /dashboard/{user_id}     →  the composed dashboard payload
POST /chat                    →  grounded natural-language Q&A over the snapshot
```

| Layer | Location | Role |
|---|---|---|
| API routes | [app/api/routes/](app/api/routes/) | HTTP endpoints (thin) |
| Services | [app/services/](app/services/) | All Supabase reads/writes |
| Agents | [app/agents/](app/agents/) | The 4 pipeline stages |
| Orchestrator | [app/pipeline/](app/pipeline/) | Linear sequencer + status tracking |
| Core math | [app/core/finance/](app/core/finance/) | Pure metric/score calculations |
| LLM | [app/llm/](app/llm/) | Groq client (via `instructor`) + prompts |
| Models | [app/models/](app/models/) | Pydantic request/response/DB schemas |
| Config | [app/config.py](app/config.py) | Env-driven settings |

---

## 2. Prerequisites

- **Python 3.12** (Render pins `3.12.2`; anything 3.11+ should work locally).
- A **Supabase** project (free tier is fine) — provides Postgres + Storage.
- A **Groq** API key — get one at <https://console.groq.com>.
- Git.

No local database is needed — all persistence is in Supabase.

---

## 3. Setup — step by step

### 3.1 Clone and create a virtual environment

```powershell
git clone <repo-url>
cd finance-agent-backend

python -m venv venv
venv\Scripts\activate          # Windows (PowerShell)
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### 3.2 Set up Supabase

1. Create a project at <https://supabase.com>.
2. **Create the tables.** Open the project's **SQL Editor**, paste the contents
   of [db/schema.sql](db/schema.sql), and run it. This creates `users`,
   `documents`, `runs`, `transactions`, `financial_facts`,
   `financial_snapshots`, and `recommendations`.
3. **Create the Storage bucket.** Go to **Storage → New bucket**, name it exactly
   `documents`, and keep it **private**. Uploaded files are stored here and read
   back by the parser via `storage_path`.
4. **Grab your keys** (Project Settings → API):
   - Project URL → `SUPABASE_URL`
   - **Secret** (service-role) key → `SUPABASE_SECRET_KEY`. The backend uses the
     secret key so it bypasses row-level security — it must only ever run
     server-side.

### 3.3 Configure environment variables

```powershell
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
```

Then fill in `.env` (see [§4](#4-environment-variables)). At minimum you need:

```env
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_SECRET_KEY=<your-service-role-secret-key>
GROQ_API_KEY=<your-groq-key>
```

That's it — you're ready to run.

---

## 4. Environment variables

Settings are loaded from `.env` via `pydantic-settings`
([app/config.py](app/config.py)). Unknown keys are ignored.

| Variable | Required | Default | Purpose |
|---|:---:|---|---|
| `SUPABASE_URL` |  | — | Supabase project URL |
| `SUPABASE_SECRET_KEY` |  | — | Service-role key (server-side only; bypasses RLS) |
| `GROQ_API_KEY` |  | — | Groq LLM API key |
| `PARSER_GROQ_MODEL` | | `meta-llama/llama-4-scout-17b-16e-instruct` | Parser model (good free-tier TPM/TPD, reliable tool-calling) |
| `CATEGORIZER_GROQ_MODEL` | | `llama-3.1-8b-instant` | Cheap/fast model for the categorizer's LLM fallback |
| `RECOMMENDATION_GROQ_MODEL` | | `llama-3.3-70b-versatile` | Stronger model for advice quality |
| `CHAT_GROQ_MODEL` | | `meta-llama/llama-4-scout-17b-16e-instruct` | Chat model (generous rate limits) |
| `GROQ_MAX_TOKENS` | | `8000` | Max output tokens (keep ≤ 8192 for llama-4-scout) |
| `CORS_ORIGINS` | | `*` | Comma-separated allowed origins (`*` = allow all) |
| `SUPABASE_PUBLISHABLE_KEY` | | `null` | Reserved for future JWT auth; unused by the DB client |
| `SUPABASE_JWKS_URL` | | `null` | Reserved for future JWT auth |
| `KEEPALIVE_URL` / `RENDER_EXTERNAL_URL` | | — | If set, the app self-pings `/health` every 10 min so a free host doesn't sleep. Not needed locally. |

> The `.env.example` in the repo lists the Supabase keys; the three required
> above (`SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `GROQ_API_KEY`) are what you must
> provide. The rest have sensible defaults.

---

## 5. Running the server

```powershell
uvicorn app.main:app --reload
```

- API base: <http://127.0.0.1:8000>
- Interactive docs (Swagger UI): <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health> → `{"status":"ok"}`

`--reload` restarts on code changes (dev only). The pipeline runs via FastAPI
`BackgroundTasks` in-process, so no separate worker is required for the MVP.

---

## 6. Trying it end to end

The easiest way is the Swagger UI at `/docs`. The typical flow:

```
POST /onboarding                    → returns user_id
POST /documents      (multipart)    → once per file (doc_type + file)
POST /pipeline/runs  { user_id }    → returns run_id (202)
GET  /pipeline/runs/{run_id}        → poll (~1s) until status == "done"
GET  /dashboard/{user_id}           → the full dashboard payload
POST /chat           { user_id, messages[] }  → grounded assistant reply
```

Quick smoke test with `curl` (create a user):

```bash
curl -X POST http://127.0.0.1:8000/onboarding \
  -H "Content-Type: application/json" \
  -d '{"name":"Aarav Sharma","age":30,"monthly_income":97500,"dependents":0}'
```

Because agents read/write only through the DB keyed by `run_id`, re-running a
pipeline for a user never duplicates data — each run owns its own dataset.

The full request/response contract for every endpoint is in
[docs/api-reference.md](docs/api-reference.md).

---

## 7. Running the tests

The `tests/` directory holds end-to-end scripts that drive the real endpoints
(via an in-process FastAPI `TestClient`) and print each stage's output. They
require a working `.env` and the Supabase schema/bucket in place, and they make
real Groq calls.

```bash
# Parser — single document (deepest per-stage view: text → masked → LLM → rows)
python tests/test_parser_flow.py path/to/bank_statement.pdf --doc-type bank_statement

# Parser — every file in a folder under one run (doc_type inferred from filename)
python tests/test_parser_multi.py dummy_data/
python tests/test_parser_multi.py dummy_data/ --verbose   # full Groq JSON
python tests/test_parser_multi.py dummy_data/ --delay 5    # space calls to dodge rate limits

# Categorizer — over an already-parsed run
python tests/test_categorizer.py <run_id>

# Analysis — over a parsed + categorized run (prints the full metrics snapshot)
python tests/test_analysis.py <run_id>

# Recommendation & chat
python tests/test_recommendation.py <run_id>
python tests/test_chat.py <user_id>

# Full pipeline sanity check
python tests/verify_pipeline.py
```

> These are runnable scripts, not a `pytest` suite — invoke them directly with
> `python`. Most take a `run_id` or `user_id` from an earlier step.

---

## 8. Project structure

```
finance-agent-backend/
├── app/
│   ├── main.py                 # FastAPI app, /health, router wiring, keep-alive loop
│   ├── config.py               # env-driven Settings (pydantic-settings)
│   ├── api/
│   │   ├── deps.py             # shared FastAPI dependencies
│   │   └── routes/             # onboarding, documents, pipeline, dashboard, chat
│   ├── agents/                 # base + parser / categorizer / analysis / recommendation
│   ├── pipeline/               # stages.py (Stage enum) + orchestrator.py (sequencer)
│   ├── core/
│   │   ├── security.py         # PII masking before any LLM call
│   │   └── finance/            # pure metric/score calculations + projections
│   ├── llm/                    # Groq client (instructor) + per-agent prompts
│   ├── models/                 # Pydantic models (requests, responses, DB shapes)
│   ├── services/               # all Supabase reads/writes (one module per concern)
│   └── db/supabase_client.py   # cached Supabase client factory
├── db/schema.sql               # full Postgres schema — run once in Supabase
├── docs/                       # architecture + API docs (see §11)
├── tests/                      # end-to-end runnable scripts
├── requirements.txt
├── render.yaml                 # Render Blueprint for deployment
├── .env.example
└── README.md
```

---

## 9. Deployment (Render)

The repo ships a [render.yaml](render.yaml) Blueprint.

1. On Render: **New → Blueprint**, connect this repo. Render reads `render.yaml`.
2. It provisions a free Python web service with:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health check: `/health`
3. Enter the **secret** env vars in the dashboard when prompted (`sync: false`):
   `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `GROQ_API_KEY`. Non-secret model/CORS
   settings are already declared in the file.
4. Free instances sleep after ~15 min idle. Render injects `RENDER_EXTERNAL_URL`,
   which the app uses to self-ping `/health` every 10 minutes so it stays warm
   (see [app/main.py](app/main.py)). Set `CORS_ORIGINS` to your deployed frontend
   URL once it's live.

---

## 10. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| App fails to start, validation error on `Settings` | A required env var (`SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `GROQ_API_KEY`) is missing from `.env`. |
| Upload succeeds but parse stage fails | The Storage bucket isn't named exactly `documents`, or it doesn't exist / isn't accessible with the secret key. |
| `relation "public.users" does not exist` (or similar) | You didn't run [db/schema.sql](db/schema.sql) in the Supabase SQL editor. |
| Groq `429` / rate-limit during parsing | Free-tier TPM/TPD limits. Space out documents (`--delay` in the multi-parser test) or switch models via `PARSER_GROQ_MODEL`. |
| `tool_use_failed` / truncated extraction | A very large statement exceeds `GROQ_MAX_TOKENS`. Chunking by page isn't implemented yet — try a smaller statement. |
| `.png/.jpg` upload marked `failed` | Expected — OCR isn't enabled yet; image parsing raises "OCR not enabled." |
| Run stuck in `running` after a restart | `BackgroundTasks` is in-process; a mid-run server restart orphans that run. Trigger a new run. |

---

## 11. Further reading

The [docs/](docs/) directory has the deep dives:

| Doc | What it covers |
|---|---|
| [api-reference.md](docs/api-reference.md) | Complete endpoint contract + data models + enums |
| [frontend-brief.md](docs/frontend-brief.md) | Product vision, screens, and design language |
| [pipeline-orchestration.md](docs/pipeline-orchestration.md) | The orchestrator, run/stage model, background execution |
| [parser-agent.md](docs/parser-agent.md) | Agent 1 — extraction, PII masking, per-doc-type behaviour |
| [categorizer-agent.md](docs/categorizer-agent.md) | Agent 2 — hybrid rules + LLM categorization, recurring detection |
| [analysis-agent.md](docs/analysis-agent.md) | Agent 3 — pure-math metrics, health score, dashboard fields |
