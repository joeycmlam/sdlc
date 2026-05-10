# AutoTest Agent Framework (ATAF)
## Architecture & Solution Design

> **Deployment:** Standalone CLI + Cloud-hosted Microservice  
> **Autonomy:** Semi-autonomous — agent suggests and runs, human approves fixes  
> **SDK:** GitHub Copilot Extensions SDK (`@github/copilot-extensions`)

---

## 1. System Overview

ATAF is a plugin-based autonomous testing platform built around three dynamic registries — Agent, Skill, and Tool — each loading configuration from flat files at startup. The **Master Orchestrator Agent** receives a test request, selects the appropriate testing agent(s), injects the relevant skills and tools, runs the tests, then routes findings through a human approval gate before producing reports and CI/CD integration outputs.

```
Entry Point → Orchestrator → [Agent Registry + Skill Registry + Tool Registry]
           → Testing Agents → Human Approval Gate → Report + CI/CD Output
```

---

## 2. Architecture Design

### 2.1 Layer Map

| Layer | Components | Technology |
|---|---|---|
| Entry | CLI, Copilot SDK, REST API | Node.js, commander.js, @github/copilot-extensions, Fastify |
| Orchestration | Master Orchestrator Agent | LangGraph / custom FSM, Copilot SDK |
| Registries | Agent, Skill, Tool | Dynamic file loaders (YAML/MD/TS) |
| Agents | 6 specialized testing agents | TypeScript, per-agent tool set |
| Approval Gate | Human-in-the-loop review | WebSocket, CLI prompt, GitHub PR comment |
| Output | Reports, CI/CD hooks | Allure, JUnit XML, GitHub Actions webhook |

### 2.2 Deployment Modes

**Standalone CLI**
```
ataf run --agent playwright --skill generate-playwright-tests --url https://myapp.com
ataf run --config ataf.config.yaml
ataf approve --session <session-id>
```

**Cloud Microservice**
```
POST /api/v1/sessions          # create session
POST /api/v1/sessions/:id/run  # trigger agents
GET  /api/v1/sessions/:id/results
POST /api/v1/sessions/:id/approve
GET  /api/v1/sessions/:id/report
```

---

## 3. Dynamic Loader Design

The three registries share a common interface. At startup (or on hot-reload), each registry scans its directory, parses the files, and registers the entries with the orchestrator.

### 3.1 Directory Structure

```
ataf/
├── agents/                        # Agent markdown files
│   ├── playwright.agent.md
│   ├── api-test.agent.md
│   ├── performance.agent.md
│   ├── unit-integration.agent.md
│   ├── visual-regression.agent.md
│   └── cucumber.agent.md
│
├── skills/                        # Skill markdown files
│   ├── generate-playwright-tests.skill.md
│   ├── generate-api-tests.skill.md
│   ├── generate-unit-tests.skill.md
│   ├── generate-cucumber-tests.skill.md
│   ├── analyze-failures.skill.md
│   ├── suggest-fixes.skill.md
│   ├── visual-compare.skill.md
│   ├── performance-baseline.skill.md
│   └── data-driven-expansion.skill.md
│
├── tools/                         # Tool TypeScript files
│   ├── playwright-runner.tool.ts
│   ├── jest-runner.tool.ts
│   ├── k6-runner.tool.ts
│   ├── cucumber-runner.tool.ts
│   ├── pixelmatch.tool.ts
│   ├── http-client.tool.ts
│   ├── code-generator.tool.ts
│   ├── diff-viewer.tool.ts
│   ├── report-builder.tool.ts
│   ├── approval-gate.tool.ts
│   └── git-tools.tool.ts
│
├── src/
│   ├── registries/
│   │   ├── agent-registry.ts
│   │   ├── skill-registry.ts
│   │   └── tool-registry.ts
│   ├── orchestrator/
│   │   └── master-orchestrator.ts
│   ├── approval/
│   │   └── approval-gate.ts
│   ├── server/                    # Cloud microservice
│   │   └── app.ts
│   └── cli/                       # Standalone CLI
│       └── index.ts
│
└── ataf.config.yaml               # Top-level config
```

### 3.2 Agent Markdown Schema (`*.agent.md`)

```markdown
---
id: playwright
name: Playwright Agent
version: 1.0.0
description: Generates and runs Playwright E2E and UI tests
skills:
  - generate-playwright-tests
  - analyze-failures
  - suggest-fixes
tools:
  - playwright-runner
  - code-generator
  - diff-viewer
  - report-builder
triggers:
  - e2e
  - ui
  - browser
  - playwright
model: claude-sonnet-4-20250514
max_tokens: 8000
---

## System Prompt

You are a Playwright expert. Given a URL or component spec, you:
1. Analyse the page structure
2. Generate comprehensive Playwright test suites covering happy paths, edge cases, and error states
3. Run the tests and capture results
4. Suggest targeted fixes for failures — do NOT auto-apply; wait for human approval

## Output Format

Return a JSON object with:
- `tests`: array of generated test files
- `results`: Playwright test runner output
- `failures`: list of failed tests with root cause
- `suggested_fixes`: list of proposed code changes (pending approval)
```

### 3.3 Skill Markdown Schema (`*.skill.md`)

```markdown
---
id: generate-playwright-tests
name: Generate Playwright Tests
version: 1.0.0
applicable_agents:
  - playwright
---

## Purpose
Generate production-ready Playwright test suites from a URL or component spec.

## Instructions
1. Inspect the DOM via page.evaluate or screenshot analysis
2. Identify interactive elements: buttons, forms, navigation, modals
3. Generate tests covering: render, interaction, validation, and navigation flows
4. Follow the Page Object Model pattern
5. Include data-testid selectors over CSS class selectors
6. Add visual snapshot assertions using expect(page).toHaveScreenshot()

## Output Template
```typescript
import { test, expect } from '@playwright/test';

test.describe('<component>', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('<url>');
  });

  test('renders correctly', async ({ page }) => {
    await expect(page).toHaveScreenshot();
  });
});
```
```

### 3.4 Tool TypeScript Schema (`*.tool.ts`)

```typescript
// playwright-runner.tool.ts
import { Tool } from '../types/tool';

export const playwrightRunnerTool: Tool = {
  id: 'playwright-runner',
  name: 'Playwright Test Runner',
  description: 'Runs a Playwright test suite and returns structured results',
  schema: {
    type: 'function',
    function: {
      name: 'run_playwright_tests',
      parameters: {
        type: 'object',
        properties: {
          testFiles: { type: 'array', items: { type: 'string' } },
          baseUrl: { type: 'string' },
          browser: { type: 'string', enum: ['chromium', 'firefox', 'webkit'] },
          headed: { type: 'boolean', default: false },
        },
        required: ['testFiles', 'baseUrl'],
      },
    },
  },
  execute: async ({ testFiles, baseUrl, browser = 'chromium', headed = false }) => {
    // Spawn playwright test runner, capture output, return structured results
  },
};
```

### 3.5 Registry Loader (TypeScript)

```typescript
// agent-registry.ts
import fs from 'fs/promises';
import path from 'path';
import matter from 'gray-matter';

export class AgentRegistry {
  private agents = new Map<string, AgentConfig>();

  async load(dir: string) {
    const files = await fs.readdir(dir);
    for (const file of files.filter(f => f.endsWith('.agent.md'))) {
      const raw = await fs.readFile(path.join(dir, file), 'utf-8');
      const { data, content } = matter(raw);
      this.agents.set(data.id, { ...data, systemPrompt: content });
    }
  }

  get(id: string) { return this.agents.get(id); }
  list() { return [...this.agents.values()]; }
  findByTrigger(trigger: string) {
    return this.list().filter(a => a.triggers?.includes(trigger));
  }
}
```

---

## 4. GitHub Copilot SDK Integration

### 4.1 SDK Setup

```bash
npm install @github/copilot-extensions
```

### 4.2 Copilot Extension Entry Point

```typescript
// src/copilot-extension.ts
import { CopilotExtension, verifyRequest } from '@github/copilot-extensions';
import { MasterOrchestrator } from './orchestrator/master-orchestrator';

const orchestrator = new MasterOrchestrator();
await orchestrator.boot('./agents', './skills', './tools');

const extension = new CopilotExtension({
  onMessage: async (message, context) => {
    // Parse intent from the Copilot chat message
    const session = await orchestrator.createSession({
      input: message.content,
      user: context.user,
    });

    // Stream back progress events
    for await (const event of orchestrator.run(session)) {
      yield event;
    }
  },
});

export default extension;
```

### 4.3 Agent API Call via Copilot SDK

```typescript
// Inside MasterOrchestrator
async callAgent(agent: AgentConfig, prompt: string, tools: Tool[]) {
  const response = await fetch('https://api.githubcopilot.com/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${process.env.COPILOT_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: agent.model ?? 'gpt-4o',
      messages: [
        { role: 'system', content: agent.systemPrompt },
        { role: 'user', content: prompt },
      ],
      tools: tools.map(t => t.schema),
      tool_choice: 'auto',
      stream: true,
    }),
  });
  return response; // stream to caller
}
```

---

## 5. Agent Catalogue

### Agent 1: Playwright Agent
**File:** `agents/playwright.agent.md`

| Property | Value |
|---|---|
| ID | `playwright` |
| Skills | generate-playwright-tests, analyze-failures, suggest-fixes |
| Tools | playwright-runner, code-generator, diff-viewer, report-builder |
| Triggers | `e2e`, `ui`, `browser`, `playwright` |
| Responsibility | Generate, run, and triage Playwright E2E and component tests |

**Workflow:** Accept URL/spec → Inspect DOM → Generate test suite → Run tests → Classify failures → Suggest fixes (pending human approval)

---

### Agent 2: API Test Agent
**File:** `agents/api-test.agent.md`

| Property | Value |
|---|---|
| ID | `api-test` |
| Skills | generate-api-tests, analyze-failures, suggest-fixes |
| Tools | http-client, code-generator, diff-viewer, report-builder |
| Triggers | `api`, `rest`, `graphql`, `contract`, `openapi` |
| Responsibility | Generate and run REST and GraphQL contract tests |

**Workflow:** Parse OpenAPI/GraphQL schema → Generate test cases covering happy path, auth, edge cases, error codes → Run via http-client → Diff expected vs actual responses → Suggest fixes

---

### Agent 3: Performance Agent
**File:** `agents/performance.agent.md`

| Property | Value |
|---|---|
| ID | `performance` |
| Skills | performance-baseline, analyze-failures, suggest-fixes |
| Tools | k6-runner, artillery-runner, report-builder |
| Triggers | `performance`, `load`, `stress`, `latency`, `k6`, `artillery` |
| Responsibility | Design and execute load/stress/spike tests; compare against baselines |

**Workflow:** Accept SLO targets → Generate k6 or Artillery script → Run ramp-up/steady-state/spike scenarios → Compare P50/P95/P99 against baseline → Flag regressions → Suggest optimisation targets

---

### Agent 4: Unit / Integration Agent
**File:** `agents/unit-integration.agent.md`

| Property | Value |
|---|---|
| ID | `unit-integration` |
| Skills | generate-unit-tests, analyze-failures, suggest-fixes |
| Tools | jest-runner, vitest-runner, pytest-runner, code-generator, diff-viewer |
| Triggers | `unit`, `integration`, `jest`, `vitest`, `pytest`, `coverage` |
| Responsibility | Generate unit and integration tests from source code or spec |

**Workflow:** Parse source file → Identify public interface, side effects, and dependencies → Generate test file with mocks → Run tests → Report coverage delta → Suggest additions for uncovered branches

---

### Agent 5: Visual Regression Agent
**File:** `agents/visual-regression.agent.md`

| Property | Value |
|---|---|
| ID | `visual-regression` |
| Skills | visual-compare, analyze-failures, suggest-fixes |
| Tools | playwright-runner, pixelmatch, percy-client, report-builder |
| Triggers | `visual`, `screenshot`, `regression`, `percy`, `snapshot` |
| Responsibility | Capture and diff UI screenshots against approved baselines |

**Workflow:** Capture screenshots via Playwright → Compare pixel-by-pixel using Pixelmatch or Percy → Generate diff images → Flag threshold breaches → Present diff to human for baseline update approval

---

### Agent 6: Cucumber Agent
**File:** `agents/cucumber.agent.md`

| Property | Value |
|---|---|
| ID | `cucumber` |
| Skills | generate-cucumber-tests, data-driven-expansion, analyze-failures, suggest-fixes |
| Tools | cucumber-runner, code-generator, data-table-expander, report-builder |
| Triggers | `bdd`, `cucumber`, `gherkin`, `feature`, `data-driven`, `scenario` |
| Responsibility | Author Gherkin feature files and step definitions; expand data-driven tables |

**Workflow:** Accept user story or AC → Generate `.feature` files with Scenario Outlines and Example tables → Generate step definition stubs → Run Cucumber → Report step coverage → Suggest missing scenarios for untested data combinations

---

### Agent 7: Master Orchestrator Agent *(internal)*
**File:** `agents/orchestrator.agent.md`

Coordinates the other agents. Owns session state, routes test requests based on triggers, injects skills and tools from registries, drives the approval gate FSM, and aggregates final reports.

---

## 6. Skill Catalogue

| ID | File | Applicable Agents | Purpose |
|---|---|---|---|
| `generate-playwright-tests` | `generate-playwright-tests.skill.md` | playwright | DOM analysis → POM-style test generation |
| `generate-api-tests` | `generate-api-tests.skill.md` | api-test | OpenAPI/GraphQL schema → request/response tests |
| `generate-unit-tests` | `generate-unit-tests.skill.md` | unit-integration | Source file → unit tests with mocks and coverage |
| `generate-cucumber-tests` | `generate-cucumber-tests.skill.md` | cucumber | User stories → Gherkin + step definitions |
| `data-driven-expansion` | `data-driven-expansion.skill.md` | cucumber | Scenario Outline → data table permutation expansion |
| `performance-baseline` | `performance-baseline.skill.md` | performance | SLO targets → k6/Artillery scripts + threshold config |
| `visual-compare` | `visual-compare.skill.md` | visual-regression | Baseline vs candidate screenshot diff strategy |
| `analyze-failures` | `analyze-failures.skill.md` | all | Parse test runner output → classify root causes |
| `suggest-fixes` | `suggest-fixes.skill.md` | all | Root causes → targeted code patch proposals |

---

## 7. Tool Catalogue

| ID | File | Description | Dependencies |
|---|---|---|---|
| `playwright-runner` | `playwright-runner.tool.ts` | Runs Playwright test suites; returns structured pass/fail/screenshot output | `@playwright/test` |
| `jest-runner` | `jest-runner.tool.ts` | Runs Jest or Vitest test files; returns coverage report | `jest`, `vitest` |
| `pytest-runner` | `pytest-runner.tool.ts` | Runs pytest suites; returns JSON report | `python`, `pytest` |
| `k6-runner` | `k6-runner.tool.ts` | Executes k6 load scripts; returns P50/P95/P99 summary | `k6` binary |
| `artillery-runner` | `artillery-runner.tool.ts` | Executes Artillery YAML scripts; returns summary stats | `artillery` |
| `cucumber-runner` | `cucumber-runner.tool.ts` | Runs Cucumber feature files; returns step-level results | `@cucumber/cucumber` |
| `pixelmatch` | `pixelmatch.tool.ts` | Pixel-level image diff; returns diff count and diff image | `pixelmatch`, `pngjs` |
| `percy-client` | `percy-client.tool.ts` | Submits screenshots to Percy for AI-assisted visual diff | `@percy/cli` |
| `http-client` | `http-client.tool.ts` | Makes REST and GraphQL requests; captures latency and response body | `axios` |
| `code-generator` | `code-generator.tool.ts` | Writes generated test files to disk in the correct directory | `fs` |
| `diff-viewer` | `diff-viewer.tool.ts` | Generates unified diffs for suggested fix proposals | `diff` |
| `report-builder` | `report-builder.tool.ts` | Aggregates results into Allure JSON, JUnit XML, or HTML | `allure-js-commons` |
| `approval-gate` | `approval-gate.tool.ts` | Blocks execution and waits for human approve/reject signal via CLI prompt, WebSocket, or GitHub PR comment | native |
| `git-tools` | `git-tools.tool.ts` | Opens PRs, creates branches, commits suggested fixes post-approval | `simple-git` |

---

## 8. Human Approval Gate (Semi-Autonomous Flow)

```
Agent Run Complete
       │
       ▼
  Failures Found?
  ┌────┴────┐
 No        Yes
  │          │
  ▼          ▼
Report    Present failures + suggested fixes
           │
           ▼
     Human reviews via:
     • CLI: ataf approve --session <id>
     • REST: POST /sessions/:id/approve
     • GitHub PR comment: /ataf approve
           │
     ┌─────┴──────┐
  Approve       Reject
     │              │
     ▼              ▼
 git-tools     Log reason,
 applies fix   re-run or close
     │
     ▼
  Re-run tests to confirm fix
     │
     ▼
  Final Report
```

### Approval Gate States (FSM)

| State | Description |
|---|---|
| `pending` | Tests running |
| `awaiting_approval` | Failures found; fix proposals presented to human |
| `approved` | Human accepted; applying fixes |
| `rejected` | Human rejected; session closed or re-queued |
| `re-running` | Fixes applied; tests re-executing |
| `completed` | All tests pass; report generated |
| `failed` | Unrecoverable failure |

---

## 9. Configuration File (`ataf.config.yaml`)

```yaml
version: "1.0"

registries:
  agents_dir: "./agents"
  skills_dir: "./skills"
  tools_dir: "./tools"

orchestrator:
  default_model: "gpt-4o"
  session_ttl_minutes: 60
  parallel_agents: 3

agents:
  enabled:
    - playwright
    - api-test
    - performance
    - unit-integration
    - visual-regression
    - cucumber

approval_gate:
  mode: "cli"           # cli | rest | github-pr
  timeout_minutes: 30

reporting:
  formats:
    - allure
    - junit
    - html
  output_dir: "./test-results"

ci:
  github_actions:
    enabled: true
    webhook_url: "${GITHUB_WEBHOOK_URL}"
```

---

## 10. GitHub Copilot SDK — Extension Manifest

```json
{
  "name": "ataf",
  "description": "AutoTest Agent Framework — automated test generation and execution",
  "homepage_url": "https://your-domain.com/ataf",
  "callback_url": "https://your-domain.com/ataf/copilot/callback",
  "request_url": "https://your-domain.com/ataf/copilot/events",
  "pre_authorization_url": "https://your-domain.com/ataf/copilot/pre-auth",
  "public": true,
  "capabilities": {
    "read_repository": true,
    "write_repository": false
  }
}
```

---

## 11. Cloud Microservice Deployment

### Container Structure

```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY dist/ ./dist/
COPY agents/ ./agents/
COPY skills/ ./skills/
COPY tools/ ./tools/
EXPOSE 3000
CMD ["node", "dist/server/app.js"]
```

### Infrastructure (Recommended)

| Component | Technology |
|---|---|
| API Server | Fastify on Node.js 22 |
| Session State | Redis (session TTL, approval FSM) |
| Test Results | PostgreSQL (long-term storage) |
| Message Queue | BullMQ (agent job queue) |
| Scaling | Kubernetes HPA on CPU/queue depth |
| Secrets | GitHub Actions OIDC / AWS Secrets Manager |

---

## 12. Adding a New Agent (Extensibility)

To add a new testing agent (e.g., Accessibility/a11y):

1. Create `agents/a11y.agent.md` with frontmatter: `id`, `skills`, `tools`, `triggers`
2. Create `skills/generate-a11y-tests.skill.md` with instructions for axe-core test generation
3. Create `tools/axe-runner.tool.ts` implementing the `Tool` interface
4. Add `a11y` to `ataf.config.yaml` under `agents.enabled`
5. Restart ATAF — the registries hot-reload automatically

No code changes to the orchestrator or existing agents are required.

---

## 13. Key Design Principles

**Plugin-first:** Every agent, skill, and tool is a file. Swap, extend, or disable any capability without touching core orchestrator code.

**Semi-autonomous by design:** The approval gate is a first-class FSM state, not an afterthought. Agents never self-apply fixes.

**GitHub Copilot SDK as the AI backbone:** All LLM calls route through the Copilot SDK endpoint, enabling GitHub Copilot chat, VSCode Copilot integration, and enterprise auth out of the box.

**Dual deployment:** The same agent/skill/tool core runs identically in CLI mode (for developer workstations and CI pipelines) and as a Fastify microservice (for shared team access, webhooks, and long-running sessions).

**Data-driven by default:** The Cucumber agent's `data-driven-expansion` skill generates Scenario Outline example tables from data sources (CSV, JSON, database) without requiring custom code per project.
