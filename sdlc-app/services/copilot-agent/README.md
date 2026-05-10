# copilot-agent — GitHub Copilot / GitHub Models CLI Agent

Two CLI agents — choose the one that matches your setup:

## Quick Start

```bash
# 1. Authenticate (one-time)
gh extension install github/gh-copilot
gh auth login

# 2. Set up the virtual environment (one-time)
cd services/copilot-agent
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt

# 3a. Run the CLI agent (no Redis / worker needed)
python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Hello"

# 3b. OR run the full API stack (3 processes — see "Bringing it up" below)
docker run -d --name redis -p 6379:6379 redis:7-alpine    # Redis
agent-worker &                                             # Arq worker pool
agent-api --port 8001                                      # FastAPI (http://localhost:8001)
```


| Script | SDK / Backend | Auth | Needs Redis? |
|--------|---------------|------|--------------|
| `agent_copilot.py`  | `github-copilot-sdk`            | Copilot CLI OAuth — **recommended** | no |
| `agent.py`          | `azure-ai-inference`            | `GITHUB_TOKEN` env var              | no |
| `api_server.py` `/run`,`/stream` | FastAPI (in-process) | inherited from agent module        | no |
| `api_server.py` `/sessions/*`    | FastAPI + Arq + Redis Streams | inherited from agent module        | **yes** |
| `worker.py`         | Arq worker pool                 | inherited from agent module         | **yes** |

---

## agent_copilot.py — GitHub Copilot SDK Edition (Recommended)

Built on the **`github-copilot-sdk`** Python package, which delegates to the GitHub Copilot CLI running locally. No `GITHUB_TOKEN` is required — authentication is handled by the Copilot CLI's own credential store.

### Key Features

- **Two built-in tools** exposed to the model:
  - `bash_exec` — runs any shell command (async, 120 s timeout)
  - `invoke_agent` — delegates a sub-task to a specialised sub-agent (isolated session, own turn budget, depth-guarded)
- **`--max-turns`** flag — configurable turn budget (default 20, max 50), ideal for complex multi-step workflows
- **Async** throughout (`asyncio` / `async-await`)
- Access to any model available via the Copilot CLI (GPT-4o, Claude, etc.)

### Prerequisites

```bash
# Install the GitHub CLI and Copilot extension, then authenticate:
gh extension install github/gh-copilot
gh auth login
```

### Setup

```bash
cd services/copilot-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Usage

```
python agent_copilot.py -a <agent-file> -m <model> [-i <instruction>] [--interactive] [--no-stream] [--max-turns N]
python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "Please provide the analysis of JIRA https://joeycmlam-1762529818344.atlassian.net/browse/SCRUM-9"
```

#### Arguments

| Flag | Description |
|------|-------------|
| `-a`, `--agent-file` | **(required)** Agent Markdown/text file containing the system prompt |
| `-m`, `--model` | Model name available via Copilot CLI (default: `gpt-4o`) |
| `-i`, `--instruction` | User instruction / prompt (single-shot mode) |
| `--interactive` | Start a multi-turn chat session |
| `--no-stream` | Disable streaming; wait for the full response |
| `--max-turns N` | Max turns per run (default: 20, max: 50). Increase for complex workflows |

### Examples

**Single-shot**
```bash
python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Explain recursion in simple terms"
```

**BA workflow with extended turn budget**
```bash
python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "please analyze the jira SCRUM-12" --max-turns 40
```

**Pipe from stdin**
```bash
cat main.py | python agent_copilot.py -a agents/coder.md -m gpt-4o -i "Review this code"
echo "What is a monad?" | python agent_copilot.py -a agents/assistant.md -m gpt-4o
```

**Interactive multi-turn chat**
```bash
python agent_copilot.py -a agents/coder.md -m gpt-4o --interactive
```

**Different models**
```bash
python agent_copilot.py -a agents/assistant.md -m claude-sonnet-4-6 -i "Hello"
python agent_copilot.py -a agents/assistant.md -m gpt-4o-mini -i "Hello"
```

### Interactive Mode Commands

| Input | Action |
|-------|--------|
| `exit` / `quit` | End the session |
| `Ctrl+C` / `Ctrl+D` | Exit immediately |

---

## api_server.py — REST API / SSE Mode (Redis-backed)

`api_server.py` exposes `AgentRunner` as a **FastAPI HTTP service**. It comes in two flavours that share the same process:

1. **Stateless endpoints** — `POST /run` and `POST /stream` execute the agent in-process and return immediately. No Redis or worker needed.
2. **Stateful sessions** — `POST /sessions/...` persist state in Redis, hand work off to an Arq worker pool, and stream events back via Redis Streams. This is the multi-pod, horizontally-scalable path.

```
        ┌────────────────┐         enqueue         ┌────────────────┐
client →│  api_server.py │ ──────────────────────→ │   worker.py    │ → AgentRunner
        │   (FastAPI)    │                         │   (Arq)        │
        │  /sessions/*   │ ←───── publish events ──│ run_session_job│
        └───────┬────────┘                         └───────┬────────┘
                │                                          │
                └──────────────── Redis ───────────────────┘
                  session:{id}  events:{id}  arq:queue
```

Three independently scalable processes: **Redis**, **N × api_server**, **N × worker**. The api_server replicas are stateless; you can run as many as you like behind a load balancer.

### Components

| Module | Role | Scalable to N processes? |
|--------|------|--------------------------|
| `api_server.py`  | FastAPI control plane (CRUD + SSE fan-in)  | ✅ |
| `worker.py`      | Arq worker — runs `AgentRunner` jobs       | ✅ |
| `session_store.py` | Pydantic `Session` ↔ Redis (`SET ex=24h`) | (library) |
| `event_bus.py`   | Per-session pub/sub on Redis Streams       | (library) |

### Setup

Requires the same virtual environment as `agent_copilot.py`. The extra dependencies (`fastapi`, `uvicorn`, `redis`, `arq`) are in `requirements.txt`.

```bash
cd services/copilot-agent
source .venv/bin/activate
pip install -r requirements.txt
# (or, if using the wheel)
pip install -e .
```

Set `REDIS_URL` if Redis is not at the default `redis://localhost:6379/0`:

```bash
cp .env.example .env       # then edit REDIS_URL if needed
export REDIS_URL=redis://localhost:6379/0
```

### Bringing it up — local dev

Open three terminals (or use `tmux` / a process manager).

**Terminal 1 — Redis**

```bash
# Easiest: Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Or Homebrew
brew install redis && brew services start redis

# Verify
redis-cli ping            # → PONG
```

**Terminal 2 — Arq worker pool**

```bash
cd services/copilot-agent
source .venv/bin/activate
agent-worker              # or: arq worker.WorkerSettings
```

You should see Arq log lines like `Starting worker for 1 functions: run_session_job`. Launch more terminals to scale workers horizontally — each worker handles up to 10 concurrent jobs (`WorkerSettings.max_jobs`).

**Terminal 3 — API server**

```bash
cd services/copilot-agent
source .venv/bin/activate
agent-api --port 8001     # or: python api_server.py --port 8001
```

Confirm the wiring is healthy:

```bash
curl http://localhost:8001/health
# → {"status":"ok","redis":true}
```

If you only need the **stateless** `/run` and `/stream` endpoints, skip Terminals 1 & 2 — those endpoints don't touch Redis or the worker.

### Bringing it up — Docker Compose (recommended for shared dev)

Use a `docker-compose.yml` similar to:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  worker:
    build: .
    command: agent-worker
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on: { redis: { condition: service_healthy } }
    deploy: { replicas: 2 }

  api:
    build: .
    command: agent-api --host 0.0.0.0 --port 8001
    ports: ["8001:8001"]
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on: { redis: { condition: service_healthy } }
    deploy: { replicas: 2 }
```

Then `docker compose up -d` brings the whole stack online.

### Endpoints

| Method | Path | Backed by | Description |
|--------|------|-----------|-------------|
| `GET`    | `/health`                 | api+Redis | Liveness check → `{"status":"ok","redis":true}` |
| `GET`    | `/agents`                 | api       | List registered agents + all `.md` files |
| `GET`    | `/agents/content?file=…`  | api       | Agent file content + parsed frontmatter |
| `GET`    | `/skills`                 | api       | List registered skills |
| `POST`   | `/run`                    | api       | Blocking, in-process run → `{"content":"…"}` |
| `POST`   | `/stream`                 | api       | SSE, in-process |
| `POST`   | `/sessions`               | Redis     | Create a session (does not start it) |
| `GET`    | `/sessions/{id}`          | Redis     | Get session state |
| `POST`   | `/sessions/{id}/run`      | Arq+Redis | Enqueue session for the worker pool |
| `GET`    | `/sessions/{id}/events`   | Redis Streams | SSE stream of session events |
| `POST`   | `/sessions/{id}/approve`  | Redis     | Approve / reject an `awaiting_approval` session |
| `GET`    | `/sessions/{id}/result`   | Redis     | Get final result + state + error |
| `DELETE` | `/sessions/{id}`          | Redis     | Delete session (does not cancel an in-flight job) |
| `GET`    | `/sessions`               | Redis     | List live sessions (newest first, `?limit=` param) |
| `POST`   | `/github/issues`          | GitHub REST | Create an issue and (optionally) assign Copilot cloud agent |

### Request body (`POST /run` and `POST /stream`)

```json
{
  "agent_file": "agents/assistant.md",
  "instruction": "Explain recursion",
  "model": "gpt-4o",
  "max_turns": 20,
  "extra_context": ""
}
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `agent_file` | yes | — | Relative path to an agent `.md` file |
| `instruction` | yes | — | The user prompt / task |
| `model` | no | `gpt-4o` | Any model available via the Copilot CLI |
| `max_turns` | no | `20` | Turn budget (capped at 50) |
| `extra_context` | no | `""` | Optional extra text prepended to the first message |

### Request body (`POST /sessions`)

Adds optional Jira / Confluence / GitHub fields that the worker injects as additional context:

```json
{
  "agent_file": "agents/ba.agent.md",
  "instruction": "Refine SCRUM-12",
  "model": "gpt-4o",
  "max_turns": 40,
  "jira_url": "https://example.atlassian.net/browse/SCRUM-12",
  "confluence_pages": ["https://example.atlassian.net/wiki/.../page"],
  "create_github_issue": false
}
```

### SSE event types

Both `POST /stream` and `GET /sessions/{id}/events` emit the same `data: <JSON>\n\n` events:

| `type` | Payload | Description |
|--------|---------|-------------|
| `state` | `{"type":"state","state":"running"}` | (sessions only) Session FSM transition |
| `chunk` | `{"type":"chunk","content":"..."}` | Incremental assistant text delta |
| `tool` | `{"type":"tool","name":"..."}` | Tool invocation started |
| `done` | `{"type":"done","content":"..."}` | Final complete response; stream ends |
| `error` | `{"type":"error","message":"...","code":500}` | Unhandled exception during the run |

`/sessions/{id}/events` replays from the start of the stream, so SSE clients that connect after `/run` was issued still see the full transcript.

### Examples — stateless

**Health check**
```bash
curl http://localhost:8001/health
```

**Blocking run**
```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"agent_file":"agents/assistant.md","instruction":"what is 2+2","model":"gpt-4o"}'
```

**SSE streaming run** (chunks appear in real time)
```bash
curl -N -X POST http://localhost:8001/stream \
  -H "Content-Type: application/json" \
  -d '{"agent_file":"agents/assistant.md","instruction":"what is 2+2","model":"gpt-4o"}'
```

### Examples — stateful sessions (worker pool)

**Full BA flow with live SSE**
```bash
# 1. Create the session
SID=$(curl -s -X POST http://localhost:8001/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "agent_file": "agents/ba.agent.md",
    "instruction": "please analyze the jira SCRUM-12",
    "model": "gpt-4o",
    "max_turns": 40
  }' | jq -r .id)
echo "session: $SID"

# 2. Subscribe to events FIRST (background)
curl -N "http://localhost:8001/sessions/$SID/events" &

# 3. Enqueue execution — picked up by the worker pool
curl -X POST "http://localhost:8001/sessions/$SID/run"

# 4. Final result (after stream ends)
curl "http://localhost:8001/sessions/$SID/result"
```

**Approval flow** (when a session enters `awaiting_approval`):
```bash
curl -X POST "http://localhost:8001/sessions/$SID/approve" \
  -H "Content-Type: application/json" \
  -d '{"action":"approve","comment":"LGTM"}'
```

### Examples — GitHub issue creation + Copilot cloud-agent assignment

`POST /github/issues` is a thin wrapper over GitHub's REST API. The server adds the special `Copilot` user to the issue's assignees when `assign_to_copilot` is `true` — GitHub's coding agent then picks up the issue automatically (provided Copilot is enabled on the target repo).

**Required env on the API server**

```bash
export GH_TOKEN=ghp_...   # PAT with 'repo' scope (Issues: write)
                          # GITHUB_TOKEN also works as a fallback
```

`agent_copilot.py` strips `GH_TOKEN`/`GITHUB_TOKEN` from the environment at import time so the Copilot CLI uses its own keyring; `api_server.py` snapshots the value before that strip happens, so setting it in the API server's environment is sufficient.

**Create an issue assigned to Copilot**

```bash
curl -X POST http://localhost:8001/github/issues \
  -H "Content-Type: application/json" \
  -d '{
    "owner": "my-org",
    "repo":  "my-repo",
    "title": "Add /v2/quote endpoint",
    "body":  "## Goal\nReplace the /quote endpoint…\n\n## Acceptance\n- [ ] …",
    "assign_to_copilot": true,
    "labels": ["enhancement", "agent:backend"],
    "custom_agent": "backend-agent"
  }'
```

Response:

```json
{
  "number": 42,
  "html_url": "https://github.com/my-org/my-repo/issues/42",
  "state": "open",
  "assignees": ["Copilot"],
  "title": "Add /v2/quote endpoint",
  "copilot_assigned": true
}
```

If GitHub silently drops the `Copilot` assignee (e.g. the repo doesn't have the coding agent enabled), the issue is still created and `copilot_assigned` returns `false` — the UI surfaces a warning in that case.

The same endpoint is what `agent_copilot.py`'s `create_github_issue` tool now calls internally, so SDK-driven sessions and the UI form go through the same path.

### Production-style start with multiple workers

```bash
# Redis (one)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 4 worker processes (each handles up to 10 concurrent jobs)
for i in 1 2 3 4; do
  REDIS_URL=redis://localhost:6379/0 agent-worker &
done

# 2 api replicas behind a reverse proxy
REDIS_URL=redis://localhost:6379/0 agent-api --port 8001 &
REDIS_URL=redis://localhost:6379/0 agent-api --port 8002 &
```

### Tuning knobs

| Setting | Where | Default | What it controls |
|---------|-------|---------|------------------|
| `max_jobs` | `worker.WorkerSettings` | 10 | Concurrent sessions per worker process |
| `job_timeout` | `worker.WorkerSettings` | 600 s | Hard limit per session run |
| `_SESSION_TTL_SECONDS` | `session_store.py` | 24 h | Session JSON TTL in Redis |
| `_STREAM_TTL_SECONDS` | `event_bus.py` | 24 h | Event-stream TTL in Redis |
| `_MAX_STREAM_LEN` | `event_bus.py` | 10 000 | Max events kept per session stream |
| `max_idle_blocks` | `EventBus.subscribe` | 10 × 30 s | SSE subscriber gives up after 5 min idle |
| `MAX_TURNS_LIMIT` | `agent_copilot.py` | 50 | Hard cap on `max_turns` per session |

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/health` returns `{"redis": false}` | Redis not running or wrong URL | `redis-cli ping`; check `REDIS_URL` |
| `POST /sessions/{id}/run` succeeds but events never appear | No worker process running | Start `agent-worker` |
| `arq.connections.RedisSettings` connection refused | Redis bind address | Set `REDIS_URL` to `redis://<host>:6379/0` |
| Session stuck in `running` after worker crash | No Arq retry configured | Set `WorkerSettings.tries = 3` |
| SSE stream hangs forever | Subscriber connected before `/run` and worker never picked up | Confirm the worker is consuming the queue |

### Docker — multi-process

The image's default `ENTRYPOINT` is the CLI. Override with the appropriate command per container role:

```bash
# API
docker run -p 8001:8001 -e REDIS_URL=redis://redis:6379/0 <image> agent-api --port 8001

# Worker
docker run -e REDIS_URL=redis://redis:6379/0 <image> agent-worker
```

---

## agent.py — GitHub Models Edition

Built on the **[azure-ai-inference](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/ai/azure-ai-inference)** Python SDK. Authenticate with a GitHub personal access token to access any model on the GitHub Marketplace.

### Setup

```bash
cd services/copilot-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your GitHub token as an environment variable:

```bash
export GITHUB_TOKEN="github_pat_..."
```

> Create a token at <https://github.com/settings/tokens> — only **`models:read`** scope is needed.

### Usage

```
python agent.py -a <agent-file> -m <model> [-i <instruction>] [--interactive] [--no-stream]
```

#### Arguments

| Flag | Description |
|------|-------------|
| `-a`, `--agent-file` | **(required)** Agent Markdown/text file containing the system prompt |
| `-m`, `--model` | Model name from [github.com/marketplace/models](https://github.com/marketplace/models) (default: `gpt-4o`) |
| `-i`, `--instruction` | User instruction / prompt (single-shot mode) |
| `--interactive` | Start a multi-turn chat session |
| `--no-stream` | Disable streaming; wait for the full response |

### Examples

**Single-shot**
```bash
python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion in simple terms"
```

**Pipe from stdin**
```bash
cat main.py | python agent.py -a agents/coder.md -m gpt-4o -i "Review this code"
echo "What is a monad?" | python agent.py -a agents/assistant.md -m gpt-4o
```

**Interactive multi-turn chat**
```bash
python agent.py -a agents/coder.md -m gpt-4o --interactive
```

**Different models** (any name from the GitHub Marketplace):
```bash
python agent.py -a agents/assistant.md -m mistral-large -i "Hello"
python agent.py -a agents/assistant.md -m meta-llama-3.1-70b-instruct -i "Hello"
python agent.py -a agents/assistant.md -m Phi-3.5-MoE-instruct -i "Hello"
```

### Interactive Mode Commands

| Input | Action |
|-------|--------|
| `exit` / `quit` | End the session |
| `reset` | Clear conversation history (keeps system prompt) |
| `Ctrl+C` / `Ctrl+D` | Exit immediately |

### Available Models (GitHub Marketplace)

Browse all available models at <https://github.com/marketplace/models>.  
Notable ones include:

| Model | Provider |
|-------|----------|
| `gpt-4o` | OpenAI |
| `gpt-4o-mini` | OpenAI |
| `mistral-large` | Mistral |
| `meta-llama-3.1-70b-instruct` | Meta |
| `Phi-3.5-MoE-instruct` | Microsoft |
| `AI21-Jamba-1.5-Large` | AI21 Labs |

---

## Agent Files

Agent files (`agents/*.agent.md`) are Markdown files with YAML frontmatter that define the **system prompt** and routing metadata used by the `AgentRegistry`.

### ATAF Frontmatter Schema

```yaml
---
id: my-agent              # unique ID used by the registry
name: "My Agent"          # human-readable display name
description: "..."        # shown in /agents; used for routing hints
triggers:                 # regex patterns matched against user input
  - "pattern one|variant"
  - "another pattern"
skills: [bdd-scenarios]   # skill IDs injected into context
tools: [read, search, edit, execute, agent]
argument-hint: "..."      # hint shown in the UI
---
```

### Bundled Agents

```
agents/
  assistant.md                  # General-purpose assistant
  coder.md                      # Software engineering focused
  jira-reader.md                # Reads and summarises Jira issues
  ba.agent.md                   # Business analyst — Jira analysis & requirements
  jira-test-automator.agent.md  # Generates automated tests from Jira stories
  test-designer.agent.md        # BDD test scenario design from requirements
  test-analyst.agent.md         # Test coverage analysis and mutation testing
  e2e-tester.md                 # Playwright end-to-end test authoring
```

Create your own for any persona or task:

```markdown
# agents/data_scientist.md
You are a senior data scientist. Respond with concise Python code using
pandas and matplotlib. Explain each step briefly.
```

Then run:
```bash
python agent_copilot.py -a agents/data_scientist.md -m gpt-4o -i "Plot a sine wave"
```

---

## Skill Files

Skills (`skills/*.skill.md`) are reusable knowledge documents loaded by `SkillRegistry` at startup. Agents declare which skills they use via the `skills:` frontmatter key.

### ATAF Frontmatter Schema

```yaml
---
id: bdd-pytest            # unique ID referenced by agents
name: bdd-pytest          # human-readable name
description: "..."        # shown in /skills
argument-hint: "..."      # hint shown in the UI
---
```

### Bundled Skills

| ID | Description |
|----|-------------|
| `bdd-scenarios` | Gherkin scenario authoring guide |
| `bdd-pytest` | pytest-bdd feature files and step definitions |
| `bdd-playwright` | Playwright BDD with `playwright-bdd` |
| `bdd-cucumber-node` | Cucumber.js BDD for Node.js / TypeScript |
| `read-jira` | Fetching and analysing Jira issues via `jira-cli` |

Check registered skills at runtime:

```bash
curl http://localhost:8000/skills
```

---

## Packaging

The project uses `pyproject.toml` with `setuptools` as the build backend.

### Install as an editable package (development)

```bash
cd services/copilot-agent
pip install -e .
```

This registers four console entry points so you can run the agents from anywhere in your shell:

```bash
agent-copilot -a agents/assistant.md -m gpt-4o -i "Hello"   # → agent_copilot.py
agent-api --port 8001                                        # → api_server.py
agent-worker                                                 # → worker.py (Arq worker pool)
copilot-agent -a agents/assistant.md -m gpt-4o -i "Hello"   # → agent.py (legacy)
```

### Build a distributable wheel

```bash
cd services/copilot-agent
pip install build
python -m build
```

Outputs are placed in `dist/`:

```
dist/
  copilot_agent-1.0.0-py3-none-any.whl
  copilot_agent-1.0.0.tar.gz
```

### Install from the wheel

```bash
pip install dist/copilot_agent-1.0.0-py3-none-any.whl
```

### pyproject.toml overview

| Setting | Value |
|---------|-------|
| Build backend | `setuptools` |
| Package name | `copilot-agent` |
| Version | `1.0.0` |
| Python requirement | `>=3.9` |
| Entry point `copilot-agent` | `agent:main` (`agent.py`) |
| Entry point `agent-copilot` | `agent_copilot:main` (`agent_copilot.py`) |
| Entry point `agent-api` | `api_server:cli_main` (`api_server.py`) |
| Entry point `agent-worker` | `worker:cli_main` (`worker.py`) |
| Bundled modules | `agent`, `agent_copilot`, `api_server`, `registry`, `session_store`, `event_bus`, `worker` |
| Runtime deps (Redis path) | `redis>=5.0`, `arq>=0.26` (in addition to FastAPI/uvicorn) |
