# DIY Helper

This is a pet project for experimenting with infrastructure design and AI agents integrations.
It works by downloading data from [Hackaday](https://hackaday.com), reading their articles and
giving the user knowledge based on those articles.

## Code

The project runs on Python + FastAPI and utilizes Gemini models. Hosting is done on GCP. Project
code is in `app/` directory, infrastructure is managed in `infra/`.

## Running

1. Obtain your Gemini API key ([here](https://aistudio.google.com/app/api-keys)).
2. Copy `.env.example` to `.env` and add your Gemini API key.
3. Docker Compose uses its PostgreSQL service automatically. When running against Supabase, replace
   `DB_URL` with its PostgreSQL connection string using the `postgresql+asyncpg` scheme.
4. Create a random string for the auth header and paste it into `.env`.
5. Apply database migrations with `docker compose run --rm api alembic upgrade head`.
6. Run the project with `docker compose up --build`.
7. Open the API documentation at <http://localhost:8000/docs>.

For local debugging outside Docker, start the reload-enabled server with:

```shell
uv run python app/main.py
```

For a production-style invocation, use:

```shell
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Database models live in `models.py` modules and schema changes are managed by Alembic. After changing
a model, create and review a migration with `uv run alembic revision --autogenerate -m "description"`,
then apply it with `uv run alembic upgrade head`.

Tests use `TEST_DB_URL` to create a fresh PostgreSQL database, apply all Alembic migrations, and
delete the database after the test session. As a safeguard, its database name must end in `_test`.
The Docker PostgreSQL service must be running before executing `uv run pytest`.

## Knowledge ingestion

Knowledge is collected in monthly artifacts. A run triggered during August, for example, collects
articles published in July and saves them as `knowledge/hackaday/2026-07.txt`. A specific month can
also be requested to rerun a failed or incomplete import. Each invocation creates a task record so
its status and result can be inspected later.

Trigger a run with `POST /knowledge-ingestion/tasks` and inspect it with `GET /tasks/{task_id}`.
Both endpoints require the value of `AUTH_HEADER` in the `X-Auth-Token` request header. The request
body accepts `source` (currently only `hackaday`) and an optional `target_month` in `YYYY-MM` format;
the previous complete month is used by default.

The ingestion endpoint delegates work to a FastAPI background task. This is intentionally a simple,
queue-free solution for now. The task can be interrupted if the application restarts, and Cloud Run
may limit CPU after returning the HTTP response. Rerun the affected month when that happens. See
[ADR 0001](docs/architecture/decisions/0001-in-process-background-tasks.md) for the accepted risks.

## Task execution

Task scheduling and task processing are separate. A scheduler only transports a persisted task ID;
it does not receive a Python callable or business dependencies.

```text
Endpoint
  ├── writes task type + parameters to PostgreSQL
  └── gives task ID to TaskScheduler
                         │
        FastAPI scheduler today
        Celery/GCP scheduler later
                         │
                         ▼
                  TaskExecutor.execute(task_id)
                    ├── loads the task
                    ├── records RUNNING/SUCCEEDED/FAILED
                    └── selects TaskHandler by task type
                                      │
                                      ▼
                         KnowledgeIngestionTaskHandler
                         Future email/backup/check handlers
```

`TaskScheduler` implementations live in `app/tasks/schedulers/`. `TaskExecutor` owns only execution
lifecycle and result logging. Business handlers are registered by task type in the DI container.
Consequently, replacing the current FastAPI scheduler with Celery or a GCP adapter does not require
changes to the executor or handlers.

## Storage configuration

Set `STORAGE_BACKEND` to select the application-wide storage implementation:

- `local` writes files below `LOCAL_STORAGE_ROOT` (default: `data`). This directory is ignored by
  Git.
- `gcs` writes files to `GCS_STORAGE_BUCKET`, optionally below `GCS_STORAGE_PREFIX`. GCP
  Application Default Credentials are used for authentication.

See `.env.example` for local and production configuration values.

`KNOWLEDGE_REQUEST_DELAY_SECONDS` controls the polite delay between Hackaday requests, while
`KNOWLEDGE_REQUEST_TIMEOUT_SECONDS` sets the timeout for each request.
