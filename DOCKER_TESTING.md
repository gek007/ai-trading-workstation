# Docker Testing Guide for FinAlly

This document provides step-by-step instructions for testing the Docker container and deployment scripts.

## Prerequisites

- Docker Desktop installed and running
- OpenRouter API key (get from https://openrouter.ai/)
- Git clone of the repository

## Initial Setup

1. **Navigate to project root:**
   ```bash
   cd /path/to/finally
   ```

2. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

3. **Edit .env and add your OpenRouter API key:**
   ```bash
   # Edit with your favorite editor
   nano .env  # or vim, code, etc.
   ```

   Ensure this line has your actual key:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
   ```

## Test 1: Docker Image Build

**Expected Result:** Docker image builds successfully in 2-3 minutes

**Steps:**
```bash
docker build -t finally:latest .
```

**What to look for:**
- ✓ Stage 1 (Node) completes: "npm run build" succeeds
- ✓ Stage 2 (Python) completes: "uv sync" succeeds
- ✓ Image created: `docker images` shows `finally:latest`

**Success indicators:**
```
=> => naming to finally:latest
```

**Troubleshooting:**
- If npm build fails: Check Node version (must be 20+)
- If uv sync fails: Check internet connection, Python version
- If out of memory: Close other applications, Docker needs ~2GB RAM

## Test 2: Manual Container Run (Direct Docker Command)

**Expected Result:** Container starts, app accessible at localhost:8000

**Steps:**
```bash
# Remove any existing container first
docker rm -f finally-app 2>/dev/null || true

# Run container manually
docker run -d \
  --name finally-app \
  -p 8000:8000 \
  -v finally-data:/app/db \
  --env-file .env \
  -e PYTHONUNBUFFERED=1 \
  finally:latest
```

**What to look for:**
- ✓ Container starts: `docker ps` shows `finally-app` in "Up" status
- ✓ Port exposed: `0.0.0.0:8000->8000/tcp`
- ✓ No immediate crashes: `docker logs finally-app` shows no errors

**Test the application:**
```bash
# Health check
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","version":"1.0.0","timestamp":"2025-03-08T..."}
```

**Browser Test:**
1. Open http://localhost:8000
2. Verify page loads (watchlist, portfolio, chat visible)
3. Check browser console for errors (F12 → Console)

**Stop container:**
```bash
docker stop finally-app
docker rm finally-app
```

## Test 3: Start Script (macOS/Linux)

**Expected Result:** Script builds (if needed) and starts container automatically

**Steps:**
```bash
# Make script executable (first time only)
chmod +x scripts/start_mac.sh

# Run start script
./scripts/start_mac.sh
```

**What to look for:**
- ✓ Banner displays
- ✓ Auto-detects if .env exists (creates if missing)
- ✓ Builds image if not present
- ✓ Creates volume if needed
- ✓ Starts container
- ✓ Displays success message with URL
- ✓ Attempts to open browser (macOS)

**Success indicators:**
```
✓ Container started successfully
Application is running at: http://localhost:8000
```

## Test 4: Stop Script (macOS/Linux)

**Expected Result:** Container stops and is removed

**Steps:**
```bash
./scripts/stop_mac.sh
```

**What to look for:**
- ✓ Banner displays
- ✓ Container stops
- ✓ Container removed
- ✓ Volume preserved message

**Verify:**
```bash
docker ps -a | grep finally-app  # Should return empty
docker volume ls | grep finally-data  # Should show volume still exists
```

## Test 5: Data Persistence

**Expected Result:** Portfolio and trades persist across container restarts

**Steps:**

1. **Start fresh:**
   ```bash
   # Remove volume to start clean
   docker volume rm finally-data 2>/dev/null || true
   ./scripts/start_mac.sh
   ```

2. **Make some trades in the app:**
   - Open http://localhost:8000
   - Buy 10 shares of AAPL
   - Buy 5 shares of GOOGL
   - Verify positions appear

3. **Stop container:**
   ```bash
   ./scripts/stop_mac.sh
   ```

4. **Restart:**
   ```bash
   ./scripts/start_mac.sh
   ```

5. **Verify persistence:**
   - Open http://localhost:8000
   - Check that your positions (10 AAPL, 5 GOOGL) are still there
   - Check that cash balance reflects the trades

**What to check:**
- ✓ Positions restored
- ✓ Cash balance correct
- ✓ Trade history preserved
- ✓ Watchlist unchanged

## Test 6: Docker Compose

**Expected Result:** Container starts via docker-compose

**Steps:**
```bash
# Stop any running containers first
./scripts/stop_mac.sh

# Start with compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

**Stop:**
```bash
docker-compose down
```

## Test 7: Windows PowerShell Scripts

**Expected Result:** Scripts work on Windows (if testing on Windows)

**Steps:**
1. Open PowerShell as Administrator
2. Navigate to project directory
3. Run: `.\scripts\start_windows.ps1`
4. If execution policy error, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

## Test 8: Health Check

**Expected Result:** Docker health check passes

**Steps:**
```bash
# Wait 30 seconds after container start
docker inspect finally-app --format='{{.State.Health.Status}}'
```

**Expected output:**
```
healthy
```

**View health check logs:**
```bash
docker inspect finally-app --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

## Test 9: Resource Limits

**Expected Result:** Container runs within acceptable resource limits

**Monitor:**
```bash
# Check resource usage
docker stats finally-app

# Expected typical usage:
# CPU: 5-15%
# Memory: 150-300MB
```

## Test 10: Log Output

**Expected Result:** Logs show proper startup and no errors

**View logs:**
```bash
docker logs finally-app
```

**What to look for:**
- ✓ "Starting FinAlly backend..."
- ✓ "Market data source started"
- ✓ "Application startup complete"
- ✓ No ERROR or CRITICAL messages
- ✓ No stack traces

**Follow logs in real-time:**
```bash
docker logs -f finally-app
```

## Cleanup Commands

**Remove everything (start fresh):**
```bash
# Stop and remove container
docker stop finally-app
docker rm finally-app

# Remove volume (deletes all data!)
docker volume rm finally-data

# Remove image (optional - forces rebuild next time)
docker rmi finally:latest
```

**Clean slate:**
```bash
docker system prune -a  # Removes all containers, images, volumes (use with caution!)
```

## Performance Benchmarks

Typical timings on modern hardware:

| Operation | Expected Time |
|-----------|---------------|
| Docker build (first time) | 2-3 minutes |
| Docker build (cached) | 30-60 seconds |
| Container start | 2-5 seconds |
| First page load | 1-2 seconds |
| Subsequent page loads | <1 second |
| SSE connection | <500ms |

## Common Issues and Solutions

### Issue: Port 8000 already in use
**Error:** `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solution:**
```bash
# Find what's using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or change port in scripts
```

### Issue: .env file not found
**Error:** `Warning: .env not found`

**Solution:**
```bash
cp .env.example .env
# Edit .env and add your API key
```

### Issue: Container exits immediately
**Check:**
```bash
docker logs finally-app
```

**Common causes:**
- Missing OPENROUTER_API_KEY
- Database init error
- Python dependency issue

### Issue: Page doesn't load
**Check:**
1. Container is running: `docker ps`
2. Port is accessible: `curl http://localhost:8000/api/health`
3. Browser console for errors
4. Firewall settings

### Issue: Prices not streaming
**Check:**
1. Backend logs: `docker logs finally-app | grep -i stream`
2. SSE endpoint: `curl -N http://localhost:8000/api/stream/prices`
3. Browser Network tab for SSE connection

## Success Criteria

All tests pass when:

- [ ] Docker image builds without errors
- [ ] Container starts and stays running
- [ ] Health check endpoint returns 200 OK
- [ ] Web page loads in browser
- [ ] Prices are streaming (watchlist updates)
- [ ] Trades execute successfully
- [ ] AI chat responds
- [ ] Data persists across container restarts
-- [ ] Start/stop scripts work idempotently
- [ ] Docker Compose works
- [ ] No resource leaks (memory stable)
- [ ] Logs show no errors

## Production Readiness Checklist

Before deploying to production:

- [ ] Remove or restrict development dependencies
- [ ] Set strong OPENROUTER_API_KEY in production environment
- [ ] Configure proper logging (not to stdout)
- [ ] Set up monitoring (health checks, metrics)
- [ ] Configure backup for database volume
- [ ] Set resource limits (CPU, memory)
- [ ] Configure restart policy
- [ ] Review security settings (run as non-root user)
- [ ] Test on target platform (AWS App Runner, Render, etc.)
