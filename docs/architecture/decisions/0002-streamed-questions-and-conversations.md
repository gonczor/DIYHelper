# ADR 0002: Streamed questions and JSON conversations

## Status

Accepted for the initial hobby-project implementation.

## Context

Questions use all knowledge sources by default, a requested subset when provided, or Gemini's broad
knowledge when the request explicitly provides an empty source list.
Users need streamed answers and follow-up questions, while the application may restart or run on
different Cloud Run instances.

## Decision

`POST /questions` returns Server-Sent Events containing conversation metadata, text chunks, and a
completion or error event. Conversation history is durable in PostgreSQL rather than an in-memory
Gemini chat object. Each conversation stores its messages as one JSON list and replaces the entire
value on update. The user message is committed before generation; the assistant message is added
only after its stream completes.

At 20 messages, Gemini summarizes older context, merges it with any previous summary, and retains
the latest 6 messages verbatim. A summary failure falls back to the full history. Knowledge
artifacts precede the summary and messages in the model request. Explicit Gemini caching and
retrieval are deferred; stable prefixes may benefit from Gemini's implicit caching.

## Consequences

The design works across process restarts and Cloud Run instances and keeps the HTTP stream separate
from conversation persistence. A client disconnect or model failure leaves the user message but no
partial assistant response.

Replacing a JSON message list is simple but concurrent questions in one conversation can overwrite
each other. Long histories, token-based summarization, ownership, message pagination, resumable
streams, retrieval, and explicit caching require later changes. Possession of the current shared
authorization secret permits access to every conversation; per-user ownership must be added with
real user authentication.
