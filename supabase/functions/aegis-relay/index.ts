/**
 * AegisRelay — ingest relay text into OpenBrain `thoughts` (embedding via OpenRouter).
 *
 * Secrets (Dashboard → Edge Functions → aegis-relay → Secrets):
 *   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (auto-injected on hosted runtime)
 *   OPENROUTER_API_KEY
 *   OPENBRAIN_SYNC_TOKEN — must match `Authorization: Bearer …` (same value as Python OB sync)
 *
 * Deploy: `supabase functions deploy aegis-relay`
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

/** Reject unless `Authorization: Bearer` matches `OPENBRAIN_SYNC_TOKEN`. */
function authorizeOpenBrain(req: Request): Response | null {
  const expected = Deno.env.get("OPENBRAIN_SYNC_TOKEN");
  if (!expected) {
    return jsonResponse(
      { error: "Server misconfiguration: OPENBRAIN_SYNC_TOKEN not set" },
      500,
    );
  }
  const auth = req.headers.get("Authorization");
  if (!auth || !auth.toLowerCase().startsWith("bearer ")) {
    return jsonResponse({ error: "Missing or invalid Authorization header" }, 401);
  }
  const token = auth.slice(7).trim();
  if (token !== expected) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }
  return null;
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

  const authErr = authorizeOpenBrain(req);
  if (authErr) return authErr;

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
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceKey) {
    return jsonResponse(
      { error: "Server misconfiguration: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing" },
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

  const supabase = createClient(supabaseUrl, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
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
