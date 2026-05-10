---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# Data Schema

The repository does **not** currently use a relational database. Persistent runtime state is stored in Redis by the `copilot-agent` service.

## Redis-backed entities

### Session document

- **Key pattern:** `session:{id}`
- **Format:** JSON serialized from the `Session` Pydantic model
- **TTL:** 24 hours
- **Purpose:** store workflow state, prompt settings, result, error, and optional Jira/GitHub metadata

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Session identifier (UUID) |
| `state` | enum | `pending`, `running`, `awaiting_approval`, `approved`, `rejected`, `completed`, `failed` |
| `agent_file` | `string` | Agent prompt path relative to `services/copilot-agent` |
| `instruction` | `string` | User task |
| `model` | `string` | LLM model name |
| `max_turns` | `integer` | Turn budget capped by the runtime |
| `extra_context` | `string` | Extra injected context |
| `jira_url` | `string?` | Jira issue URL attached to the session |
| `confluence_pages` | `string[]` | Confluence URLs attached to the session |
| `create_github_issue` | `boolean` | Whether workflow should create an issue |
| `github_owner` / `github_repo` | `string?` | Target repository for issue creation |
| `custom_agent` | `string?` | Optional GitHub cloud-agent selection |
| `result` | `string?` | Final model output |
| `github_issue_url` | `string?` | Created GitHub issue URL |
| `error` | `string?` | Terminal error message |
| `created_at` / `updated_at` | timestamp | Audit timestamps |

### Session event stream

- **Key pattern:** `events:{session_id}`
- **Type:** Redis Stream
- **Retention:** max length ~10,000 entries and 24 hour TTL
- **Purpose:** replayable SSE event history for the session UI

Event payloads are stored as JSON in the `data` field and use the event types documented in [`../api/endpoints.md`](../api/endpoints.md).

### Arq queue

- **Key family:** managed by Arq, commonly surfaced as `arq:queue`
- **Purpose:** dispatch `run_session_job` work to the background worker pool
- **Retention:** controlled by Arq settings and Redis eviction behavior

## Other persisted inputs

- `.env` files provide runtime configuration for the UI, `copilot-agent`, and `atlassian-bridge`.
- Markdown files under `services/copilot-agent/agents` and `services/copilot-agent/skills` act as a file-based registry of behavior.
