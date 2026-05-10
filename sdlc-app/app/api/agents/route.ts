import { NextResponse } from "next/server";

const MOCK_FILES = [
  "assistant.md",
  "ba.agent.md",
  "coder.md",
  "e2e-tester.md",
  "jira-reader.md",
  "jira-test-automator.agent.md",
  "test-analyst.agent.md",
  "test-designer.md",
];

const MOCK_AGENTS = [
  {
    id: "assistant",
    name: "Assistant",
    description: "General-purpose AI assistant (mock — backend offline).",
    skills: [],
    tools: [],
  },
];

export async function GET() {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/agents`, {
      next: { revalidate: 0 },
    });
    if (response.ok) {
      const data = await response.json();
      // Forward the full backend shape: { agents: RegisteredAgent[], files: string[] }.
      // Older backends might omit one or the other — fall back rather than blow up.
      return NextResponse.json({
        agents: Array.isArray(data.agents) ? data.agents : [],
        files: Array.isArray(data.files)
          ? data.files
          : Array.isArray(data.agents) && typeof data.agents[0] === "string"
            ? (data.agents as string[])
            : [],
      });
    }
  } catch {
    // Backend not available — fall through to mock.
  }

  return NextResponse.json({ agents: MOCK_AGENTS, files: MOCK_FILES });
}
