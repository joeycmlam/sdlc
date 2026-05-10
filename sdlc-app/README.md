# mypoc — Full-Stack Monorepo

A full-stack monorepo for proof-of-concept (POC) projects, combining a **Next.js** frontend with independent **Python** backend services.

## Structure

```
mypoc/
├── app/               # Next.js App Router (pages, API routes, layouts)
├── components/        # React UI components
├── lib/               # Shared TypeScript utilities (utils.ts, types.ts, api.ts)
├── services/          # Python backend services (each service is self-contained)
│   ├── copilot-agent/ # FastAPI server + LLM agent runner
│   ├── jira-cli/      # Jira CLI tool for reading/writing tickets
├── docs/              # Architecture diagrams and design documents
└── .github/           # GitHub and workspace configuration
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | ≥ 18 | Next.js frontend |
| pnpm | ≥ 8 | Node package manager |
| Python | ≥ 3.9 | Python services |
| GitHub CLI (`gh`) | latest | Copilot agent auth |

---

## 1. Frontend — Next.js UI

A single unified UI for the `copilot-agent` API server. Three pages share a common shell with a top nav:

| Route | Purpose | Backend it talks to |
|-------|---------|---------------------|
| `/`             | Chat — single-shot streaming run via `/stream` (in-process)   | api_server only |
| `/sessions`     | List of worker-pool sessions, polled every 5s                | api_server + Redis |
| `/sessions/[id]` | Session detail with live SSE event stream + approve/reject  | api_server + worker + Redis Streams |
| `/issues/new`   | Create a GitHub issue and (optionally) assign to Copilot     | api_server + GitHub REST |
| `/settings`     | Backend health / Redis status / UI-side backend URL          | api_server only |

The chat page covers quick interactive runs; the `/sessions/*` pages cover multi-step workflows that go through the Arq worker pool (BA-on-Jira, etc.); `/issues/new` is the entry point for the GitHub-cloud-agent path (engineering personas).

### Install dependencies

```bash
pnpm install
```

### Start development server

```bash
pnpm dev
```

The app is available at **http://localhost:3000**.

### Other commands

```bash
pnpm build    # Production build
pnpm start    # Start production server
pnpm lint     # Run ESLint
```

> The UI expects the `copilot-agent` API server at `http://localhost:8000` (override with `NEXT_PUBLIC_API_URL`). For the `/sessions/*` pages you also need Redis and at least one Arq worker — see [services/copilot-agent/README.md](services/copilot-agent/README.md#bringing-it-up--local-dev).

---

## 2. Backend Services

Each service under `services/` is fully independent with its own virtual environment and dependencies.

### copilot-agent (FastAPI + LLM Agent)

Full setup and usage instructions: [services/copilot-agent/README.md](services/copilot-agent/README.md)

**Quick start:**

```bash
cd services/copilot-agent

# One-time setup
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt

# Authenticate GitHub Copilot CLI (one-time)
gh extension install github/gh-copilot
gh auth login

# Start Redis (required for /sessions/* endpoints)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Start the Arq worker pool (required for /sessions/* endpoints)
agent-worker &

# Start the API server
agent-api --port 8000
```

Server runs at **http://localhost:8000**.

---

### jira-cli (Jira Issue Reader)

Full setup and usage instructions: [services/jira-cli/README.md](services/jira-cli/README.md)

**Quick start:**

```bash
cd services/jira-cli

# One-time setup
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt

# Configure credentials
cp .env.example .env               # then edit .env with your Jira URL, user, and API token

# Run
python jira_cli.py PROJECT-123
```

---

## Running the Full Stack

Open four terminals:

**Terminal 1 — Redis:**
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

**Terminal 2 — Arq Worker:**
```bash
cd services/copilot-agent
source .venv/bin/activate
agent-worker
```

**Terminal 3 — API Server:**
```bash
cd services/copilot-agent
source .venv/bin/activate
agent-api --port 8000
```

**Terminal 4 — Frontend:**
```bash
pnpm dev
```

Then open **http://localhost:3000** in your browser.

---

For more information, see [Copilot Instructions](.github/copilot-instructions.md)
