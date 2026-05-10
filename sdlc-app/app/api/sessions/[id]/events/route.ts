import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Long-lived SSE — disable static optimisation and Vercel edge buffering.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    const upstream = await fetch(
      `${BACKEND}/sessions/${encodeURIComponent(id)}/events`,
      { cache: "no-store" },
    );
    if (!upstream.ok || !upstream.body) {
      return NextResponse.json(
        { error: `Backend returned ${upstream.status}` },
        { status: upstream.status },
      );
    }
    return new NextResponse(upstream.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    return NextResponse.json(
      { error: `Backend unreachable: ${(err as Error).message}` },
      { status: 502 },
    );
  }
}
