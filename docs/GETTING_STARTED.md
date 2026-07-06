# Getting Started with AegisRelay

This guide walks you through running the **Python project** on your machine so you know the relay works end to end. OpenBrain sync is handled by the governed relay pipeline, not by a separate deployment surface.

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
- Your `thoughts` table (AegisRelay syncs governed records into it)
- Your OpenRouter API key (for embeddings — same key, same model)
- Your Supabase service role key

---

## What you're building (in one minute)

- **On your laptop:** You download this repo, create a small Python environment, install dependencies, and run automated tests. That proves the relay logic and database code behave as expected (using a temporary SQLite file — nothing leaves your computer).

- **For OpenBrain integration:** The governed sync path is `ob_sync_worker.py`, which runs after relay persistence and embedding completion. There is no separate direct-to-OpenBrain deployment surface.

---

## If you get stuck

Supabase's own assistant lives in the dashboard (usually a chat icon in the **bottom-right**). Paste error messages from the SQL editor, the terminal, or worker/runtime logs. It cannot see your screen, but it can walk you through clicks and explain output line by line.

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

OPENROUTER (same key as Open Brain)
  API key:                     ____________________  ← openrouter.ai/keys

LOCAL MACHINE ONLY (.env — never commit)
  DATABASE_URL:               ____________________  ← only if you run optional Postgres tests
--------------------------------------

💡 **Seriously — paste the tracker into a file now.** You'll want these values handy when configuring relay + OpenBrain integration.
```

---

## What you need installed

| Thing | Why |
|--------|-----|
| **Python 3.11 or newer** | Runs the relay code and tests. (The project metadata still allows 3.10; 3.11+ is easier.) |
| **Git** | To clone the repository. |
| **A working Open Brain instance** | AegisRelay writes to your existing `thoughts` table. See prerequisites above. |
| **OpenRouter account** (optional) | For embeddings in the governed sync path. You likely already have this from Open Brain setup. |

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

> **Key step — what "good" looks like:** Run `pytest` to verify all tests pass. A Postgres-specific test may be skipped when `DATABASE_URL` is not set.

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

# OpenBrain sync

OpenBrain sync is handled by `ob_sync_worker.py` as part of the relay pipeline. No separate deployment is required. See relay setup instructions above.

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

---

## Environment variables (cheat sheet)

Use **`.env.example`** as a starting point on your machine. **Never commit** a filled `.env`.

| Variable | You need it when… |
|----------|-------------------|
| `DATABASE_URL` | Optional Postgres tests or Postgres-backed runs. |
| `OPENAI_API_KEY` | Running the Python embedding worker with OpenAI. |
| `PERPLEXITY_API_KEY` | Live Perplexity calls; without it, the adapter returns a stub echo. |
| `OPENROUTER_API_KEY` | Optional embeddings for the Python OpenBrain sync path. |
| `OPENBRAIN_SYNC_URL` | Python worker posting to your Supabase REST API. |
| `OPENBRAIN_SYNC_TOKEN` | Auth token for the governed OpenBrain sync path, if your deployment uses one. |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Supabase credentials used by the governed sync path; never paste them into client apps. |

---

## Quick troubleshooting

| Symptom | What to try |
|---------|-------------|
| `pytest` not found | Activate `.venv` again; reinstall with `pip install -e ".[dev]"`. |
| Postgres test skipped | Normal without `DATABASE_URL`. |
| OpenBrain sync not happening | Confirm outbox rows exist, embeddings complete when required, and your sync credentials are configured for `ob_sync_worker.py`. |
| 502-style embedding failures | Check your OpenRouter key, credits, or model availability in the worker/runtime logs. |
| Insert fails | Confirm `thoughts` table exists and that the governed sync path has valid Supabase credentials. |

---

You're done when Part 1 shows all tests passing and the governed OpenBrain sync path is configured for your environment. Everything else is optional depth.
