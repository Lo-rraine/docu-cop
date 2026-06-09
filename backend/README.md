# Backend — FastAPI app

## Quick start

### 1. Install dependencies
```bash
uv sync
```

### 2. Set up environment
Copy `.env.example` to `.env` and fill in required values:
```bash
cp .env.example .env
```

Required env vars:
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — from Supabase project
- `DATABASE_URL` — Postgres connection string
- `OPENAI_API_KEY` — OpenAI API key

### 3. Run the app
```bash
uv run uvicorn app.main:app --reload --port 8000
```

The app will start on `http://localhost:8000`. Health check: `GET /health`

## Common commands

| Task | Command |
|------|---------|
| Run app (dev) | `uv run uvicorn app.main:app --reload` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| DB migrations | `uv run alembic upgrade head` |
| New migration | `uv run alembic revision --autogenerate -m "description"` |

## Configuration

All config lives in `app/config.py` (Pydantic `Settings` module). Environment variables are loaded on startup—missing required vars will fail fast with an error message.

## Development

- Reload on file changes: `--reload` flag enables hot reload via Uvicorn
- Logging: structured logs via `structlog`
- Database: connects to Supabase Postgres; `pgvector` extension required for embeddings
