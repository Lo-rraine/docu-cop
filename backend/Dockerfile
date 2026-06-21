FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for psycopg2 and pgvector
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY backend/pyproject.toml backend/uv.lock* ./

# Install dependencies with uv
RUN uv sync --frozen --no-dev

# Copy app code
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run migrations and start server
CMD ["sh", "-c", "uv run alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
