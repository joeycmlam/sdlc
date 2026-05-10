---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# API Endpoints

## 1. Next.js API routes (`sdlc-app/app/api`)

| Method | Path | Proxies to | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | `${NEXT_PUBLIC_API_URL}/health` | UI health check with mock fallback |
| `POST` | `/api/run` | `${NEXT_PUBLIC_API_URL}/run` | Blocking agent run |
| `POST` | `/api/stream` | `${NEXT_PUBLIC_API_URL}/stream` | SSE agent stream with mock fallback |
| `GET` | `/api/agents` | `${NEXT_PUBLIC_API_URL}/agents` | List local agent files |
| `GET` | `/api/agents/content` | `${NEXT_PUBLIC_API_URL}/agents/content` | Read local agent content |
| `GET` | `/api/github/agents` | `${NEXT_PUBLIC_API_URL}/github/agents` | List repository-backed GitHub agents |
| `GET` | `/api/github/agents/content` | `${NEXT_PUBLIC_API_URL}/github/agents/content` | Read GitHub agent content |
| `POST` | `/api/github/issues` | `${NEXT_PUBLIC_API_URL}/github/issues` | Create a GitHub issue and optionally assign Copilot |
| `GET` | `/api/sessions` | `${NEXT_PUBLIC_API_URL}/sessions` | List sessions |
| `POST` | `/api/sessions` | `${NEXT_PUBLIC_API_URL}/sessions` | Create a session |
| `GET` | `/api/sessions/[id]` | `${NEXT_PUBLIC_API_URL}/sessions/{id}` | Get session state |
| `DELETE` | `/api/sessions/[id]` | `${NEXT_PUBLIC_API_URL}/sessions/{id}` | Delete a session |
| `POST` | `/api/sessions/[id]/run` | `${NEXT_PUBLIC_API_URL}/sessions/{id}/run` | Enqueue a worker job |
| `GET` | `/api/sessions/[id]/events` | `${NEXT_PUBLIC_API_URL}/sessions/{id}/events` | Subscribe to SSE events |
| `POST` | `/api/sessions/[id]/approve` | `${NEXT_PUBLIC_API_URL}/sessions/{id}/approve` | Approve or reject a session |
| `GET` | `/api/sessions/[id]/result` | `${NEXT_PUBLIC_API_URL}/sessions/{id}/result` | Read final result or error |

## 2. Copilot-agent FastAPI endpoints (`sdlc-app/services/copilot-agent/api_server.py`)

| Method | Path | Backing service | Description |
|---|---|---|---|
| `GET` | `/health` | FastAPI + Redis ping | Liveness and Redis connectivity |
| `GET` | `/agents` | file system | List registered agent markdown files |
| `GET` | `/agents/content?file=...` | file system | Read agent content and frontmatter |
| `GET` | `/skills` | file system | List registered skill markdown files |
| `POST` | `/run` | in-process `AgentRunner` | Blocking agent run |
| `POST` | `/stream` | in-process `AgentRunner` | SSE stream of chunks, tools, and final result |
| `GET` | `/sessions` | Redis | List live sessions |
| `POST` | `/sessions` | Redis | Create a new session document |
| `GET` | `/sessions/{id}` | Redis | Get one session |
| `POST` | `/sessions/{id}/run` | Arq + Redis | Queue a session for worker execution |
| `GET` | `/sessions/{id}/events` | Redis Streams | Replay/live stream of events |
| `POST` | `/sessions/{id}/approve` | Redis | Human-in-the-loop approval/rejection |
| `GET` | `/sessions/{id}/result` | Redis | Result, state, error, and GitHub issue URL |
| `DELETE` | `/sessions/{id}` | Redis | Remove a session document |
| `POST` | `/github/issues` | GitHub REST | Create issue and optionally assign Copilot |
| `GET` | `/github/copilot-status` | GitHub auth check | Report Copilot assignment readiness |
| `GET` | `/github/agents` | GitHub contents API | List agent files from a repo |
| `GET` | `/github/agents/content` | GitHub contents API | Read one GitHub-hosted agent file |

### Core request shapes

#### Stateless run request

```json
{
  "agent_file": "agents/assistant.md",
  "instruction": "Explain recursion",
  "model": "gpt-4o",
  "max_turns": 20,
  "extra_context": ""
}
```

#### Stateful session request

```json
{
  "agent_file": "agents/ba.agent.md",
  "instruction": "Refine SCRUM-12",
  "model": "gpt-4o",
  "max_turns": 40,
  "jira_url": "https://example.atlassian.net/browse/SCRUM-12",
  "confluence_pages": ["https://example.atlassian.net/wiki/.../page"],
  "create_github_issue": false
}
```

### SSE event contract

| Type | Meaning |
|---|---|
| `state` | Session finite-state-machine transition |
| `chunk` | Incremental model output |
| `tool` | Tool invocation started |
| `done` | Final result |
| `error` | Unhandled failure |

## 3. Atlassian bridge FastAPI endpoints (`atlassian-bridge/app`)

### Health

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service liveness check |

### Jira router (`/jira`)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/jira/fetch` | Fetch Jira issue metadata, description, comments, labels, components, and attachments |
| `POST` | `/jira/update` | Add a comment, update description, and/or transition an issue |
| `POST` | `/jira/transitions` | List available transitions for a Jira issue |

### Confluence router (`/confluence`)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/confluence/fetch` | Fetch a page by full URL and convert storage HTML to Markdown |
| `POST` | `/confluence/search` | Search pages by text and optional space key |
| `POST` | `/confluence/children` | List direct child pages |

## Security and boundary notes

- Jira and Confluence URLs are sent in **POST bodies**, not query strings, to reduce exposure in access logs.
- `atlassian-bridge` keeps Atlassian credentials on the server side.
- Session agent files are path-validated under `services/copilot-agent` before execution.
