import { NextResponse } from "next/server";

export async function GET() {
  // Try to reach the Python backend, fallback to mock if unavailable
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/health`, {
      next: { revalidate: 0 },
    });
    if (response.ok) {
      return NextResponse.json(await response.json());
    }
  } catch {
    // Backend not available, return mock response
  }

  return NextResponse.json({ status: "ok", mode: "mock" });
}
