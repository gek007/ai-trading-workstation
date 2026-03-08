# FinAlly - Stop script for Windows PowerShell
# This script stops and removes the running Docker container

$ErrorActionPreference = "Stop"

# Configuration
$CONTAINER_NAME = "finally-app"
$VOLUME_NAME = "finally-data"

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
Write-ColorOutput "║  Stopping FinAlly                                         ║" Yellow
Write-ColorOutput "║                                                           ║" Cyan
Write-ColorOutput "╚═══════════════════════════════════════════════════════════╝" Cyan
Write-Host ""

# Check if Docker is installed
try {
    $null = docker --version
} catch {
    Write-ColorOutput "Error: Docker is not installed" Red
    exit 1
}

# Check if container is running
$RUNNING_CONTAINER = docker ps -q -f name="$CONTAINER_NAME" 2>$null
if (-not $RUNNING_CONTAINER) {
    # Check if container exists but is stopped
    $EXISTING_CONTAINER = docker ps -aq -f name="$CONTAINER_NAME" 2>$null
    if ($EXISTING_CONTAINER) {
        Write-ColorOutput "Container exists but is not running" Yellow
        Write-ColorOutput "Removing container..." Yellow
        docker rm "$CONTAINER_NAME" 2>$null | Out-Null
        Write-ColorOutput "✓ Container removed" Green
    } else {
        Write-ColorOutput "No FinAlly container found" Yellow
    }
    exit 0
}

# Stop the container
Write-ColorOutput "Stopping container: $CONTAINER_NAME" Cyan
docker stop "$CONTAINER_NAME" 2>$null | Out-Null

# Remove the container
Write-ColorOutput "Removing container: $CONTAINER_NAME" Cyan
docker rm "$CONTAINER_NAME" 2>$null | Out-Null

Write-ColorOutput "✓ Container stopped and removed" Green
Write-Host ""
Write-ColorOutput "Database volume '$VOLUME_NAME' is preserved" Cyan
Write-ColorOutput "To remove all data, run: docker volume rm $VOLUME_NAME" Cyan
Write-Host ""
Write-ColorOutput "To start again: .\scripts\start_windows.ps1" Cyan
