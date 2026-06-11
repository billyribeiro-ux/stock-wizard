# Stock Wizard — task runner
set dotenv-load := true

default:
    @just --list

# --- setup ---
install:
    uv sync --all-extras
    cd apps/web && pnpm install

# --- infra ---
up:
    docker compose up -d

down:
    docker compose down

logs:
    docker compose logs -f

# --- database ---
migrate:
    cd storage && uv run alembic upgrade head

makemigration message:
    cd storage && uv run alembic revision --autogenerate -m "{{message}}"

# --- run ---
api:
    uv run uvicorn app.main:app --reload --app-dir services/api --host 0.0.0.0 --port 8000

worker:
    cd services/worker && uv run arq worker.main.WorkerSettings

web:
    cd apps/web && pnpm dev

# --- quality ---
test:
    uv run pytest -q

test-unit:
    uv run pytest tests/unit -q

lint:
    uv run ruff check .
    uv run mypy engine packages services

fmt:
    uv run ruff format .
    uv run ruff check --fix .

check-web:
    cd apps/web && pnpm run check

# --- contracts ---
gen-types:
    uv run python -m engine.schemas.export_jsonschema > apps/web/src/lib/contracts.schema.json
    cd apps/web && pnpm run gen-types
