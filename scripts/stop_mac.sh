#!/usr/bin/env bash
# FinAlly - Stop script for macOS / Linux
# Stops and removes the container; the data volume is preserved.
# Idempotent: safe to run multiple times.

set -euo pipefail

CONTAINER_NAME="finally-app"
VOLUME_NAME="finally-data"

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
cyan()   { printf '\033[0;36m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }

cyan "╔═══════════════════════════════════════════════════════════╗"
cyan "║  Stopping FinAlly                                         ║"
cyan "╚═══════════════════════════════════════════════════════════╝"
echo ""

if ! command -v docker &>/dev/null; then
  red "Error: Docker is not installed."
  exit 1
fi

# Stop if running
if docker ps -q -f "name=^${CONTAINER_NAME}$" | grep -q .; then
  cyan "Stopping container: $CONTAINER_NAME"
  docker stop "$CONTAINER_NAME" >/dev/null
fi

# Remove if it exists (stopped or just stopped above)
if docker ps -aq -f "name=^${CONTAINER_NAME}$" | grep -q .; then
  cyan "Removing container: $CONTAINER_NAME"
  docker rm "$CONTAINER_NAME" >/dev/null
  green "✓ Container stopped and removed."
else
  yellow "No FinAlly container found — nothing to do."
fi

echo ""
cyan "Database volume '$VOLUME_NAME' is preserved."
cyan "To remove all data, run: docker volume rm $VOLUME_NAME"
echo ""
cyan "To start again: ./scripts/start_mac.sh"
