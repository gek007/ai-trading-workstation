# Docker Quick Start Guide

## One-Line Start

### macOS/Linux
```bash
./scripts/start_mac.sh
```

### Windows (PowerShell)
```bash
.\scripts\start_windows.ps1
```

That's it! The script will:
1. Check if `.env` exists (create from `.env.example` if needed)
2. Build the Docker image (first time only, takes 2-3 minutes)
3. Start the container
4. Open your browser to `http://localhost:8000`

## Stopping

### macOS/Linux
```bash
./scripts/stop_mac.sh
```

### Windows (PowerShell)
```bash
.\scripts\stop_windows.ps1
```

## Common Commands

### View logs
```bash
docker logs -f finally-app
```

### Check if running
```bash
docker ps | grep finally-app
```

### Restart
```bash
./scripts/stop_mac.sh && ./scripts/start_mac.sh
```

### Delete everything and start fresh
```bash
docker stop finally-app
docker rm finally-app
docker volume rm finally-data
./scripts/start_mac.sh
```

## Troubleshooting

### Port 8000 already in use?
```bash
# Find what's using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows
```

### Container won't start?
```bash
# Check logs
docker logs finally-app

# Try rebuilding
docker build -t finally:latest --no-cache .
```

### Prices not updating?
```bash
# Check if SSE is working
curl -N http://localhost:8000/api/stream/prices

# Should see events like:
# event: price_update
# data: {"tickers": [...]}
```

### Reset everything (deletes all data!)
```bash
docker stop finally-app
docker rm finally-app
docker volume rm finally-data
docker rmi finally:latest
```

## Using Docker Compose (Alternative)

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Stop and delete data
docker-compose down -v
```

## Manual Docker Run

```bash
docker run -d \
  --name finally-app \
  -p 8000:8000 \
  -v finally-data:/app/db \
  --env-file .env \
  -e PYTHONUNBUFFERED=1 \
  finally:latest
```

## Environment Setup

Before running, make sure `.env` exists:

```bash
# Copy template
cp .env.example .env

# Edit and add your OpenRouter API key
nano .env  # or use your favorite editor
```

Required in `.env`:
```
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
```

## Health Check

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-03-08T..."
}
```

## What Gets Saved

Your data persists in a Docker volume named `finally-data`:
- Portfolio positions
- Trade history
- Cash balance
- Watchlist
- Chat history

This data survives:
- Container restarts
- Server reboots
- Docker daemon restarts

## Browser Access

After starting:
- Main app: http://localhost:8000
- API docs: http://localhost:8000/docs

## First Run

On first run:
1. Script creates `.env` from template (if missing)
2. Script builds Docker image (takes 2-3 minutes)
3. Script creates Docker volume `finally-data`
4. Container starts and initializes database with seed data
5. You get $10,000 virtual cash
6. Default watchlist: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

## System Requirements

- Docker Desktop installed and running
- 2GB RAM available for Docker
- 500MB disk space
- OpenRouter API key (free tier available)

## Getting Help

If something doesn't work:
1. Check `DOCKER_TESTING.md` for detailed troubleshooting
2. Check container logs: `docker logs finally-app`
3. Verify `.env` has valid `OPENROUTER_API_KEY`
4. Ensure port 8000 is not in use
5. Try rebuilding the image

## Next Steps

After successfully starting:
1. Open http://localhost:8000 in your browser
2. Watch prices stream in real-time
3. Make some test trades
4. Try the AI chat assistant
5. Check out the API docs at http://localhost:8000/docs

Enjoy trading!
