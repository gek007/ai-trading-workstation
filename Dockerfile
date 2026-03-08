# Multi-stage Dockerfile for FinAlly - AI Trading Workstation
# Stage 1: Build Next.js frontend
FROM node:20-slim AS frontend-builder

# Set working directory
WORKDIR /build/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build static export
RUN npm run build

# Stage 2: Python runtime with FastAPI
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Copy Python project files
COPY backend/pyproject.toml backend/uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy backend application code
COPY backend/app ./app
COPY backend/start_server.py .

# Copy frontend build output to static directory
# Note: main.py looks for static at Path(__file__).parent.parent.parent / "static"
# which resolves to /static/ in the container (three levels up from app/main.py)
# So we copy to /static/ at the filesystem root, not /app/static/
COPY --from=frontend-builder /build/frontend/out /static

# Create database directory with proper permissions
RUN mkdir -p /app/db && \
    chown -R nobody:nogroup /app/db

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run as non-root user for security
USER nobody

# Set database path to volume mount
ENV DB_PATH=/app/db

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
