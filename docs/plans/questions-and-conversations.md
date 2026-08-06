# Questions and conversations implementation plan

## Status

In progress. This document records the agreed scope for this implementation increment.

## Scope

Add an authenticated `POST /questions` endpoint that streams Gemini responses using Server-Sent
Events (SSE). Omitted or null sources select all available knowledge sources, a non-empty list limits
the scope to that subset, and an empty list selects Gemini's broad knowledge. Selected artifacts are
supplied before the conversation context.

Requests may contain an optional `conversation_id`. Without one, the service creates a conversation
and returns its ID in the first SSE metadata event. With one, the service loads and reuses the full
saved conversation context.

Only `GEMINI_API_KEY` is configurable initially. Use the async Google GenAI client and implicit
caching; do not implement explicit Gemini cache resources.

## Persistence

Add a `Conversation` database model containing:

- UUID primary key
- messages stored as JSON
- nullable conversation summary
- creation and update timestamps

There is one user for now, so conversations have no owner column. Access remains protected by the
existing shared endpoint authorization. Add the table through a new Alembic migration; existing
migrations remain immutable.

Update messages by replacing the complete JSON value so SQLAlchemy reliably detects changes. Save
the user message before calling Gemini. Accumulate streamed assistant text in memory and save the
assistant message only after successful completion. A failed or interrupted stream must not be
stored as a complete assistant response.

Two simultaneous questions for one conversation can overwrite JSON history. Accept and document
this limitation for the proof of concept.

## Summarization

When a conversation reaches 20 stored messages:

1. Retain the latest 6 messages verbatim.
2. Ask Gemini to summarize the older messages together with any existing summary.
3. Preserve decisions, constraints, unresolved questions, referenced projects, and important facts.
4. Store the new summary and replace the message list with the retained messages.
5. Send future requests as optional knowledge, summary, recent messages, then the new question.

If summarization fails, log the error and answer using the complete history. Summarization uses a
separate non-streaming Gemini request and is tested with the mocked client.

## Implementation sequence

1. Define question, conversation, message, summary, and SSE schemas. `sources` and
   `conversation_id` are optional; there is no month selector.
2. Add the conversation database model and repository through a new migration.
3. Extend memory, local, and GCS storage backends with artifact loading and source-prefix listing.
4. Add `google-genai`, the API-key setting, and an application-scoped async Gemini client that is
   closed during application shutdown.
5. Implement conversation persistence and artifact selection.
6. Implement Gemini summarization using the threshold and retention policy above.
7. Implement the question service: persist the question, summarize when needed, construct Gemini
   contents, stream text, and persist the completed answer.
8. Expose the authorized SSE endpoint. Keep the Dishka scope open until streaming completes.
9. Update `.env.example`, the README, and architecture decisions with configuration and known
   limitations.
10. Run all tests and quality checks, then verify no API key or other secret is tracked.

## Testing

Mock the Gemini client; do not make real Gemini requests and do not record Gemini VCR cassettes.
Assert the exact model call contents and configuration.

Cover:

- broad questions without artifacts
- questions using all artifacts for selected sources
- new conversations and follow-up questions
- ordering of knowledge, summary, history, and the new question
- SSE metadata, text, completion, and error behavior
- user-message persistence before generation
- assistant-message persistence only after successful completion
- summarization calls, retained messages, and fallback after summary failure
- endpoint authentication and request-to-PostgreSQL persistence
- cleanup after streaming and client disconnection

## Deferred decisions

- explicit Gemini context caching and cache lifecycle
- vector search or other retrieval over knowledge artifacts
- token-based summarization thresholds and context budgeting
- separate message rows, concurrency control, and message pagination
- users, conversation ownership, and per-user authorization
- resumable streams and persisted partial assistant responses
- frontend implementation
