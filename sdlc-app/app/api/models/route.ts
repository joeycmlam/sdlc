import { NextRequest, NextResponse } from "next/server";

/**
 * Fallback list used only when the backend is unreachable.  Authoritative list
 * comes from the backend's `/models` endpoint, which queries the local Copilot
 * CLI via `models.list`. Keep this short — it's a graceful-degradation list,
 * not a source of truth.
 */
const FALLBACK_MODELS = [
  { id: "claude-sonnet-4.5", name: "Claude Sonnet 4.5", billing_multiplier: 1.0 },
  { id: "claude-haiku-4.5", name: "Claude Haiku 4.5", billing_multiplier: 0.33 },
  { id: "gpt-5.2", name: "GPT-5.2", billing_multiplier: 1.0 },
  { id: "gpt-5-mini", name: "GPT-5 mini", billing_multiplier: 0.0 },
];

export async function GET(request: NextRequest) {
  const refresh = request.nextUrl.searchParams.get("refresh") === "true";
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const url = `${backendUrl}/models${refresh ? "?refresh=true" : ""}`;
    const response = await fetch(url, { next: { revalidate: 0 } });
    if (response.ok) {
      return NextResponse.json(await response.json());
    }
  } catch {
    // Backend not available — fall through to local fallback.
  }

  return NextResponse.json({ models: FALLBACK_MODELS, cached: false, source: "fallback" });
}
