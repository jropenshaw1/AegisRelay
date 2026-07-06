/**
 * AegisRelay — ingest relay text into OpenBrain `thoughts` (embedding via OpenRouter).
 *
 * Secrets (set via `supabase secrets set`):
 *   SUPABASE_URL          (auto-injected on hosted runtime)
 *   OB_SUPABASE_SECRET    (opaque sb_secret_* key — shared across all projects)
 *   OPENROUTER_API_KEY
 *
 * Auth: callers send `apikey: <OB_SUPABASE_SECRET>` header.
 * Gateway JWT verification disabled (`--no-verify-jwt`).
 *
 * Deploy: `supabase functions deploy aegis-relay --no-verify-jwt --use-api`
 */

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "@supabase/supabase-js";

const OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings";
const EMBED_MODEL = "openai/text-embedding-3-small";

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function defaultMetadata(): Record<string, unknown> {
  return {
    type: "reference",
    topics: ["aegisrelay", "relay-result"],
    people: [],
    action_items: [],
    dates_mentioned: [],
    source: "aegisrelay",
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

/** Verify inbound `apikey` header against OB_SUPABASE_SECRET. */
function verifyApiKey(req: Request): boolean {
  const apikey = req.headers.get("apikey");
  const expected = Deno.env.get("OB_SUPABASE_SECRET");

  if (!expected) {
    throw new Error(
      "[auth] OB_SUPABASE_SECRET not set. " +
      'Run: supabase secrets set OB_SUPABASE_SECRET="<sb_secret_key>"',
    );
  }

  if (!apikey) return false;

  // Constant-time comparison
  if (apikey.length !== expected.length) return false;
  const a = new TextEncoder().encode(apikey);
  const b = new TextEncoder().encode(expected);
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a[i] ^ b[i];
  }
  return diff === 0;
}

async function embedOpenRouter(
  apiKey: string,
  text: string,
): Promise<number[]> {
  const res = await fetch(OPENROUTER_EMBED_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: EMBED_MODEL,
      input: text,
    }),
  });
  const rawText = await res.text();
  if (!res.ok) {
    throw new Error(`OpenRouter embeddings HTTP ${res.status}: ${rawText.slice(0, 500)}`);
  }
  const raw = JSON.parse(rawText) as {
    data?: Array<{ embedding?: unknown }>;
  };
  const emb = raw.data?.[0]?.embedding;
  if (!Array.isArray(emb)) {
    throw new Error("OpenRouter response missing data[0].embedding");
  }
  return emb.map((x) => Number(x));
}

function mergeMetadata(incoming: unknown): Record<string, unknown> {
  const base = defaultMetadata();
  if (
    incoming !== undefined && incoming !== null && typeof incoming === "object" &&
    !Array.isArray(incoming)
  ) {
    for (const [k, v] of Object.entries(incoming as Record<string, unknown>)) {
      base[k] = v;
    }
  }
  return base;
}

interface IngestBody {
  content?: unknown;
  metadata?: unknown;
}

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const url = new URL(req.url);
  const path = url.pathname;

  if (req.method === "GET") {
    const health =
      path.endsWith("/health") || url.searchParams.get("health") === "1";
    return jsonResponse({
      ok: true,
      function: "aegis-relay",
      ...(health ? { health: "ok" as const } : {}),
    });
  }

  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  if (!verifyApiKey(req)) {
    return jsonResponse(
      { error: "Missing or invalid apikey header" },
      401,
    );
  }

  let body: IngestBody;
  try {
    body = (await req.json()) as IngestBody;
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  if (typeof body.content !== "string" || !body.content.trim()) {
    return jsonResponse({ error: "Field \"content\" is required and must be a non-empty string" }, 400);
  }

  const content = body.content.trim();
  const metadata = mergeMetadata(body.metadata);

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const obKey = Deno.env.get("OB_SUPABASE_SECRET");
  if (!supabaseUrl || !obKey) {
    return jsonResponse(
      { error: "Server misconfiguration: SUPABASE_URL or OB_SUPABASE_SECRET missing" },
      500,
    );
  }

  const openrouterKey = Deno.env.get("OPENROUTER_API_KEY");
  let embedding: number[] | null = null;
  if (openrouterKey) {
    try {
      embedding = await embedOpenRouter(openrouterKey, content);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return jsonResponse({ error: "Embedding failed", detail: msg }, 502);
    }
  }

  const supabase = createClient(supabaseUrl, obKey, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: {
      headers: {
        apikey: obKey,
      },
    },
  });

  const row: Record<string, unknown> = {
    content,
    metadata,
    embedding,
  };

  const { data, error } = await supabase
    .from("thoughts")
    .insert(row)
    .select()
    .single();

  if (error) {
    return jsonResponse(
      { error: "Insert failed", detail: error.message, code: error.code },
      500,
    );
  }

  return jsonResponse({ ok: true, thought: data }, 201);
});
