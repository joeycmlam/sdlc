

## What Is an Agent Harness?

An **agent harness** is the engineered software wrapper that surrounds an LLM with tools, context, control loops, sandboxes, memory, and validators — turning raw model calls into a reliable, repeatable pipeline. It handles the Observe → Orient → Decide → Act loop, where the harness owns the first two and last phases, and the LLM owns only the "Decide" step. For automated testing, the harness orchestrates test generation, execution, evaluation, and regression reporting without human intervention.[1][2]

***

## Phase 1: Define Your Architecture

Before writing code, establish the four core layers of the harness:

- **Orchestrator Agent** — the "brain" that reads a spec (e.g., AppSpec JSON or Product Requirement Document) and delegates tasks to sub-agents[3]
- **Sub-Agents** — context-isolated agents for specific concerns: test generation, test execution, validation, and reporting[4]
- **Tool Layer** — integrations with CI/CD, ticketing (Linear/Jira), source control (GitHub), and observability (MLflow, OpenTelemetry)[5][3]
- **Evaluation Engine** — the scoring layer using "LLM-as-a-Judge", deterministic comparators, and golden datasets[6][5]

For financial services, add a **Security & Governance layer** — define permission boundaries, secret management, and audit logging per agent from day one.[7]

***

## Phase 2: Build the Golden Dataset

The golden dataset is your **single source of truth** for correctness. Follow these steps:[6]

1. **Curate ground-truth Q&A pairs** — human-approved inputs and expected outputs, immutably versioned (treat them like code via dataset PRs)
2. **Define deterministic vs. non-deterministic test cases** — use exact-match comparators for structured fields (account numbers, trade IDs) and semantic similarity scores for free-text outputs
3. **Generate adversarial scenarios** — use rule-constrained agents to automatically produce edge cases, distributional shifts, and permutations[6]
4. **Gate with human-in-the-loop approval** — all newly generated test cases require SME sign-off before entering the golden set[5]

***

## Phase 3: Implement the Core Harness

### 3.1 — AppSpec / Task Definition File
Create a structured JSON spec that serves as the single source of truth for the orchestrator:[3]

```json
{
  "project": "trade-validation-agent-tests",
  "agents": {
    "planner": { "model": "claude-sonnet", "prompt_file": "planner.md" },
    "tester":  { "model": "claude-haiku",  "prompt_file": "tester.md" },
    "evaluator": { "model": "claude-sonnet", "prompt_file": "evaluator.md" }
  },
  "golden_dataset": "data/golden_v1.json",
  "quality_gates": { "min_pass_rate": 0.95, "semantic_threshold": 0.85 }
}
```

### 3.2 — The Execution Loop
The harness follows this pipeline:[2][8]

1. **Planner Agent** reads the AppSpec and decomposes it into discrete test tasks
2. **Tester Agent** generates test cases (initial pass), run in isolated context windows to avoid cross-contamination[3]
3. **Inspector/Validator Agent** verifies test correctness and code coverage, iterating in a loop until coverage thresholds are met[8]
4. **Evaluator Agent** scores outputs against golden data using multi-metric evaluation (accuracy, faithfulness, groundedness, safety, latency)[9]
5. **Reporter Agent** aggregates results, computes pass/fail grades, and posts to CI/CD and Slack/email[4]

### 3.3 — Multi-Metric Evaluation Pipeline
Wire up the five key metrics in parallel:[9]

| Metric | Method | Tool |
|---|---|---|
| **Accuracy** | Exact match + F1 against golden data | Custom comparator |
| **Faithfulness** | LLM-as-a-Judge vs. source documents | Claude / GPT-4o Judge |
| **Semantic Similarity** | Embedding cosine distance | sentence-transformers |
| **Safety / Hallucination** | Automated red-team probe | Giskard / Ragas |
| **Latency / Cost** | P50/P95 timing + token count | MLflow Tracing [5] |

***

## Phase 4: Add Observability

Instrument every agent call with distributed tracing from day one:[5]

- **MLflow Tracing** (built on OpenTelemetry) — captures step-by-step traces for multi-agent architectures, enabling root-cause analysis when tests fail
- **AI Insights** — use an "agent-of-agents" pattern to automatically read traces and surface issues[5]
- Emit structured spans: `agent_name`, `model`, `tokens_in/out`, `latency_ms`, `tool_calls`, `pass_fail`
- Store traces in a Unity Catalog table (or equivalent) for SQL-queryable KPIs and regression detection[5]

***

## Phase 5: CI/CD Integration & Quality Gates

Connect the harness to your delivery pipeline:[6]

1. **Trigger on PR** — run the evaluation harness against a staging version of the agent on every pull request
2. **Automated rollback rules** — if `pass_rate < 0.95` or any safety metric degrades, block the merge and trigger automated rollback[6]
3. **Canary validation** — deploy to 5% of traffic and run live shadow scoring before full promotion[6]
4. **Regression reporting** — publish a diff report comparing current vs. baseline golden dataset scores, with highlighted regressions[10]

For a Python-based evaluation harness in regulated industries, the pattern is: execute golden dataset queries against the staging agent → parse execution traces → calculate a pass/fail grade → gate deployment.[10]

***

## Phase 6: Context Isolation & Long-Running Agent Pattern

The #1 failure mode in harnesses is **context window overflow**. Mitigate this by:[3]

- Running each sub-agent task in a **fresh context window** — never accumulate all history in one session[3]
- Using **Anthropic's long-running agent harness** pattern (persistence + progress tracking across sessions) for tasks exceeding a single context window[4]
- Passing only the task-relevant state (delta, not full history) between agent handoffs

***

## Phase 7: Security & Governance (Financial Services Critical)

Given your asset management context, enforce these controls:[7]

- **LLM connector governance** — declare which model (Anthropic/OpenAI/Gemini) is permitted per agent type, enforced via config
- **Secret management** — use a vault (HashiCorp Vault or cloud KMS) for API keys; never embed in agent prompts
- **Audit log** — every agent action, tool call, and output is immutably logged with timestamps and agent identity
- **Human-in-the-loop gates** — for any agent that writes to production systems (trade validation, compliance checks), require mandatory human approval before execution

***

## Recommended Stack

| Layer | Tool |
|---|---|
| Orchestration | Claude Agents SDK / LangGraph |
| Evaluation | MLflow Tracing + Ragas |
| Golden Data Store | Git-versioned JSON + DVC |
| CI/CD Gate | GitHub Actions / Harness CI |
| Observability | OpenTelemetry → Datadog/Splunk |
| Auth & MCP | Arcade MCP Gateway [4] |

This framework gives you a production-grade, auditable, and extensible agent harness that satisfies both engineering rigour and the compliance requirements typical in global asset management.[10][6]

Sources
[1] Toward Executable, Verifiable, and Stateful Agent Systems ◆ https://arxiv.org/html/2605.18747v1
[2] Building AI Agents the Claude Code Way - ClaudeCodeLab https://claudecode-lab.com/en/blog/claude-code-harness-engineering/
[3] How to Turn Claude Code into a Full Engineering Team (Agent Harnesses Explained) https://www.youtube.com/watch?v=xmB2oHoEKes
[4] Turn Claude Code into Your Full Engineering Team with Subagents https://www.youtube.com/watch?v=-GyX21BL1Nw
[5] How to Test GenAI Agents in Production: MLflow Tracing & Evaluation Deep Dive https://www.youtube.com/watch?v=J92rI0IUmAI&list=PLaoPu6xpLk9GcoEL8bEAdV76mNVwlA7-k&index=1&trk=article-ssr-frontend-pulse_little-text-block
[6] How to build auditable GenAI test platforms with a solution ... https://www.linkedin.com/posts/sainathkumar_genai-aitesting-machinelearning-activity-7377697418408255488-HXBy
[7] Security And Governance​ https://developer.harness.io/docs/platform/harness-aida/harness-agents/
[8] Multi-Agent LLMs for End-to-End Test Generation with Accurate ... https://arxiv.org/html/2506.02943v3
[9] GenAI Testing Framework. 🎯 Overview | by Ankit Tripathi https://medium.com/@2022aiml554/genai-testing-framework-a8cf91a870cd
[10] The AI Litmus test: Scientifically evaluating GenAI Playbook Agents https://discuss.google.dev/t/the-ai-litmus-test-scientifically-evaluating-genai-playbook-agents/340720
[11] [PDF] Harness GenAI in Test Automation Frameworks - Directory Listing / https://docbox.etsi.org/workshop/2025/04_UCAAT/00_TUTORIAL_WORKSHOP_TESTHATON/TUTORIAL_2_ANDREEA_COSARIU.pdf
[12] RUCAIBox/awesome-agent-harness: The official ... https://github.com/RUCAIBox/awesome-agent-harness
[13] How We Built a Multi-Agent AI System with Claude Code https://www.epam.com/insights/ai/blogs/step-by-step-guide-to-building-a-multi-agent-claude-code-ai-development-team
[14] Agent Harness Engineering: A Survey https://picrew.github.io/LLM-Harness/main.pdf
[15] Multi-Agent Pipeline - rohitg00/awesome-claude-code-toolkit - GitHub https://github.com/rohitg00/awesome-claude-code-toolkit/blob/main/examples/multi-agent-pipeline.md
