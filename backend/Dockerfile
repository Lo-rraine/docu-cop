FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files from the repository root
COPY backend/pyproject.toml ./
COPY backend/uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application source
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start application
CMD ["sh", "-c", "uv run alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]