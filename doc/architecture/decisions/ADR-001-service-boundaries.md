---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# ADR-001: Separate UI, agent runtime, and Atlassian bridge

## Status

Accepted

## Context

The repository needs to support:

- browser-based AI interactions,
- long-running worker-backed agent sessions,
- GitHub issue creation,
- Jira and Confluence access without exposing Atlassian credentials to the browser, and
- future growth through markdown-defined agents and skills.

## Decision

Keep the platform split into:

1. a **Next.js UI** for presentation and browser-safe proxy endpoints,
2. a **copilot-agent FastAPI service** for agent execution and GitHub interactions,
3. an **Atlassian bridge** for Jira/Confluence access, and
4. **Redis + Arq workers** for durable session workflows.

## Consequences

### Positive

- Browser clients never need Jira or Confluence credentials.
- Stateless and stateful agent workloads can scale independently.
- Long-running jobs do not block the HTTP control plane.
- Agent personas and skills remain easy to extend through markdown files.

### Negative

- Local development requires multiple processes.
- Ports and environment variables must be kept aligned across services.
- Session consistency is eventual and Redis-backed rather than relational.

## Follow-up guidance

- Prefer `NEXT_PUBLIC_API_URL` as the UI-to-agent integration point.
- Route Jira and Confluence access through `atlassian-bridge` instead of direct browser calls.
- Use Redis-backed sessions only when workflow state or approval is required.
