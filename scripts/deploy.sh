#!/usr/bin/env zsh
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — Build-once, deploy-anywhere script for the SDLC platform
#
# Prerequisites (local):
#   - SSH access configured (key forwarding / ~/.zshrc alias)
#   - Local Docker images already built:
#       sdlc-atlassian-bridge  sdlc-copilot-agent  sdlc-arq-worker  sdlc-frontend
#
# Prerequisites (EC2 — one-time setup):
#   - Docker and Docker Compose installed
#   - ~/.env file created from .env.ec2.example with real secrets
#   - EC2 Security Group: inbound TCP 3000 and 8001 open
#
# Usage:
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

EC2_HOST="ec2-35-89-228-36.us-west-2.compute.amazonaws.com"
EC2_USER="ec2-user"
EC2_KEY="$HOME/.ssh/mysys-m5pro-aws.pem"
SSH=(ssh -i "$EC2_KEY")
SCP=(scp -i "$EC2_KEY")
COMPOSE_FILE="$(dirname "$0")/../docker-compose.ec2.yml"

# Local images to transfer (redis is pulled directly on EC2)
LOCAL_IMAGES=(
  sdlc-atlassian-bridge
  sdlc-copilot-agent
  sdlc-arq-worker
  sdlc-frontend
)

# ── Preflight checks ──────────────────────────────────────────────────────────
echo "==> Checking SSH connectivity..."
"${SSH[@]}" -o ConnectTimeout=10 "${EC2_USER}@${EC2_HOST}" "echo '    EC2 reachable'" || {
  echo "ERROR: Cannot connect to $EC2_HOST. Check your SSH config."
  exit 1
}

echo "==> Checking that ~/.env exists on EC2..."
"${SSH[@]}" "${EC2_USER}@${EC2_HOST}" "test -f ~/.env" || {
  echo ""
  echo "ERROR: ~/.env not found on EC2."
  echo "Run the following to set it up first:"
  echo "  scp -i \"$EC2_KEY\" .env.ec2.example ${EC2_USER}@${EC2_HOST}:~/.env"
  echo "  ssh -i \"$EC2_KEY\" ${EC2_USER}@${EC2_HOST} 'nano ~/.env'"
  exit 1
}

echo "==> Checking that local images exist..."
for img in "${LOCAL_IMAGES[@]}"; do
  docker image inspect "$img" > /dev/null 2>&1 || {
    echo "ERROR: Local image '$img' not found. Build it first."
    exit 1
  }
done

# ── Transfer images ───────────────────────────────────────────────────────────
echo ""
echo "==> Transferring images to EC2 (this may take a few minutes)..."
for img in "${LOCAL_IMAGES[@]}"; do
  echo "    • $img"
  docker save "$img" | gzip | "${SSH[@]}" "${EC2_USER}@${EC2_HOST}" "gunzip | docker load"
done

echo "==> Pulling redis:7-alpine on EC2..."
"${SSH[@]}" "${EC2_USER}@${EC2_HOST}" "docker pull redis:7-alpine"

# ── Copy compose file ─────────────────────────────────────────────────────────
echo ""
echo "==> Copying docker-compose.ec2.yml to EC2..."
"${SCP[@]}" "$COMPOSE_FILE" "${EC2_USER}@${EC2_HOST}:~/docker-compose.yml"

# ── Start stack ───────────────────────────────────────────────────────────────
echo ""
echo "==> Starting services..."
"${SSH[@]}" "${EC2_USER}@${EC2_HOST}" "cd ~ && docker compose --env-file .env up -d --remove-orphans --pull never"

# ── Status ────────────────────────────────────────────────────────────────────
echo ""
echo "==> Service status:"
"${SSH[@]}" "${EC2_USER}@${EC2_HOST}" "docker compose ps"

echo ""
echo "==> Deploy complete!"
echo "    Frontend:      http://${EC2_HOST}:3000"
echo "    Copilot agent: http://${EC2_HOST}:8001/health"
