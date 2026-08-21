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
7. Open the frontend at <http://localhost:5173> or the API documentation at
   <http://localhost:8000/docs>.

### Frontend

The React frontend lives in `frontend/` and is included in `docker compose up --build`. Its Nginx
container serves the built application at <http://localhost:5173> and proxies `/api` requests to the
API container.

For frontend development with hot reload, leave the API running and start Vite separately:

```shell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> and enter the same `AUTH_HEADER` value used by the API. Vite proxies
requests under `/api` to the local backend. Run `npm test`, `npm run lint`, and `npm run build` to
validate frontend changes.

For local debugging outside Docker, start the reload-enabled server with:

```shell
uv run python app/main.py
```

For a production-style invocation, use:

```shell
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Database models live in `models.py` modules and schema changes are managed by Alembic. After changing
a model, create and review a migration with `uv run alembic revision --autogenerate -m "description"`,
then apply it with `uv run alembic upgrade head`.

Tests use `TEST_DB_URL` to create a fresh PostgreSQL database, apply all Alembic migrations, and
delete the database after the test session. As a safeguard, its database name must end in `_test`.
The Docker PostgreSQL service must be running before executing `uv run pytest`.

## Knowledge ingestion

Knowledge is collected as complete articles and indexed in PostgreSQL. A run triggered during
August, for example, collects articles published in July, upserts them by source and URL, and saves
a transitional snapshot as `knowledge/hackaday/2026-07.txt`. A specific month can also be requested
to rerun a failed or incomplete import. Each invocation creates a task record so its status and
result can be inspected later.

Hackaday categories and tags are collected with each article and included in both the monthly
artifact and PostgreSQL search index. After applying a taxonomy-related migration, rerun ingestion
for previously imported months to backfill those fields; the source-and-URL upsert updates existing
rows without creating duplicates.

Trigger a run with `POST /knowledge-ingestion/tasks` and inspect it with `GET /tasks/{task_id}`.
Both endpoints require the value of `AUTH_HEADER` in the `X-Auth-Token` request header. The request
body accepts `source` (currently only `hackaday`) and an optional `target_month` in `YYYY-MM` format;
the previous complete month is used by default.

The ingestion endpoint delegates work to a FastAPI background task. This is intentionally a simple,
queue-free solution for now. The task can be interrupted if the application restarts, and Cloud Run
may limit CPU after returning the HTTP response. Rerun the affected month when that happens. See
[ADR 0001](docs/architecture/decisions/0001-in-process-background-tasks.md) for the accepted risks.

## Questions and conversations

Ask a question with the authenticated `POST /questions` endpoint. The response uses Server-Sent
Events so Gemini text is delivered as it is generated. Omit `sources` (or send `null`) to include
all stored knowledge, provide source names such as `hackaday` to restrict the scope, or send an empty
list to use Gemini's broad knowledge. Pass the `conversation_id` returned by the first metadata event
to ask follow-up questions.

```shell
curl --no-buffer http://localhost:8000/questions \
  -H "X-Auth-Token: $AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is an ESP32?","sources":["hackaday"]}'
```

Conversation messages are stored as one JSON value. At 20 messages, Gemini summarizes older
context while the latest 6 messages remain verbatim. Set `GEMINI_API_KEY` to use this endpoint. See
[ADR 0002](docs/architecture/decisions/0002-streamed-questions-and-conversations.md) for limitations.

### Indexed knowledge selection

Ingested articles are stored as complete documents in PostgreSQL and selected with weighted
full-text search before a question is sent to Gemini. Search is restricted by the requested source
scope. Query lexemes use OR matching, with articles matching more terms ranked first; exact title,
category, and tag matches are weighted above content, while discounted prefix matches allow a term
such as `ATmega` to retrieve `ATmega328P`. Complete articles are considered in rank order and
included up to configurable article-count and knowledge-token limits; articles are not split or
truncated. Token counts are calculated through Gemini when first needed and then cached.

Every retrieval produces a structured log showing the source scope, candidate article URLs and
titles, PostgreSQL ranks, token counts, and why each evaluated candidate was selected or excluded.
Article and conversation contents are not logged. Lexical search can still miss related terminology
or return weak results for broad questions; semantic search, query rewriting, and chunking are
deferred until real usage demonstrates a need. Use an empty `sources` list to explicitly retry with
Gemini's general knowledge when indexed knowledge is insufficient.

See [ADR 0003](docs/architecture/decisions/0003-postgresql-article-retrieval.md) for the full design.

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

- `local` writes files below `LOCAL_STORAGE_ROOT` (default: `<project-root>/data`). Relative paths
  are resolved from the project root regardless of the process working directory. This directory
  is ignored by Git.
- `gcs` writes files to `GCS_STORAGE_BUCKET`, optionally below `GCS_STORAGE_PREFIX`. GCP
  Application Default Credentials are used for authentication.

See `.env.example` for local and production configuration values.

Knowledge artifacts are currently transitional ingestion snapshots. Indexed PostgreSQL articles
serve question requests, and the storage dependency may be removed after database-backed recovery
has proved sufficient.

`KNOWLEDGE_REQUEST_DELAY_SECONDS` controls the polite delay between Hackaday requests, while
`KNOWLEDGE_REQUEST_TIMEOUT_SECONDS` sets the timeout for each request.
