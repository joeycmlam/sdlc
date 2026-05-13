---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# Components

## Repository components

| Component | Location | Responsibility | Key dependencies |
|---|---|---|---|
| Next.js UI | `sdlc-app/app`, `sdlc-app/components`, `sdlc-app/lib` | Render chat, sessions, issue creation, settings, and proxy browser requests | Next.js, React, TypeScript |
| Next.js proxy routes | `sdlc-app/app/api` | Shield browser clients from backend details and provide mock fallback behavior | Fetch API |
| Copilot-agent API | `sdlc-app/services/copilot-agent/api_server.py` | Run agents, expose SSE, manage sessions, create GitHub issues | FastAPI, GitHub Copilot SDK, Redis, Arq |
| Session store | `sdlc-app/services/copilot-agent/session_store.py` | Persist sessions and enforce state transitions | Redis, Pydantic |
| Event bus | `sdlc-app/services/copilot-agent/event_bus.py` | Publish/replay SSE events per session | Redis Streams |
| Worker pool | `sdlc-app/services/copilot-agent/worker.py` | Execute long-running session jobs | Arq, AgentRunner |
| Agent library | `sdlc-app/services/copilot-agent/agents` | Persona-specific system prompts for BA, coder, QA, etc. | Markdown frontmatter |
| Skill library | `sdlc-app/services/copilot-agent/skills` | Tool-guidance documents for agents | Markdown |
| Jira CLI | `sdlc-app/services/jira-cli` | Standalone issue-to-Markdown export utility | Python, Jira REST API |
| Atlassian bridge | `atlassian-bridge/app` | Jira/Confluence proxy and content normalization | FastAPI, httpx |

## Runtime responsibilities

### UI and browser layer

- Presents routes for `/`, `/sessions`, `/sessions/[id]`, `/issues/new`, and `/settings`.
- Talks only to Next.js API routes from the browser.
- Falls back to mock content for some routes when the backend is unavailable.

### Agent runtime layer

- Loads agent prompt files from disk.
- Runs stateless requests directly or enqueues stateful requests.
- Publishes model chunks and tool events back to the UI through SSE.
- Can create GitHub issues and assign the `Copilot` user when requested.

### Integration layer

- Converts Jira Atlassian Document Format into Markdown-like text.
- Converts Confluence storage HTML into simplified Markdown.
- Accepts full Atlassian URLs in POST bodies and resolves REST API calls internally.
