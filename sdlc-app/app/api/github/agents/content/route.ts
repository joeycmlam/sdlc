import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const sourceRepo = url.searchParams.get("source_repo");
  const path = url.searchParams.get("path");
  if (!sourceRepo || !path) {
    return NextResponse.json(
      { error: "source_repo and path are required" },
      { status: 400 },
    );
  }
  const qs = new URLSearchParams({ source_repo: sourceRepo, path }).toString();
  try {
    const res = await fetch(`${BACKEND}/github/agents/content?${qs}`, {
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: `Backend unreachable: ${(err as Error).message}` },
      { status: 502 },
    );
  }
}
