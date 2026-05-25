#!/usr/bin/env zsh
# ─────────────────────────────────────────────────────────────────────────────
# build-amd64.sh — Build all SDLC images for linux/amd64 (EC2 target)
#
# Run this on Apple Silicon before deploying to an x86_64 EC2 instance.
# Requires Docker Desktop with buildx support (included by default).
#
# Usage:
#   chmod +x scripts/build-amd64.sh
#   ./scripts/build-amd64.sh
#   ./scripts/deploy.sh          # then deploy
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(dirname "$0")/.."
PLATFORM="linux/amd64"

echo "==> Building for platform: $PLATFORM"
echo ""

# atlassian-bridge
echo "── sdlc-atlassian-bridge ──────────────────────────────────────────────"
docker buildx build \
  --platform "$PLATFORM" \
  --load \
  -t sdlc-atlassian-bridge \
  "$REPO_ROOT/atlassian-bridge"

echo ""

# copilot-agent (also used as arq-worker)
echo "── sdlc-copilot-agent ─────────────────────────────────────────────────"
docker buildx build \
  --platform "$PLATFORM" \
  --load \
  -t sdlc-copilot-agent \
  -f "$REPO_ROOT/sdlc-app/services/copilot-agent/Dockerfile" \
  "$REPO_ROOT/sdlc-app/services"

echo ""

# arq-worker shares the same Dockerfile — just retag
echo "── sdlc-arq-worker (retag from sdlc-copilot-agent) ───────────────────"
docker tag sdlc-copilot-agent sdlc-arq-worker
echo "    Tagged sdlc-copilot-agent → sdlc-arq-worker"

echo ""

# frontend
echo "── sdlc-frontend ──────────────────────────────────────────────────────"
docker buildx build \
  --platform "$PLATFORM" \
  --load \
  --build-arg NEXT_PUBLIC_API_URL=http://copilot-agent:8001 \
  -t sdlc-frontend \
  "$REPO_ROOT/sdlc-app"

echo ""
echo "==> All images built for $PLATFORM"
echo "    Run ./scripts/deploy.sh to push to EC2"
