---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
Source instructions: sdlc-app/.github/copilot-instructions.md
---

# SDLC System Documentation

This `doc/` tree provides a repository-level view of the SDLC platform. The current repository contains two deployable back-end services (`sdlc-app/services/copilot-agent` and `atlassian-bridge`) plus a Next.js UI in `sdlc-app`.

## Documentation index

| Area | File | Purpose |
|---|---|---|
| Overview | [System documentation](README.md) | Navigation and repository summary |
| API | [API overview](api/README.md) | API surface and service boundaries |
| API | [Endpoints](api/endpoints.md) | Frontend proxy, FastAPI, and Atlassian bridge endpoints |
| API | [API flows](api/api-flows.md) | Sequence diagrams for major request paths |
| Architecture | [Design](architecture/DESIGN.md) | Deployment model and high-level architecture |
| Architecture | [Components](architecture/components.md) | Responsibilities of each major module |
| Architecture | [ADR-001](architecture/decisions/ADR-001-service-boundaries.md) | Why the system is split into UI, agent API, bridge, and Redis worker components |
| Database | [Schema](database/schema.md) | Redis-backed data model and persistence notes |
| Database | [ER diagram](database/er-diagram.md) | Conceptual entity relationships |
| Database | [Migrations](database/migrations.md) | Current migration story and schema change guidance |
| Workflows | [Business logic](workflows/business-logic.md) | User-facing business flows |
| Workflows | [Data flows](workflows/data-flows.md) | How Jira, Confluence, sessions, and GitHub issue data move |
| Workflows | [Sequence diagrams](workflows/sequence-diagrams.md) | Runtime interaction diagrams |
| Guides | [Developer guide](guides/DEVELOPER.md) | Local setup and service bring-up |
| Changelog | [Documentation changelog](changelog/CHANGELOG.md) | Documentation baseline history |

## System summary

- **Frontend:** `sdlc-app` is a Next.js App Router UI for chat, sessions, issue creation, and settings.
- **Agent execution:** `sdlc-app/services/copilot-agent` exposes stateless `/run` and `/stream` endpoints plus Redis-backed `/sessions/*` workflows.
- **Atlassian integration:** `atlassian-bridge` is a FastAPI service that proxies Jira and Confluence behind server-held credentials.
- **State management:** Redis stores session documents, event streams, and the Arq queue for long-running jobs.
- **Repository guidance source:** repository conventions were taken from [`sdlc-app/.github/copilot-instructions.md`](../sdlc-app/.github/copilot-instructions.md).

## Existing source documentation worth reading

- [`sdlc-app/README.md`](../sdlc-app/README.md)
- [`sdlc-app/services/copilot-agent/README.md`](../sdlc-app/services/copilot-agent/README.md)
- [`sdlc-app/services/jira-cli/README.md`](../sdlc-app/services/jira-cli/README.md)
- [`sdlc-app/docs/ATAF-Design.md`](../sdlc-app/docs/ATAF-Design.md)

## Documentation update summary

- ✅ API documentation created for the Next.js proxy layer, Copilot agent API, and Atlassian bridge.
- ✅ Database documentation created for the Redis-backed session and event model.
- ✅ Architecture documentation created for the runtime component layout and deployment model.
- ✅ Workflow documentation created for chat, BA refinement, approval, and GitHub issue creation flows.
- ✅ Developer guidance created for local setup and service startup.
