# FinAlly - Start script for Windows PowerShell
# This script builds (if needed) and runs the Docker container

$ErrorActionPreference = "Stop"

# Configuration
$IMAGE_NAME = "finally:latest"
$CONTAINER_NAME = "finally-app"
$VOLUME_NAME = "finally-data"
$PORT = "8000"
$ENV_FILE = ".env"

# Helper function for colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# Print banner
Write-ColorOutput "╔═══════════════════════════════════════════════════════════╗" Cyan
Write-ColorOutput "║                                                           ║" Cyan
Write-ColorOutput "║  FinAlly - AI Trading Workstation                        ║" Green
Write-ColorOutput "║                                                           ║" Cyan
Write-ColorOutput "╚═══════════════════════════════════════════════════════════╝" Cyan
Write-Host ""

# Check if Docker is installed
try {
    $null = docker --version
} catch {
    Write-ColorOutput "Error: Docker is not installed" Red
    Write-Host "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
}

# Check if .env file exists
if (-not (Test-Path $ENV_FILE)) {
    Write-ColorOutput "Warning: $ENV_FILE not found" Yellow
    Write-Host "Creating $ENV_FILE from template..."

    if (Test-Path "$ENV_FILE.example") {
        Copy-Item "$ENV_FILE.example" $ENV_FILE
        Write-ColorOutput "✓ Created $ENV_FILE from example" Green
        Write-ColorOutput "Please edit $ENV_FILE and add your OpenRouter API key" Yellow
        Write-Host ""
    } else {
        Write-ColorOutput "Creating minimal $ENV_FILE..." Yellow
        @"
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false

# Optional: Massive (Polygon) API key; when set, backend uses Massive polling instead of simulator
MASSIVE_API_KEY=

# Optional: Seed for deterministic simulator price sequence (testing)
MARKET_SIM_SEED=
"@ | Out-File -FilePath $ENV_FILE -Encoding utf8
        Write-ColorOutput "✓ Created minimal $ENV_FILE" Green
        Write-ColorOutput "Please edit $ENV_FILE and add your OpenRouter API key" Yellow
        Write-Host ""
    }
}

# Check if image exists, build if not
$IMAGE_EXISTS = docker images -q "$IMAGE_NAME" 2>$null
if (-not $IMAGE_EXISTS) {
    Write-ColorOutput "Docker image not found. Building..." Yellow
    docker build -t "$IMAGE_NAME" .
    Write-ColorOutput "✓ Build complete" Green
    Write-Host ""
}

# Check if container is already running
$RUNNING_CONTAINER = docker ps -q -f name="$CONTAINER_NAME" 2>$null
if ($RUNNING_CONTAINER) {
    Write-ColorOutput "Container is already running" Yellow
    Write-Host ""
    docker ps -f name="$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    Write-Host ""
    Write-ColorOutput "✓ Application is available at: http://localhost:$PORT" Green
    exit 0
}

# Check if container exists but is stopped
$EXISTING_CONTAINER = docker ps -aq -f name="$CONTAINER_NAME" 2>$null
if ($EXISTING_CONTAINER) {
    Write-ColorOutput "Removing existing stopped container..." Yellow
    docker rm "$CONTAINER_NAME" 2>$null | Out-Null
}

# Create volume if it doesn't exist
$VOLUME_EXISTS = docker volume ls -q -f name="$VOLUME_NAME" 2>$null
if (-not $VOLUME_EXISTS) {
    Write-ColorOutput "Creating Docker volume: $VOLUME_NAME" Yellow
    docker volume create "$VOLUME_NAME" | Out-Null
}

# Run the container
Write-ColorOutput "Starting FinAlly container..." Cyan
docker run -d `
    --name "$CONTAINER_NAME" `
    --restart unless-stopped `
    -p "$PORT`:8000" `
    -v "${VOLUME_NAME}:/app/db" `
    --env-file "$ENV_FILE" `
    -e PYTHONUNBUFFERED=1 `
    "$IMAGE_NAME"

# Wait for container to be healthy
Write-ColorOutput "Waiting for application to start..." Yellow
Start-Sleep -Seconds 3

# Check if container is running
$RUNNING_CONTAINER = docker ps -q -f name="$CONTAINER_NAME" 2>$null
if ($RUNNING_CONTAINER) {
    Write-ColorOutput "✓ Container started successfully" Green
    Write-Host ""
    docker ps -f name="$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    Write-Host ""
    Write-ColorOutput "╔═══════════════════════════════════════════════════════════╗" Green
    Write-ColorOutput "║  Application is running at:                             ║" Green
    Write-ColorOutput "║  http://localhost:$PORT                                  ║" Cyan
    Write-ColorOutput "║                                                           ║" Green
    Write-ColorOutput "║  API Documentation:                                      ║" Green
    Write-ColorOutput "║  http://localhost:$PORT/docs                             ║" Cyan
    Write-ColorOutput "╚═══════════════════════════════════════════════════════════╝" Green
    Write-Host ""
    Write-ColorOutput "To view logs: docker logs -f $CONTAINER_NAME" Cyan
    Write-ColorOutput "To stop:      .\scripts\stop_windows.ps1" Cyan
    Write-Host ""

    # Try to open browser
    Write-ColorOutput "Attempting to open browser..." Yellow
    Start-Sleep -Seconds 1
    try {
        Start-Process "http://localhost:$PORT"
    } catch {
        # Ignore errors opening browser
    }
} else {
    Write-ColorOutput "✗ Failed to start container" Red
    Write-ColorOutput "Check logs with: docker logs $CONTAINER_NAME" Yellow
    exit 1
}
