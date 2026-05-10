# Plan: ATAF Gap Analysis & Reflection for mypoc

## TL;DR
The mypoc repo is a functioning proof-of-concept with a Python FastAPI backend (copilot-agent), a Next.js chat UI, and a set of Jira/asset-management domain agents. Measured against ATAF-Design.md, the repo implements only the foundation layer (HTTP server, streaming, sub-agent delegation, some BDD skills) but is missing nearly every ATAF-specific component: the 6 testing agents, 14 tools, 9 skills, registry system, master orchestrator, approval gate FSM, session API, and reporting.

---

## ATAF vs Current: Layer-by-Layer Comparison

### Layer 1 – Technology Stack
| Dimension | ATAF Spec | Current | Status |
|---|---|---|---|
| Runtime | Node.js / TypeScript | Python (FastAPI) | Mismatch |
| Agent SDK | @github/copilot-extensions (npm) | github-copilot-sdk (pip) + azure-ai-inference | Different SDKs |
| Server | Fastify | FastAPI + uvicorn | Different ecosystems |
| Orchestration | LangGraph / custom FSM | while-loop + turn counter | No FSM |
| Frontend | Not specified | Next.js + React (full chat UI) | Addition |

### Layer 2 – Dynamic Registry System
- ATAF: AgentRegistry, SkillRegistry, ToolRegistry — TypeScript classes, gray-matter parsing, hot-reload, findByTrigger()
- Current: No registries. Agents loaded by direct path; skills are passive directories; zero tool registry.
- Status: **Not implemented**

### Layer 3 – Agent Catalogue
- ATAF: 7 agents (playwright, api-test, performance, unit-integration, visual-regression, cucumber, orchestrator)
- Current: 8 agents (assistant, ba, coder, e2e-tester, jira-reader, jira-test-automator, test-analyst, test-designer) — all Jira/asset-management domain
- Status: **0 of 7 ATAF agents exist**; frontmatter schema inconsistent

### Layer 4 – Skill Catalogue
- ATAF: 9 skills as flat `<id>.skill.md` files
- Current: 5 skills as `skills/<name>/SKILL.md` (VS Code Copilot format) — partial content overlap (bdd-playwright, bdd-cucumber-node)
- Status: **0 of 9 ATAF skills exist** in required format

### Layer 5 – Tool Catalogue
- ATAF: 14 typed TypeScript `.tool.ts` files (runners, http-client, code-generator, approval-gate, git-tools, etc.)
- Current: Zero `.tool.ts` files; all tool execution via generic `bash_exec` shell wrapper
- Status: **0 of 14 tools implemented**

### Layer 6 – Master Orchestrator
- ATAF: MasterOrchestrator boots registries, creates sessions, routes by trigger, injects agents/skills/tools, drives approval FSM, aggregates reports
- Current: `jira-test-automator.agent.md` is closest analog — orchestrates 4-step Jira→test workflow via invoke_agent — domain-specific only
- Status: **Not implemented**

### Layer 7 – Human Approval Gate
- ATAF: FSM with 7 states (pending→awaiting_approval→approved/rejected→re-running→completed/failed); 3 channels (CLI, REST, GitHub PR)
- Current: No approval concept; agents run end-to-end
- Status: **Not implemented**

### Layer 8 – Session API
- ATAF: POST /api/v1/sessions, POST /api/v1/sessions/:id/run, GET /api/v1/sessions/:id/results, POST /api/v1/sessions/:id/approve, GET /api/v1/sessions/:id/report
- Current: POST /run, POST /stream (stateless, no session IDs), GET /health, GET /agents
- Status: **No versioning, no sessions, no results/approve/report endpoints**

### Layer 9 – Reporting
- ATAF: Allure JSON, JUnit XML, HTML via report-builder tool
- Current: Raw streamed text only
- Status: **Not implemented**

### Layer 10 – CI/CD
- ATAF: git-tools (branches, PRs, commits), GitHub Actions webhook
- Current: None
- Status: **Not implemented**

### Layer 11 – CLI
- ATAF: `ataf run --agent playwright --skill X --url Y`, `ataf approve --session <id>`, `ataf run --config ataf.config.yaml`
- Current: `python agent_copilot.py -a agents/... -m model -i "..."` — no `ataf` binary, no config file, no approve command

---

## What mypoc Has That ATAF Doesn't Specify (Value-Adds)
- Full Next.js chat UI (streaming, model selector, agent selector, tool cards, mobile)
- Domain agents for asset management (BA, Jira Reader, Test Designer, Test Analyst) with MiFID II / UCITS knowledge
- Dual Python agent implementations (Copilot SDK + Azure AI Inference)
- Sub-agent delegation via `invoke_agent` (depth-limited, isolated sessions)
- `finish` tool for explicit completion signalling
- `WorkflowAnalyser` for step-aware continuation detection
- BDD skill library (playwright-bdd, pytest-bdd, cucumber-node, bdd-scenarios, read-jira)

---

## Priority Gap Roadmap

| Priority | Gap | Effort |
|---|---|---|
| P0 | 6 ATAF testing agent files (.agent.md) with correct frontmatter schema | Medium |
| P0 | Master Orchestrator with trigger-based routing | High |
| P0 | Human Approval Gate FSM (7 states, 3 channels) | High |
| P1 | 14 typed tool implementations | Very High |
| P1 | Agent/Skill/Tool registry system (TypeScript or Python equivalent) | High |
| P1 | Session management + /api/v1/ REST endpoints | Medium |
| P2 | `ataf` CLI binary + ataf.config.yaml support | Medium |
| P2 | Allure/JUnit XML report generation | Medium |
| P2 | git-tools CI/CD integration | Medium |
| P3 | Skill files renamed to `<id>.skill.md` flat format | Low |
| P3 | Standardise agent frontmatter to ATAF schema | Low |
