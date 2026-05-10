export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  toolName?: string;
}

export type ConnectionStatus = "connected" | "connecting" | "disconnected";

export interface StreamEvent {
  type: "chunk" | "tool" | "done" | "error";
  content?: string;
  name?: string;
  message?: string;
}

export interface StreamAgentParams {
  agent_file: string;
  instruction: string;
  model: string;
  max_turns: number;
}

export interface RegisteredAgent {
  id: string;
  name: string;
  description: string;
  skills: string[];
  tools: string[];
}

export interface AgentsResponse {
  /** Agents discovered with valid YAML frontmatter (id, name, description, ...). */
  agents: RegisteredAgent[];
  /** Every .md/.agent.md file in the agents directory (filename only). */
  files: string[];
}

export interface AgentMetadata {
  id?: string;
  name?: string;
  description?: string;
  skills?: string[];
  tools?: string[];
  triggers?: string[];
  agents?: string[];
  "argument-hint"?: string;
}

export interface AgentDetail {
  file: string;
  content: string;
  metadata: AgentMetadata;
}

export interface HealthResponse {
  status: string;
  mode?: string;
  redis?: boolean;
}

// ---------------------------------------------------------------------------
// Sessions (worker-pool flow)
// ---------------------------------------------------------------------------

export type SessionState =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "completed"
  | "failed";

export interface Session {
  id: string;
  state: SessionState;
  agent_file: string;
  instruction: string;
  model: string;
  max_turns: number;
  extra_context: string;
  created_at: string;
  updated_at: string;
  result: string | null;
  github_issue_url: string | null;
  jira_url: string | null;
  confluence_pages: string[];
  create_github_issue: boolean;
  github_owner: string | null;
  github_repo: string | null;
  custom_agent: string | null;
  error: string | null;
}

export interface SessionsResponse {
  sessions: Session[];
}

export interface CreateSessionParams {
  agent_file: string;
  instruction: string;
  model: string;
  max_turns: number;
  extra_context?: string;
  jira_url?: string;
  confluence_pages?: string[];
  create_github_issue?: boolean;
  github_owner?: string;
  github_repo?: string;
  custom_agent?: string;
}

export interface SessionEvent {
  type: "state" | "chunk" | "tool" | "done" | "error";
  state?: SessionState;
  content?: string;
  name?: string;
  message?: string;
  code?: number;
  session_id?: string;
}

// ---------------------------------------------------------------------------
// GitHub issue creation + Copilot cloud-agent assignment
// ---------------------------------------------------------------------------

export interface CreateGitHubIssueParams {
  owner: string;
  repo: string;
  title: string;
  body: string;
  assign_to_copilot?: boolean;
  additional_assignees?: string[];
  labels?: string[];
  custom_agent?: string;
  skills?: string[];
}

export type CopilotAssignmentReason =
  | "ok"
  | "not_requested"
  | "not_enabled"
  | "graphql_error"
  | "unknown";

export interface CreateGitHubIssueResponse {
  number: number;
  html_url: string;
  state: string;
  assignees: string[];
  title: string;
  copilot_assigned: boolean;
  copilot_reason: CopilotAssignmentReason | null;
  copilot_message: string | null;
  /** Logins of every actor GitHub returned via `suggestedActors`. */
  actor_candidates: string[];
}

// ---------------------------------------------------------------------------
// GitHub-sourced custom agents (repo .github/agents + org .github-private)
// ---------------------------------------------------------------------------

export interface GitHubCustomAgent {
  id: string;
  name: string;
  scope: "repo" | "org";
  source_repo: string;
  path: string;
  description: string | null;
  tools: string[];
  skills: string[];
}

export interface GitHubAgentsResponse {
  owner: string;
  repo: string;
  agents: GitHubCustomAgent[];
}

export interface GitHubAgentContentResponse {
  source_repo: string;
  path: string;
  content: string;
  metadata: Record<string, unknown> & {
    name?: string;
    description?: string;
    skills?: string[];
    tools?: string[];
    triggers?: string[];
    agents?: string[];
  };
}

// ---------------------------------------------------------------------------
// LLM models (sourced from Copilot CLI's models.list)
// ---------------------------------------------------------------------------

export interface AvailableModel {
  id: string;
  name: string;
  /** GitHub Copilot premium-request multiplier (e.g. 1.0, 0.33, 0.0). */
  billing_multiplier: number | null;
}

export interface ModelsResponse {
  models: AvailableModel[];
  cached?: boolean;
  source?: "fallback";
}
