---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# Developer Guide

## Repository layout

- `sdlc-app/` — Next.js UI plus Python services under `services/`
- `atlassian-bridge/` — standalone FastAPI service for Jira and Confluence
- `doc/` — repository-level system documentation

## Prerequisites

- Node.js 18+
- `pnpm`
- Python 3.9+ for `sdlc-app/services/*`
- Python 3.11+ for `atlassian-bridge`
- Docker or a local Redis install for session workflows
- GitHub CLI with Copilot extension for the recommended agent path

## Local startup

### 1. Frontend

```bash
cd sdlc-app
pnpm install
pnpm dev
```

### 2. Copilot-agent service

```bash
cd sdlc-app/services/copilot-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
agent-api --port 8000
```

### 3. Redis and worker for stateful sessions

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
cd sdlc-app/services/copilot-agent
source .venv/bin/activate
agent-worker
```

### 4. Atlassian bridge

```bash
cd atlassian-bridge
python -m venv .venv
source .venv/bin/activate
pip install -e .
atlassian-bridge
```

## Environment variables

| File | Key examples |
|---|---|
| `sdlc-app/.env.example` | `NEXT_PUBLIC_API_URL` |
| `sdlc-app/services/copilot-agent/.env.example` | `REDIS_URL`, GitHub token settings |
| `atlassian-bridge/.env.example` | Atlassian base URL, user, API token |

## Common development flows

- Use `/stream` for quick prompt experiments.
- Use `/sessions/*` when you need Redis-backed workflow state or approvals.
- Use `jira-cli` when you need a standalone Jira export without starting the full UI.
- Use `atlassian-bridge` when agent flows need Jira or Confluence context safely.

## Additional references

- [`../../sdlc-app/README.md`](../../sdlc-app/README.md)
- [`../../sdlc-app/services/copilot-agent/README.md`](../../sdlc-app/services/copilot-agent/README.md)
- [`../../sdlc-app/services/jira-cli/README.md`](../../sdlc-app/services/jira-cli/README.md)
