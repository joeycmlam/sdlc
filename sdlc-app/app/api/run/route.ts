import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json();

  // Try to reach the Python backend first
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (response.ok) {
      return NextResponse.json(await response.json());
    }
  } catch {
    // Backend not available, use mock response
  }

  // Mock response
  return NextResponse.json({
    content: `Mock response for instruction: "${body.instruction}"\n\nThe backend API server is not running. Start it with:\n\ncd app/copilot-agent && python api_server.py`,
  });
}
