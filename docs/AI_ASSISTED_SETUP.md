# Build AegisRelay with an AI Coding Tool

## The Short Version

Point your AI coding tool at this repo and tell it to walk you through the [setup guide](GETTING_STARTED.md). That's it. The guide has every command, every config step, every expected output — your AI reads it and helps you execute each one.

This works in Cursor, Claude Code, Codex, Windsurf, or any AI coding tool that can read files. You don't need to copy-paste from a browser or follow along manually. Let your AI be your pair programmer through the whole build.

## Before You Start — Open Brain Is Required

AegisRelay writes to an **Open Brain** memory store. If you don't have one yet, set it up first:

- **AI-assisted (fastest):** [Build Your Open Brain with an AI Coding Tool](https://github.com/NateBJones-Projects/OB1/blob/main/docs/04-ai-assisted-setup.md)
- **Windows manual:** [Open Brain Setup Guide (Windows)](https://github.com/NateBJones-Projects/OB1/blob/main/docs/open-brain-guide-windows-tabbed.xlsx)
- **Mac manual:** [Open Brain Setup Guide (Mac)](https://github.com/NateBJones-Projects/OB1/blob/main/docs/open-brain-guide-mac.xlsx)

Once your Open Brain is running (you can capture and search thoughts), come back here.

## How to Start

1. Clone or open this repo in your AI coding tool
2. Tell it: **"Read `docs/GETTING_STARTED.md` and walk me through setting up AegisRelay step by step."**
3. Follow along. It handles the code parts. You handle the clicking (Supabase dashboard, OpenRouter signup if you haven't already).

That's the whole workflow. The sections below cover what to watch out for.

## What Your AI Handles Well

- **Python environment setup** — Creating the virtual environment, installing dependencies, running tests. Your AI can run these directly if your tool supports terminal access.
- **CLI commands** — Linking your Supabase project, setting secrets, deploying the Edge Function. Straightforward terminal work.
- **Smoke testing** — Your AI can build and run the POST request to verify the deployment, then check your `thoughts` table for the new row.
- **Debugging** — When something doesn't work, your AI can read Edge Function logs and help diagnose the issue. This is where the AI-assisted path genuinely shines over going solo.

## What You Should Do Manually

Some steps involve clicking through web UIs where your AI can't help directly. These are fast but you need to do them yourself:

- **Supabase dashboard** — Copying your project ref, project URL, and service role key from Settings → API. Checking Table Editor for your test row.
- **Generating your sync token** — Use your password manager's "generate" feature to create a long random string. Your AI can tell you what to do with it, but you need to create and save the value yourself.
- **OpenRouter** — If you don't already have an API key from Open Brain setup, sign up and create one at openrouter.ai.

Your AI can tell you exactly what to click and where — it just can't click for you.

## Common Gotchas

### Don't let your AI improvise when it can't read the source

If your AI can't access a file or section, it will make something up rather than tell you it's stuck. Now that the full guide lives in this repo, this shouldn't happen — your AI can read everything. But if your AI is generating setup code from scratch instead of referencing `docs/GETTING_STARTED.md`, stop it and point it back to the file.

### Configuration problems need configuration fixes

When something breaks, your AI's instinct is to rewrite code. Resist this. The Edge Function code in this repo works. Problems are almost always configuration:

- A secret that doesn't match (`npx supabase secrets list` to check)
- A bearer token with extra spaces
- Running `supabase link` from the wrong directory
- A step that got skipped

Check Edge Function logs first (Supabase dashboard → Edge Functions → aegis-relay → Logs). Paste the error to your AI and let it diagnose — but don't let it start rewriting the function code unless the logs point to an actual code problem.

### Keep your credential tracker open

The [setup guide](GETTING_STARTED.md) has a credential tracker template near the top. Copy it into a text file before you start. Your AI can remind you to fill it in as you go, but you need to actually save the values somewhere it can reference later.

### Part 1 is independent of Part 2

You can run the Python tests (Part 1) without touching Supabase at all. They use SQLite in memory. If Part 1 passes (51 passed, 1 skipped), the code works. Part 2 is purely about deploying the live endpoint.

## Tips

- **Go step by step.** Don't ask your AI to "set up the whole thing." Walk through Part 1 (Python tests), verify it passes, then do Part 2 (Supabase deploy). The guide is structured this way for a reason.
- **Test at Step 8.** The guide has a specific smoke test command and expected response. Do it. If the POST returns 201 and a row appears in `thoughts`, everything is wired correctly.
- **Use Supabase's built-in AI too.** The Supabase dashboard has its own AI assistant (chat icon, bottom-right). It knows Supabase's docs inside out. Your coding AI handles the big picture; the Supabase AI handles Supabase-specific questions.
- **Reuse your Open Brain values.** Same Supabase project, same OpenRouter key, same `thoughts` table. AegisRelay is an extension of Open Brain, not a separate system.

## After Setup

Your AegisRelay endpoint is live. Any trusted client that sends the right bearer token can now write structured thoughts to your Open Brain over HTTPS. From here you can integrate it into AI agent workflows, build relay pipelines, or explore the governance pipeline in the Python codebase.

---

*Modeled on Nate Jones's [AI-assisted setup guide for Open Brain](https://github.com/NateBJones-Projects/OB1/blob/main/docs/04-ai-assisted-setup.md). If you build AegisRelay with an AI coding tool, open an issue and share how it went.*
