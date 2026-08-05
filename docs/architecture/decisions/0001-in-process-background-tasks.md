# ADR 0001: In-process background tasks

## Status

Accepted for the initial hobby-project implementation.

## Context

Knowledge ingestion is triggered through an authenticated FastAPI endpoint. A scrape may take too
long to perform as ordinary request work, but introducing a durable queue would add infrastructure
and cost that the project does not currently need.

## Decision

The endpoint creates a persistent task record and schedules it using FastAPI's in-process background
tasks. The scheduler transports only the task ID. Its background callback opens a new scope in the
framework-independent dependency-injection container and invokes the generic task executor; it must
not reuse request-scoped database sessions or services.

The executor loads the task and resolves an asynchronous business handler from a registry keyed by
task type. Task persistence and lifecycle management therefore do not know whether they are running
knowledge ingestion, email, backups, or another operation. A future Celery or GCP adapter can deliver
the same task ID to a worker that invokes this executor, without changing task internals or handlers.

Task execution is tracked as `PENDING`, `RUNNING`, `SUCCEEDED`, or `FAILED`. A rerun creates a new
task for the same source and target month. Successful output replaces the stable monthly artifact;
failed runs leave an existing artifact untouched.

## Consequences

This execution is not durable. A process restart or Cloud Run instance termination can interrupt a
task and leave its record in `PENDING` or `RUNNING`. With request-based Cloud Run billing, CPU may
also be unavailable after the endpoint returns. A cooldown may reduce this risk later, but cannot
provide delivery guarantees.

For now, abandoned tasks are detected operationally and the month is rerun manually. If stronger
guarantees become necessary, a Celery, Cloud Tasks, or other durable scheduling adapter will replace
the FastAPI adapter. The executor and business handlers remain independent of FastAPI's dependency
system and HTTP context.

See [Google Cloud's background activity guidance](https://docs.cloud.google.com/run/docs/tips/general#background-activity).
