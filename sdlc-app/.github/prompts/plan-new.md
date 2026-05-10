## Recommendation: Python-First, Phased Delivery

### The Core Decision: Don't Rewrite the Stack

The gap analysis flags a "TypeScript vs Python" mismatch as Layer 1. **Don't chase it.** ATAF's spec is TypeScript because it was written from scratch, not because TypeScript is architecturally required. The Python FastAPI server already streams, handles sub-agents, and has a working Next.js UI consuming it. A TypeScript rewrite is a full restart with zero POC value gained.

Everything ATAF specifies in TypeScript has a clean Python equivalent:

| ATAF TypeScript | Python Equivalent |
|---|---|
| `gray-matter` frontmatter parsing | `python-frontmatter` or `PyYAML` |
| `AgentRegistry` class | Plain `dict` loaded from `*.agent.md` at startup |
| LangGraph FSM | `enum` + `dataclass` state machine |
| Fastify session API | FastAPI + in-memory `dict` or Redis |
| `commander.js` CLI | `click` or `typer` |

---

### What to Build, in Order

**Phase 1 — Fix the Foundation (P3, low effort, high leverage)**

Before building anything new, standardise the existing work so it's extensible:
- Rename skills from `skills/<name>/SKILL.md` → `skills/<id>.skill.md` (flat)
- Add/fix ATAF frontmatter schema on all existing `.agent.md` files (`id`, `triggers`, `skills`, `tools`)
- This unblocks the registry loader

**Phase 2 — Registry System (P1)**

Implement a Python `AgentRegistry`/`SkillRegistry` that parses frontmatter on startup. This is 50–80 lines of Python. It gives the orchestrator the routing table it needs and makes agent management declarative rather than path-hardcoded.

**Phase 3 — 6 ATAF Test Agents (P0)**

Create the 6 `.agent.md` files (playwright, api-test, performance, unit-integration, visual-regression, cucumber) with correct frontmatter. These are primarily prompt content — they don't depend on tools existing yet. The agents become immediately invocable once the registry is live.

**Phase 4 — Master Orchestrator + Session API (P0, P1)**

The biggest architectural gap. Add:
- In-memory session store (`session_id → SessionState`)
- Trigger-based routing (regex match on user input → select agent)
- `/api/v1/sessions` REST endpoints replacing the current stateless `/run`/`/stream`

This is the most impactful single change — it turns the POC from a one-shot agent runner into a proper framework.

**Phase 5 — Approval Gate FSM (P0)**

Implement the 7-state FSM as a Python dataclass. Start with CLI/REST approval only (skip GitHub PR channel for the POC). The `/api/v1/sessions/:id/approve` endpoint is the primary interface.

**Phase 6 — Tool Implementations (P1, highest effort)**

Don't try to implement all 14 tools at once. Prioritise by agent coverage:
1. `playwright-runner` (wraps `npx playwright test` via subprocess) — enables the highest-value agent
2. `jest-runner` / `pytest-runner` — unit/integration coverage
3. `http-client` — API testing
4. `code-generator` — writes files to disk
5. `report-builder` — Allure JSON / JUnit XML

Defer: `k6-runner`, `artillery-runner`, `pixelmatch`, `percy-client`, `diff-viewer` (these are P2/P3 for a POC).

---

### What to Preserve (Don't Touch)

The gap analysis correctly identifies these as genuine value-adds:
- **Next.js chat UI** — keeps human-in-the-loop visible; update it to consume the new session API
- **Domain agents** (BA, Jira Reader, Test Designer, Test Analyst) — these are independent; they co-exist with ATAF agents
- **BDD skill library** — plug directly into the skill registry once it exists

---

### What to Skip for the POC

- **`ataf` CLI binary** — the REST API + Next.js UI covers the interaction surface for a POC
- **GitHub PR approval channel** — REST approval is sufficient
- **`ataf.config.yaml`** — environment variables + FastAPI startup args serve the same purpose with less ceremony
- **Allure HTML reporting** — JUnit XML is sufficient to demonstrate the reporting layer
- **`@github/copilot-extensions` npm SDK** — only needed if deploying as a GitHub Marketplace extension; the Python SDK + FastAPI path is fully functional for a POC

---

### Suggested Delivery Sequence

| Sprint | Deliverable | Risk |
|---|---|---|
| 1 | Frontmatter standardisation + registry loader | Low |
| 2 | 6 ATAF agent files + registry hot-load validation | Low |
| 3 | Session store + `/api/v1/` routes + trigger routing | Medium |
| 4 | Approval Gate FSM + `/approve` endpoint | Medium |
| 5 | `playwright-runner` + `code-generator` + `http-client` tools | High |
| 6 | `pytest-runner` + `jest-runner` + `report-builder` tools | High |
| 7 | Next.js UI update to session-aware API | Low |

The P0 orchestrator + approval gate items (Phases 3–4) should be treated as a single deliverable — the session API without the approval gate is incomplete, and the approval gate without session management is unrouteable.