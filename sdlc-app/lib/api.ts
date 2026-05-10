import type {
  AgentDetail,
  AgentsResponse,
  CreateGitHubIssueParams,
  CreateGitHubIssueResponse,
  CreateSessionParams,
  GitHubAgentContentResponse,
  GitHubAgentsResponse,
  HealthResponse,
  ModelsResponse,
  Session,
  SessionEvent,
  SessionsResponse,
  StreamAgentParams,
  StreamEvent,
} from "./types";

export async function fetchAgents(): Promise<AgentsResponse> {
  const res = await fetch("/api/agents");
  if (!res.ok) throw new Error("Failed to fetch agents");
  return res.json();
}

export async function fetchAgentContent(file: string): Promise<AgentDetail> {
  const res = await fetch(`/api/agents/content?file=${encodeURIComponent(file)}`);
  if (!res.ok) throw new Error("Failed to fetch agent content");
  return res.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

/** List LLM models the local Copilot CLI currently supports. */
export async function fetchAvailableModels(): Promise<ModelsResponse> {
  const res = await fetch("/api/models", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch models");
  return res.json();
}

export function getAgentDisplayName(agentFile: string): string {
  const name = agentFile.replace(/\.agent\.md$|\.md$/, "");
  return name
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function getAgentDescription(agentFile: string): string {
  const name = agentFile.replace(/\.agent\.md$|\.md$/, "").toLowerCase();
  const descriptions: Record<string, string> = {
    assistant: "General-purpose AI assistant",
    ba: "Business analysis and requirements",
    coder: "Code generation and review",
    "e2e-tester": "End-to-end test automation",
    "jira-reader": "Read and summarize Jira issues",
    "jira-test-automator": "Automate Jira test workflows",
    "test-analyst": "Test analysis and planning",
    "test-designer": "Test case design and documentation",
  };
  return descriptions[name] ?? "AI agent";
}

/** Map a registered agent's `id` to its on-disk filename. */
export function findAgentFile(
  agentId: string,
  files: string[] | undefined,
): string | null {
  if (!files || files.length === 0) return null;
  return (
    files.find((f) => f === `${agentId}.agent.md`) ??
    files.find((f) => f === `${agentId}.md`) ??
    null
  );
}

async function* readSseStream<T>(
  res: Response,
): AsyncGenerator<T> {
  if (!res.ok || !res.body) throw new Error("Stream request failed");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data) {
            try {
              yield JSON.parse(data) as T;
            } catch {
              // skip malformed SSE data
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function* streamAgent(
  params: StreamAgentParams,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal,
  });
  yield* readSseStream<StreamEvent>(res);
}

// ---------------------------------------------------------------------------
// Sessions (worker-pool flow)
// ---------------------------------------------------------------------------

export async function listSessions(limit = 100): Promise<SessionsResponse> {
  const res = await fetch(`/api/sessions?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to list sessions");
  return res.json();
}

export async function getSession(id: string): Promise<Session> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch session");
  return res.json();
}

export async function createSession(params: CreateSessionParams): Promise<Session> {
  const res = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Failed to create session");
  return res.json();
}

export async function startSession(id: string): Promise<{ session_id: string; state: string }> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(id)}/run`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to start session");
  return res.json();
}

export async function approveSession(
  id: string,
  action: "approve" | "reject",
  comment = "",
): Promise<Session> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, comment }),
  });
  if (!res.ok) throw new Error("Failed to approve session");
  return res.json();
}

export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("Failed to delete session");
}

export async function* streamSessionEvents(
  id: string,
  signal?: AbortSignal,
): AsyncGenerator<SessionEvent> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(id)}/events`, { signal });
  yield* readSseStream<SessionEvent>(res);
}

// ---------------------------------------------------------------------------
// GitHub issue creation + Copilot cloud-agent assignment
// ---------------------------------------------------------------------------

export async function createGitHubIssue(
  params: CreateGitHubIssueParams,
): Promise<CreateGitHubIssueResponse> {
  const res = await fetch("/api/github/issues", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string; error?: string } | null;
    throw new Error(data?.detail || data?.error || `Failed: HTTP ${res.status}`);
  }
  return res.json();
}

/** List custom .agent.md profiles for a target repo (repo + org scopes merged). */
export async function listGitHubAgents(
  owner: string,
  repo: string,
): Promise<GitHubAgentsResponse> {
  const qs = new URLSearchParams({ owner, repo }).toString();
  const res = await fetch(`/api/github/agents?${qs}`, { cache: "no-store" });
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string; error?: string } | null;
    throw new Error(data?.detail || data?.error || `Failed: HTTP ${res.status}`);
  }
  return res.json();
}

/** Fetch the raw text + parsed frontmatter of a single GitHub-hosted .agent.md. */
export async function fetchGitHubAgentContent(
  sourceRepo: string,
  path: string,
): Promise<GitHubAgentContentResponse> {
  const qs = new URLSearchParams({ source_repo: sourceRepo, path }).toString();
  const res = await fetch(`/api/github/agents/content?${qs}`, { cache: "no-store" });
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { detail?: string; error?: string } | null;
    throw new Error(data?.detail || data?.error || `Failed: HTTP ${res.status}`);
  }
  return res.json();
}
