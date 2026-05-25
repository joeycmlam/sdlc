# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir build

# Copy only what is needed to build the wheel
# (build context is ./sdlc-app/services, so paths are relative to that)
COPY copilot-agent/pyproject.toml copilot-agent/README.md copilot-agent/requirements.txt ./
COPY copilot-agent/agent.py ./
COPY copilot-agent/agent_copilot.py ./
COPY copilot-agent/api_server.py ./
COPY copilot-agent/checkpoint_gate.py ./
COPY copilot-agent/session_store.py ./
COPY copilot-agent/event_bus.py ./
COPY copilot-agent/registry.py ./
COPY copilot-agent/worker.py ./
COPY copilot-agent/agents/ ./agents/
COPY copilot-agent/skills/ ./skills/
COPY copilot-agent/teams/ ./teams/

# Build the wheel
RUN python -m build --wheel --outdir /dist

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security.
# --create-home is required: the Copilot CLI (Node.js SEA) extracts its
# bundled package into $HOME on first run and fails with EACCES if the
# directory does not exist.
RUN useradd --create-home --shell /bin/false appuser

WORKDIR /app

# Install the wheel and its runtime dependencies
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Install jira-cli dependencies (jira, rich, pdfminer, python-docx, openpyxl)
COPY jira-cli/requirements.txt /tmp/jira-cli-requirements.txt
RUN pip install --no-cache-dir -r /tmp/jira-cli-requirements.txt && rm /tmp/jira-cli-requirements.txt

# Bundle the built-in agent prompt files
COPY copilot-agent/agents/ ./agents/
COPY copilot-agent/skills/ ./skills/
COPY copilot-agent/teams/ ./teams/

# Bundle the jira-cli script so agents can call it via bash_exec
# The agent invokes: python "../jira-cli/jira_cli.py" from cwd /app/
# ../jira-cli/jira_cli.py resolves to /jira-cli/jira_cli.py
COPY jira-cli/jira_cli.py /jira-cli/jira_cli.py

# Drop privileges
USER appuser

# GITHUB_TOKEN must be supplied at runtime (e.g. -e GITHUB_TOKEN=...)
ENV GITHUB_TOKEN=""

EXPOSE 8001

# Default: run the API server on port 8001.
# Override in docker-compose with: command: ["agent-worker"]
CMD ["agent-api", "--port", "8001"]
