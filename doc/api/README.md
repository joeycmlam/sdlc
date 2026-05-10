---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# API Overview

The repository exposes APIs through three layers:

1. **Next.js API routes** in `sdlc-app/app/api/*` that proxy browser requests to the Python backend.
2. **`copilot-agent` FastAPI endpoints** that execute AI-agent runs, manage long-lived sessions, and create GitHub issues.
3. **`atlassian-bridge` FastAPI endpoints** that read and update Jira/Confluence content without exposing Atlassian credentials to the browser.

## API groups

| Group | Base path | Purpose |
|---|---|---|
| Next.js proxy routes | `/api/*` | Browser-safe proxy and fallback responses |
| Agent control plane | `http://localhost:8000` or configured `NEXT_PUBLIC_API_URL` | Agent execution, session management, GitHub issue creation |
| Atlassian bridge | `http://localhost:8002` | Jira and Confluence fetch/update/search operations |

## Notes

- The UI defaults to `NEXT_PUBLIC_API_URL=http://localhost:8000`, while the `copilot-agent` README also shows standalone examples on port `8001`. The configured environment variable is the source of truth for a running deployment.
- Stateless agent calls (`/run`, `/stream`) can work without Redis.
- Stateful session calls (`/sessions/*`) require Redis and at least one Arq worker.

See [Endpoints](endpoints.md) for the full route catalog and [API flows](api-flows.md) for sequence diagrams.
