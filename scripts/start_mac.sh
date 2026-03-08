#!/usr/bin/env bash
# FinAlly - Start script for macOS / Linux
# Idempotent: safe to run multiple times.

set -euo pipefail

IMAGE_NAME="finally:latest"
CONTAINER_NAME="finally-app"
VOLUME_NAME="finally-data"
PORT="8000"
ENV_FILE=".env"

# Colour helpers
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
cyan()   { printf '\033[0;36m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }

cyan "╔═══════════════════════════════════════════════════════════╗"
cyan "║  FinAlly - AI Trading Workstation                        ║"
cyan "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Verify Docker is available
if ! command -v docker &>/dev/null; then
  red "Error: Docker is not installed."
  echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop"
  exit 1
fi

# Create .env from template if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
  yellow "Warning: $ENV_FILE not found."
  if [ -f "${ENV_FILE}.example" ]; then
    cp "${ENV_FILE}.example" "$ENV_FILE"
    green "✓ Created $ENV_FILE from template."
    yellow "Please edit $ENV_FILE and add your OpenRouter API key, then re-run this script."
    exit 0
  else
    yellow "Creating minimal $ENV_FILE..."
    cat > "$ENV_FILE" <<'EOF'
OPENROUTER_API_KEY=your-openrouter-api-key-here
LLM_MOCK=false
MASSIVE_API_KEY=
MARKET_SIM_SEED=
EOF
    green "✓ Created minimal $ENV_FILE."
    yellow "Please edit $ENV_FILE and add your OpenRouter API key, then re-run this script."
    exit 0
  fi
fi

# Build image if it doesn't exist (or --build flag was passed)
BUILD_FLAG="${1:-}"
if [ "$BUILD_FLAG" = "--build" ] || [ -z "$(docker images -q "$IMAGE_NAME" 2>/dev/null)" ]; then
  yellow "Building Docker image..."
  docker build -t "$IMAGE_NAME" .
  green "✓ Build complete."
  echo ""
fi

# If container is already running, report and exit cleanly
if docker ps -q -f "name=^${CONTAINER_NAME}$" | grep -q .; then
  yellow "Container is already running."
  echo ""
  docker ps -f "name=^${CONTAINER_NAME}$" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  echo ""
  green "✓ Application is available at: http://localhost:${PORT}"
  exit 0
fi

# Remove any stopped container with the same name
if docker ps -aq -f "name=^${CONTAINER_NAME}$" | grep -q .; then
  yellow "Removing existing stopped container..."
  docker rm "$CONTAINER_NAME" >/dev/null
fi

# Ensure named volume exists
docker volume create "$VOLUME_NAME" >/dev/null 2>&1 || true

# Start the container
cyan "Starting FinAlly container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${PORT}:8000" \
  -v "${VOLUME_NAME}:/app/db" \
  --env-file "$ENV_FILE" \
  -e PYTHONUNBUFFERED=1 \
  "$IMAGE_NAME"

# Wait for health check to pass (up to 60 s)
cyan "Waiting for application to start..."
RETRIES=12
for i in $(seq 1 $RETRIES); do
  if curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq "$RETRIES" ]; then
    red "✗ Application did not become healthy in time."
    yellow "Check logs with: docker logs $CONTAINER_NAME"
    exit 1
  fi
  sleep 5
done

echo ""
green "╔═══════════════════════════════════════════════════════════╗"
green "║  Application is running at:                              ║"
cyan  "║  http://localhost:${PORT}                                  ║"
green "║  API Documentation: http://localhost:${PORT}/docs          ║"
green "╚═══════════════════════════════════════════════════════════╝"
echo ""
cyan "To view logs:  docker logs -f $CONTAINER_NAME"
cyan "To stop:       ./scripts/stop_mac.sh"
echo ""

# Open browser if possible
if command -v open &>/dev/null; then
  open "http://localhost:${PORT}"
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:${PORT}"
fi
