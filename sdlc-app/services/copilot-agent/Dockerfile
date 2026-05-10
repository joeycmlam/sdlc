# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir build

# Copy only what is needed to build the wheel
COPY pyproject.toml README.md requirements.txt ./
COPY agent.py ./
COPY agent_copilot.py ./
COPY api_server.py ./
COPY agents/ ./agents/

# Build the wheel
RUN python -m build --wheel --outdir /dist

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Create a non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

# Install the wheel and its runtime dependencies
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Bundle the built-in agent prompt files
COPY agents/ ./agents/

# Drop privileges
USER appuser

# GITHUB_TOKEN must be supplied at runtime (e.g. -e GITHUB_TOKEN=...)
ENV GITHUB_TOKEN=""

EXPOSE 8000

# Default: run the CLI with no arguments (prints help)
ENTRYPOINT ["copilot-agent"]
CMD ["--help"]
# To run as API: docker run -p 8000:8000 <image> uvicorn api_server:app --host 0.0.0.0 --port 8000
