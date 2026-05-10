import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json();

  // Try to reach the Python backend first
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (response.ok && response.body) {
      // Proxy the SSE stream
      return new NextResponse(response.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }
  } catch {
    // Backend not available, use mock response
  }

  // Mock streaming response
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const chunks = [
        { type: "chunk", content: "I'm analyzing your request" },
        { type: "chunk", content: "..." },
        { type: "chunk", content: "\n\n" },
        { type: "tool", name: "bash_exec" },
        { type: "chunk", content: "Executing command to gather information.\n\n" },
        { type: "chunk", content: "**Note:** The backend API server is not currently running.\n\n" },
        { type: "chunk", content: "To connect to the real Copilot Agent:\n\n" },
        { type: "chunk", content: "1. Navigate to `app/copilot-agent/`\n" },
        { type: "chunk", content: "2. Run `python api_server.py`\n" },
        { type: "chunk", content: "3. The server will start on `http://localhost:8000`\n\n" },
        { type: "chunk", content: "This UI will automatically connect when the backend is available." },
        {
          type: "done",
          content:
            "I'm analyzing your request...\n\nExecuting command to gather information.\n\n**Note:** The backend API server is not currently running.\n\nTo connect to the real Copilot Agent:\n\n1. Navigate to `app/copilot-agent/`\n2. Run `python api_server.py`\n3. The server will start on `http://localhost:8000`\n\nThis UI will automatically connect when the backend is available.",
        },
      ];

      for (const chunk of chunks) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`)
        );
      }

      controller.close();
    },
  });

  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
