# SDLC AI Agent Platform

An intelligent, multi-agent platform for automating Software Development Lifecycle (SDLC) workflows across Jira, Confluence, GitHub, and development tooling. Built on the GitHub Copilot SDK with specialized AI agents for business analysis, test automation, documentation, and code generation.

## 🏗️ Architecture Overview

The platform consists of four primary components orchestrated through Docker Compose:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│                      http://localhost:3000                          │
└────────────────────┬────────────────────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┬──────────────────┐
    │                │                │                  │
    ▼                ▼                ▼                  ▼
┌─────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐
│  Redis  │  │ Copilot      │  │ Atlassian    │  │   Arq    │
│  :6379  │  │ Agent API    │  │ Bridge       │  │  Worker  │
│         │  │ :8001        │  │ :8002        │  │  Pool    │
└─────────┘  └──────────────┘  └──────────────┘  └──────────┘
     │              │                  │                │
     └──────────────┴──────────────────┴────────────────┘
                Session State & Event Streams
```

### Component Responsibilities

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Next.js 16, React 19, Tailwind CSS 4 | Web UI for chat, sessions, issue creation, settings |
| **Copilot Agent API** | FastAPI, GitHub Copilot SDK | LLM agent orchestration, tool execution, session management |
| **Atlassian Bridge** | FastAPI, httpx | Jira REST API v3 + Confluence REST API v2 proxy |
| **Arq Worker Pool** | Arq, asyncio | Async job processing for long-running agent workflows |
| **Redis** | Redis 7 | Session state, event streams (Redis Streams), job queue |

---

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose** (v2.0+)
- **Node.js** ≥ 18 (for local development)
- **Python** ≥ 3.11 (for local development)
- **GitHub CLI** with Copilot extension:
  ```bash
  gh extension install github/gh-copilot
  gh auth login
  ```

### Running with Docker Compose (Recommended)

1. **Clone and configure environment:**
   ```bash
   git clone <repository-url>
   cd sdlc
   cp .env.example .env
   # Edit .env with your credentials:
   # - JIRA_URL, JIRA_USER, JIRA_API_TOKEN
   # - GH_TOKEN (GitHub Personal Access Token)
   # - ATLASSIAN_* credentials
   ```

2. **Start all services:**
   ```bash
   docker compose up --build
   ```

3. **Access the platform:**
   - Frontend: http://localhost:3000
   - Copilot Agent API: http://localhost:8001
   - Atlassian Bridge: http://localhost:8002
   - API Docs: http://localhost:8001/docs

### Local Development (without Docker)

Run each service in a separate terminal. Start them in the order below.

#### 1. Redis (required for sessions and worker)

```bash
# Using Docker for Redis only
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Or via Homebrew (macOS)
brew install redis && brew services start redis
```

#### 2. Atlassian Bridge

```bash
cd atlassian-bridge

# One-time setup
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -e .

# Configure credentials
cp .env.example .env             # edit with JIRA_URL, JIRA_USER, JIRA_API_TOKEN, etc.

# Start the service (http://localhost:8002)
atlassian-bridge
```

#### 3. Copilot Agent API + Worker

```bash
cd sdlc-app/services/copilot-agent

# One-time setup
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt

# Authenticate GitHub Copilot CLI (one-time)
gh extension install github/gh-copilot
gh auth login

# Terminal A — Arq worker pool (required for /sessions/* endpoints)
source .venv/bin/activate
agent-worker

# Terminal B — FastAPI server (http://localhost:8001)
source .venv/bin/activate
agent-api --port 8001
```

#### 4. Frontend (Next.js)

```bash
cd sdlc-app

# One-time setup
pnpm install

# Start dev server (http://localhost:3000)
NEXT_PUBLIC_API_URL=http://localhost:8001 pnpm dev
```

> **Service URLs (local)**
> - Frontend: http://localhost:3000
> - Copilot Agent API + docs: http://localhost:8001 / http://localhost:8001/docs
> - Atlassian Bridge: http://localhost:8002

For full per-service documentation see:
- [Frontend (sdlc-app)](./sdlc-app/README.md)
- [Copilot Agent](./sdlc-app/services/copilot-agent/README.md)
- [Atlassian Bridge](./atlassian-bridge/README.md)
- [Jira CLI Tool](./sdlc-app/services/jira-cli/README.md)

---

## 🤖 Specialized Agents

The platform includes 12+ specialized agents for different SDLC personas:

### Business & Requirements
- **`ba.agent.md`** — Business Analyst: Jira analysis, requirement extraction
- **`jira-ba.agent.md`** — Jira-focused BA with enhanced context gathering
- **`jira-reader.md`** — Read-only Jira analysis

### Testing & Quality
- **`test-analyst.agent.md`** — Test strategy and planning
- **`test-designer.agent.md`** — Test case design from requirements
- **`jira-test-automator.agent.md`** — Generates automated tests from Jira tickets
- **`e2e-tester.md`** — End-to-end test automation
- **`gem-browser-tester.agent.md`** — Browser-based testing with Playwright
- **`qa-subagent.agent.md`** — QA workflow orchestration

### Development & Documentation
- **`coder.md`** — Code generation and review
- **`doc-architect.agent.md`** — Architecture documentation
- **`assistant.md`** — General-purpose assistant

### Team Workflows

Teams can be configured with manifests in `sdlc-app/services/copilot-agent/teams/`:
- **`core-platform.team.md`** — Platform engineering team defaults
- **`digital-wealth.team.md`** — Digital wealth management team
- **`innovation-lab.team.md`** — Innovation projects

Each team defines:
- Allowed agents
- Default execution mode (autonomous vs. human-touch with approval gates)
- Jira project + Confluence space scoping
- Approval policies for sensitive operations

---

## 🔧 Key Features

### 1. Multi-Turn Agent Workflows
Agents can execute complex multi-turn workflows with configurable turn budgets (default 20, max 50):
```bash
python agent_copilot.py -a agents/ba.agent.md -m gpt-4o \
  -i "Analyze SCRUM-123" --max-turns 30
```

### 2. Human-in-the-Loop Approval Gates
Sessions can require human approval for sensitive operations:
- GitHub issue creation
- Jira ticket updates
- Confluence page modifications
- Destructive operations

```bash
# Session enters awaiting_approval state
POST /sessions/{id}/approve
{"action": "approve"}  # or "reject"
```

### 3. Tool Execution with Context
Built-in tools available to agents:
- **`bash_exec`** — Execute shell commands (sandboxed, 120s timeout)
- **`invoke_agent`** — Delegate sub-tasks to specialized agents
- **`read_jira`** — Fetch Jira issues with attachments
- **`create_github_issue`** — Create GitHub issues with labels
- **`read_confluence`** — Fetch Confluence pages

### 4. Real-Time Streaming
- **`/stream` endpoint** — Server-Sent Events (SSE) for streaming responses
- **`/sessions/{id}/events`** — Live event stream for async workflows
- WebSocket support for UI real-time updates

### 5. Session Persistence
All sessions are stored in Redis with:
- 24-hour TTL (configurable via `SESSION_TTL_SECONDS`)
- FSM state management (pending → running → awaiting_approval → completed)
- Full event replay from Redis Streams

---

## 📖 API Reference

### Core Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Health check (includes Redis ping) |
| `GET` | `/agents` | List all registered agents |
| `GET` | `/agents/content?file=ba.agent.md` | Get agent definition |
| `GET` | `/skills` | List all registered skills |
| `POST` | `/run` | Blocking agent execution (in-process) |
| `POST` | `/stream` | SSE streaming agent execution |

### Session Management (Worker Pool)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/sessions` | Create a new session |
| `GET` | `/sessions/{id}` | Get session state |
| `POST` | `/sessions/{id}/run` | Enqueue session for worker |
| `GET` | `/sessions/{id}/events` | SSE event stream |
| `POST` | `/sessions/{id}/approve` | Approve/reject checkpoint |
| `GET` | `/sessions/{id}/result` | Get final result |
| `DELETE` | `/sessions/{id}` | Delete session |

### GitHub Integration

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/github/issues` | Create GitHub issue |
| `GET` | `/github/agents` | List GitHub cloud agents |
| `GET` | `/github/agents/content` | Get cloud agent content |

### Atlassian Bridge

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/jira/issue/{key}` | Get Jira issue details |
| `POST` | `/jira/issue/{key}/comment` | Add comment to Jira issue |
| `GET` | `/confluence/page/{id}` | Get Confluence page content |

---

## 🔐 Security & Authentication

### GitHub Authentication
- **Copilot CLI OAuth** (recommended): Managed by `gh auth login`
- **GitHub Token**: Set `GITHUB_TOKEN` or `GH_TOKEN` environment variable

### Atlassian Authentication
- **API Token**: Generate at [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens)
- Credentials stored server-side in `atlassian-bridge` service
- Frontend never sees Atlassian credentials

### Redis Access
- No authentication in dev mode
- Production: Configure `REDIS_URL` with auth: `redis://user:pass@host:port/0`

---

## 📊 Monitoring & Observability

### Health Checks
All services expose `/health` endpoints:
- Frontend: http://localhost:3000/api/health
- Copilot Agent: http://localhost:8001/health
- Atlassian Bridge: http://localhost:8002/health

### Logs
View service logs:
```bash
docker compose logs -f copilot-agent
docker compose logs -f atlassian-bridge
docker compose logs -f frontend
docker compose logs -f arq-worker
```

### Redis Inspection
```bash
# Connect to Redis
docker exec -it redis redis-cli

# List all sessions
KEYS session:*

# Get session details
GET session:abc-123

# Monitor Redis Streams
XREAD STREAMS session:abc-123:events 0
```

---

## 🗂️ Repository Structure

```
sdlc/
├── README.md                    # This file
├── ARCHITECTURE.md              # Detailed system architecture
├── docker-compose.yml           # Full-stack orchestration
├── .env.example                 # Environment template
│
├── atlassian-bridge/            # Jira + Confluence proxy service
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── jira.py             # Jira REST API routes
│   │   └── confluence.py       # Confluence REST API routes
│   └── pyproject.toml
│
└── sdlc-app/                    # Frontend + backend monorepo
    ├── README.md                # Frontend-specific docs
    ├── app/                     # Next.js pages and API routes
    ├── components/              # React components
    ├── lib/                     # TypeScript utilities
    ├── docs/                    # Architecture diagrams
    │   └── ATAF-Design.md       # AutoTest Agent Framework design
    │
    └── services/                # Python backend services
        ├── copilot-agent/       # LLM agent orchestration
        │   ├── README.md        # Detailed agent docs
        │   ├── agent_copilot.py # GitHub Copilot SDK agent
        │   ├── api_server.py    # FastAPI server
        │   ├── worker.py        # Arq worker
        │   ├── agents/          # Agent definitions (*.agent.md)
        │   ├── skills/          # Skill definitions (*.skill.md)
        │   └── teams/           # Team manifests (*.team.md)
        │
        └── jira-cli/            # CLI tool for Jira data extraction
            ├── README.md
            └── jira_cli.py
```

---

## 🧪 Testing

### Run Frontend Tests
```bash
cd sdlc-app
pnpm test
```

### Run Python Tests
```bash
cd sdlc-app/services/copilot-agent
pytest
```

### Manual API Testing
Use the interactive docs at http://localhost:8001/docs or Postman/curl:
```bash
# Create a session
curl -X POST http://localhost:8001/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "agent_file": "ba.agent.md",
    "instruction": "Analyze SCRUM-123",
    "model": "gpt-4o"
  }'

# Stream a response
curl -N http://localhost:8001/stream \
  -H "Content-Type: application/json" \
  -d '{
    "agent_file": "assistant.md",
    "instruction": "What is recursion?",
    "model": "gpt-4o"
  }'
```

---

## 🚢 Deployment

### Production Checklist
- [ ] Set strong `REDIS_PASSWORD` in production
- [ ] Use managed Redis (AWS ElastiCache, Azure Cache for Redis)
- [ ] Configure `SESSION_TTL_SECONDS` based on compliance requirements
- [ ] Enable HTTPS with valid certificates
- [ ] Set `ALLOWED_ORIGINS` in atlassian-bridge to production domains
- [ ] Use secrets management (AWS Secrets Manager, Azure Key Vault)
- [ ] Configure horizontal scaling for `arq-worker` (multiple replicas)
- [ ] Set up monitoring (Prometheus, Grafana, CloudWatch)
- [ ] Enable audit logging for approval gate decisions
- [ ] Review and restrict `allowed_agents` in team manifests

### Docker Compose Production
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Kubernetes Deployment
See [DEPLOYMENT.md](./DEPLOYMENT.md) for Kubernetes manifests and Helm charts.

---

## 🤝 Contributing

1. **Agent Development**: Add new agents in `sdlc-app/services/copilot-agent/agents/`
   - Use YAML frontmatter: `id`, `name`, `description`, `triggers`, `skills`, `tools`
   - Markdown body becomes the system prompt

2. **Skill Development**: Add skills in `sdlc-app/services/copilot-agent/skills/`
   - Use YAML frontmatter: `id`, `name`, `description`, `argument-hint`
   - Markdown body contains skill instructions

3. **Team Configuration**: Add team manifests in `sdlc-app/services/copilot-agent/teams/`
   - Define team-specific defaults and constraints
   - Document team standards in the Markdown body

---

## 📚 Additional Documentation

- [Frontend Development Guide](./sdlc-app/README.md)
- [Copilot Agent Deep Dive](./sdlc-app/services/copilot-agent/README.md)
- [System Architecture](./ARCHITECTURE.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [AutoTest Agent Framework](./sdlc-app/docs/ATAF-Design.md)

---

## 📄 License

[Add your license here]

---

## 🐛 Troubleshooting

### Redis Connection Errors
```bash
# Check Redis is running
docker ps | grep redis

# Restart Redis
docker compose restart redis
```

### Agent Authentication Issues
```bash
# Re-authenticate GitHub CLI
gh auth login
gh auth refresh

# Verify Copilot extension
gh extension list
```

### Worker Not Processing Jobs
```bash
# Check worker logs
docker compose logs -f arq-worker

# Verify Redis connectivity
docker exec copilot-agent redis-cli -h redis ping

# Manually restart worker
docker compose restart arq-worker
```

### Port Conflicts
```bash
# Find process using port
lsof -i :3000  # or :8001, :8002, :6379

# Kill process
kill -9 <PID>
```

---

**Built with ❤️ using GitHub Copilot SDK**
