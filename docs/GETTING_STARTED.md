# Getting Started with AegisRelay

This guide walks you through two things: running the **Python project** on your machine (so you know it works), and deploying the **Supabase Edge Function** that can save relay text into your Open Brain `thoughts` table. You can stop after Part 1 if you only want the code; Part 2 is for "live" ingest over HTTPS.

**Who this is for:** You are comfortable opening a terminal and copying commands, but you do not need to be a senior engineer. When something sounds technical, we explain it in plain language first.

**Prefer an AI-assisted walkthrough?** See [`AI_ASSISTED_SETUP.md`](AI_ASSISTED_SETUP.md) — point your AI coding tool at this file and let it guide you step by step.

---

## Before You Start — Open Brain Is Required

AegisRelay writes to an **Open Brain** memory store. Open Brain is a Supabase-backed persistent memory system with a `thoughts` table, embeddings, and MCP integration. **You must have a working Open Brain instance before proceeding.**

If you don't have Open Brain yet, set it up first using Nate Jones's guides:

- **Windows:** [Open Brain Setup Guide (Windows)](https://github.com/NateBJones-Projects/OB1/blob/main/docs/open-brain-guide-windows-tabbed.xlsx)
- **Mac:** [Open Brain Setup Guide (Mac)](https://github.com/NateBJones-Projects/OB1/blob/main/docs/open-brain-guide-mac.xlsx)
- **AI-assisted setup:** [Build Your Open Brain with an AI Coding Tool](https://github.com/NateBJones-Projects/OB1/blob/main/docs/04-ai-assisted-setup.md) — the fastest path if you have Cursor, Claude Code, or any AI coding tool

Once your Open Brain is running (you can capture and search thoughts), come back here.

**What you'll reuse from Open Brain setup:**
- Your Supabase project (same project ref, same URL)
- Your `thoughts` table (AegisRelay writes to it)
- Your OpenRouter API key (for embeddings — same key, same model)
- Your Supabase service role key

---

## What you're building (in one minute)

- **Part 1 — On your laptop:** You download this repo, create a small Python environment, install dependencies, and run automated tests. That proves the relay logic and database code behave as expected (using a temporary SQLite file — nothing leaves your computer).

- **Part 2 — On Supabase:** You connect this repo to your Supabase project, upload the `aegis-relay` Edge Function, and set a couple of secrets. After that, any trusted client can `POST` JSON to a URL you get from Supabase; the function checks a **shared password** (called a *bearer token*), optionally asks OpenRouter for an embedding, and inserts a row into `thoughts`.

---

## If you get stuck

Supabase's own assistant lives in the dashboard (usually a chat icon in the **bottom-right**). Paste error messages from the SQL editor, the terminal, or **Edge Functions → Logs**. It cannot see your screen, but it can walk you through clicks and explain output line by line.

---

## Credential tracker — copy this first

You will create or look up several values. **Do not rely on memory.** Copy the block below into Notes, Notepad, or any text file and fill it in as you go. Each line says roughly *when* you'll need it.

```
AEGISRELAY — CREDENTIAL TRACKER
Keep this file private. Fill in as you go.
--------------------------------------

FROM YOUR SUPABASE DASHBOARD (same as Open Brain)
  Project name (optional):     ____________________
  Project ref:                 ____________________  ← Part 2, Step 4
  Project URL:                 ____________________  ← Settings → API (same as Open Brain)
  Service role key:            ____________________  ← Settings → API (reveal & copy)
                               ⚠️ Treat like a password — full database access.

YOU CHOOSE (shared secret for the Edge function)
  OPENBRAIN_SYNC_TOKEN:       ____________________  ← Part 2, Step 5
                               Invent a long random string. Every client must send:
                               Authorization: Bearer <exactly this value>

OPENROUTER (same key as Open Brain)
  API key:                     ____________________  ← openrouter.ai/keys

AFTER DEPLOY
  Edge function URL:           ____________________  ← Part 2, Step 7
                               Looks like:
                               https://YOUR_PROJECT_REF.supabase.co/functions/v1/aegis-relay

LOCAL MACHINE ONLY (.env — never commit)
  DATABASE_URL:               ____________________  ← only if you run optional Postgres tests
--------------------------------------

💡 **Seriously — paste the tracker into a file now.** You'll need the project ref and URLs in quick succession during Part 2.
```

---

## What you need installed

| Thing | Why |
|--------|-----|
| **Python 3.11 or newer** | Runs the relay code and tests. (The project metadata still allows 3.10; 3.11+ is easier.) |
| **Node.js 18+** | Lets you run `npx supabase` without installing the CLI globally. |
| **Git** | To clone the repository. |
| **A working Open Brain instance** | AegisRelay writes to your existing `thoughts` table. See prerequisites above. |
| **OpenRouter account** (optional) | For embeddings in the Edge Function. You likely already have this from Open Brain setup. Without it, rows still insert — `embedding` will be empty until you add a key later. |

---

# Part 1 — Python on your computer

Work through these steps in order. **Key steps** are called out so you don't skip something that breaks the next step.

### Step 1: Get the code

```bash
git clone https://github.com/jropenshaw1/AegisRelay.git
cd AegisRelay
```

> **Key step:** Run every following command from inside the `AegisRelay` folder (the one that contains `pyproject.toml` and `src`).

### Step 2: Create a virtual environment

A *virtual environment* is an isolated Python folder so this project's packages don't clash with other projects.

```bash
python -m venv .venv
```

**Activate it:**

- **macOS or Linux:**

```bash
source .venv/bin/activate
```

- **Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of your terminal line. If Windows blocks the script, you may need to allow scripts for your user once (search "PowerShell execution policy" — or use Command Prompt with `.venv\Scripts\activate.bat`).

> **Key step:** If `python` doesn't work, try `py -m venv .venv` on Windows or `python3` on macOS.

### Step 3: Install the project and test tools

```bash
pip install -e ".[dev]"
```

That installs AegisRelay in *editable* mode (code changes on disk are picked up immediately) and pulls in **pytest** for tests.

### Step 4: Optional — copy the environment template

```bash
cp .env.example .env
```

On Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

For **Part 1 only**, you can skip filling `.env`. The default tests use SQLite in memory / temp files.

### Step 5: Run the test suite

```bash
pytest tests/
```

> **Key step — what "good" looks like:** You should see **51 passed**, **1 skipped**. The skipped test is for **Postgres**; it only runs when `DATABASE_URL` is set. Skipping is normal on a fresh laptop.

If you see errors about missing `pytest`, your virtual environment may not be active — go back to Step 2.

### Step 6 (optional) — Run the Postgres tests too

Only do this if you have a Postgres URL and want to exercise the production-style database code.

```bash
pip install -e ".[dev,postgres]"
```

Put your connection string in `.env` as `DATABASE_URL=...`, then run:

```bash
pytest tests/
```

---

# Part 2 — Deploy the Edge Function to Supabase

This part uses the **Supabase CLI** through `npx`, so you don't have to install anything globally.

> **Key idea — how the function knows it's you:**
> You invent a long secret (`OPENBRAIN_SYNC_TOKEN`) and store it in Supabase **Edge Function secrets**. When something calls your function, it must send a header:
> `Authorization: Bearer <that same secret>`
> If the header is missing or wrong, you get **401 Unauthorized**. This is separate from Supabase's "anon" key — you are not putting the service role key in the browser.

### Step 1: Open a terminal in the repo root

The folder must contain **`supabase/config.toml`**. If you `cd` into `supabase` by mistake, go up one level.

### Step 2: Check that the CLI runs

```bash
npx supabase --version
```

If this fails, install or update **Node.js** (LTS from nodejs.org is fine).

### Step 3: Log in to Supabase (first time only)

If you have never used the CLI on this machine:

```bash
npx supabase login
```

Follow the browser prompt. This saves a token so `link` and `deploy` can talk to your account.

### Step 4: Find your project ref

1. Open [supabase.com](https://supabase.com) and open your project.
2. Look at the browser URL. It looks like:
   `https://supabase.com/dashboard/project/abcdefghijklmnop`
3. The part after `/project/` is your **project ref** — copy it into the credential tracker.

### Step 5: Link this repo to that project

```bash
npx supabase link --project-ref YOUR_PROJECT_REF
```

Replace `YOUR_PROJECT_REF` with the value from your tracker. The CLI may ask for your **database password** (the one you set when you created the project).

> **Key step:** Linking ties the local `supabase` folder to *your* cloud project. You must do this from **this** cloned AegisRelay repo.

### Step 6: Invent and set your sync token + OpenRouter

1. Generate a long random string for `OPENBRAIN_SYNC_TOKEN` (password manager "generate" is perfect). Paste it into your credential tracker.
2. Copy your OpenRouter API key (same one you use for Open Brain).

Push them to Supabase as **secrets** (hosted Edge Functions read these securely):

```bash
npx supabase secrets set OPENBRAIN_SYNC_TOKEN=paste-your-token-here OPENROUTER_API_KEY=paste-your-openrouter-key-here
```

⚠️ **Do not** paste your **service role key** into chat apps or client-side code. The Edge runtime already receives `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` automatically on Supabase's servers — you normally **do not** set those with `secrets set` for this function.

If you skip OpenRouter for now, you can set only the sync token:

```bash
npx supabase secrets set OPENBRAIN_SYNC_TOKEN=paste-your-token-here
```

### Step 7: Deploy the function

```bash
npx supabase functions deploy aegis-relay
```

This repo's config sets **`verify_jwt = false`** for `aegis-relay` so your **custom** bearer token works. If deploy succeeds but calls fail with a JWT-related error, try:

```bash
npx supabase functions deploy aegis-relay --no-verify-jwt
```

> **Key step:** When deploy finishes, copy the **function URL** into your tracker. Pattern:
> `https://<project-ref>.supabase.co/functions/v1/aegis-relay`

You can also confirm in the dashboard: **Edge Functions** → **aegis-relay**.

### Step 8: Smoke test — did it work?

Replace placeholders with values from your tracker.

**Using curl (macOS, Linux, or Windows with Git Bash):**

```bash
curl -sS -X POST "https://YOUR_PROJECT_REF.supabase.co/functions/v1/aegis-relay" \
  -H "Authorization: Bearer YOUR_OPENBRAIN_SYNC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"Hello from my first AegisRelay test"}'
```

**Using PowerShell:**

```powershell
$uri = "https://YOUR_PROJECT_REF.supabase.co/functions/v1/aegis-relay"
$headers = @{
  "Authorization" = "Bearer YOUR_OPENBRAIN_SYNC_TOKEN"
  "Content-Type"  = "application/json"
}
$body = '{"content":"Hello from my first AegisRelay test"}'
Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body
```

> **Key step — success:** You want HTTP **201** and JSON containing `"ok": true` and a `"thought"` object. In Supabase, open **Table Editor → thoughts** and you should see a new row.

**Quick health check (GET, no body):**

```bash
curl -sS "https://YOUR_PROJECT_REF.supabase.co/functions/v1/aegis-relay"
```

---

## API reference — `aegis-relay` (short)

**URL:** `https://<project-ref>.supabase.co/functions/v1/aegis-relay`

**Headers**

- `Authorization: Bearer <OPENBRAIN_SYNC_TOKEN>` — required.
- `Content-Type: application/json` — required for `POST`.

**POST body (JSON)**

| Field | Required | What it does |
|--------|----------|----------------|
| `content` | Yes | The text stored in `thoughts.content`. Must be a non-empty string. |
| `metadata` | No | A JSON object merged into `thoughts.metadata`. If you omit it, the server fills in defaults such as `type`, `topics`, and `source: "aegisrelay"`. You can add your own keys the same way you do in Open Brain. |

**Example body**

```json
{
  "content": "Notes from today's relay run.",
  "metadata": {
    "type": "reference",
    "topics": ["aegisrelay", "daily"]
  }
}
```

**Success (201)**

```json
{
  "ok": true,
  "thought": { "id": "...", "content": "...", "metadata": {}, "embedding": null }
}
```

**Common errors**

| Code | Meaning |
|------|---------|
| **400** | Bad JSON or missing / empty `content`. |
| **401** | Wrong or missing `Authorization` header. |
| **500** | Server misconfiguration (e.g. secret not set). |
| **502** | Embedding failed (check OpenRouter key and credits). |

If `OPENROUTER_API_KEY` is not set, the row still saves with `embedding: null`.

---

## How the repo is organized (big picture)

You do not need to read every file. This is so you know where to look later.

| Area | Plain-English role |
|------|---------------------|
| **`src/aegisrelay/models/`** | Data shapes (requests, responses, memory rows). |
| **`src/aegisrelay/governance/`** | Rules and the **eight-step pipeline** that runs after a provider answers (normalize text, split into segments, classify trust, flag uncertainty, time-based expiry hints, light redaction stub, dedupe, then hand off to persistence). |
| **`src/aegisrelay/adapters/`** | Talks to AI providers (e.g. Perplexity) and turns answers into one standard format. |
| **`src/aegisrelay/admin/`** | Saves relays, governance events, and "outbox" jobs in the database. |
| **`src/aegisrelay/db/`** | **SQLite** for local/tests; **Postgres** for real deployments. |
| **`src/aegisrelay/workers/`** | Background-style workers: embeddings and syncing toward Open Brain. |
| **`src/aegisrelay/relay_service.py`** | Wires the whole Python flow together. |
| **`supabase/functions/aegis-relay/`** | The Edge Function you deployed in Part 2. |

---

## Environment variables (cheat sheet)

Use **`.env.example`** as a starting point on your machine. **Never commit** a filled `.env`.

| Variable | You need it when… |
|----------|-------------------|
| `DATABASE_URL` | Optional Postgres tests or Postgres-backed runs. |
| `OPENAI_API_KEY` | Running the Python embedding worker with OpenAI. |
| `PERPLEXITY_API_KEY` | Live Perplexity calls; without it, the adapter returns a stub echo. |
| `OPENROUTER_API_KEY` | Edge Function embeddings and optional Python OB sync path. |
| `OPENBRAIN_SYNC_URL` | Python worker posting to your Supabase REST API. |
| `OPENBRAIN_SYNC_TOKEN` | Must match the bearer token the Edge Function expects. |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Automatically provided **inside** hosted Edge Functions — not something you paste into client apps. |

---

## Quick troubleshooting

| Symptom | What to try |
|---------|-------------|
| `pytest` not found | Activate `.venv` again; reinstall with `pip install -e ".[dev]"`. |
| 51 passed, 1 skipped | Normal without `DATABASE_URL`. |
| `supabase link` fails | Run `npx supabase login`; confirm project ref; use correct database password. |
| 401 from Edge Function | Header must be exactly `Bearer ` + your `OPENBRAIN_SYNC_TOKEN` (no extra spaces). |
| 502 embedding failed | OpenRouter key, credits, or model availability — check Edge **Logs**. |
| Insert fails | Confirm `thoughts` table exists and columns match what the function inserts (`content`, `metadata`, `embedding`). |

---

You're done when Part 1 shows **51 passed, 1 skipped** and Part 2 returns **201** with a new row in `thoughts`. Everything else is optional depth.
