# ADR 0003: PostgreSQL article retrieval

## Status

Accepted.

## Context

Question answering currently loads every monthly knowledge artifact in the selected source scope
into the Gemini request. With more than 200 articles, this consumes tokens regardless of whether an
article is relevant to the question.

Splitting articles into chunks would reduce the amount of retrieved text, but it could also remove
context carried between paragraphs. The immediate problem is the number of articles loaded, not the
size of an individual article, so chunking would add retrieval and merging complexity before it is
known to be necessary.

## Decision

PostgreSQL is the serving source for processed knowledge. Each collected article is stored as one
searchable document containing its human-readable source name, URL, title, content, publication
time, and ingestion metadata. A document is uniquely identified by `(source, url)`; a separate
source-specific identifier is not stored because current sources use the URL as that identifier.

The PostgreSQL models, repository, and full-text retrieval service belong to an `app/knowledge/`
package. Knowledge-source collection and ingestion task orchestration remain in
`app/knowledge_ingestion/` and write collected documents through the knowledge repository. The
`app/knowledge/` package is an application boundary, not a new filesystem storage location.

PostgreSQL full-text search ranks complete articles. The title receives greater search weight than
the content, and the existing question source scope is applied as a database filter. An omitted
source list searches every source, a non-empty list searches only those sources, and an empty list
continues to bypass stored knowledge and use Gemini's broad knowledge.

Question answering selects complete articles in search-rank order. Selection is constrained by a
configurable maximum article count and total input-token budget. Articles are not split, truncated,
or merged. If article-level retrieval later proves too coarse or expensive, chunking can be
introduced as a separate decision based on observed retrieval quality.

The token count for an article is populated lazily. When a selected candidate has no cached count,
the application calls Gemini's token-counting operation and stores the result. Subsequent requests
reuse it. The project has one active model, so the model name is not stored with or compared against
the cached count. Reingesting changed article content invalidates its cached token count.

The complete request includes instructions, conversation context, and article metadata in addition
to article content. The application may count the assembled request before generation as a final
guard and remove the lowest-ranked article until the request fits the configured budget.

Each retrieval emits one structured diagnostic event correlated with the request and conversation.
It records the source filter, configured limits, retrieval duration, and every evaluated
candidate's title, URL, rank, token count, token-cache status, selection result, and exclusion
reason. Evaluation stops as soon as the article-count limit is reached. The event also records the
final selected article count and token total. Article content, conversation text, authentication
values, and other prompt contents are not logged.

Monthly local or GCS artifacts temporarily remain ingestion snapshots for diagnostics and recovery,
but the question path no longer loads them. PostgreSQL and structured retrieval logs provide the
primary serving and diagnostic paths. Artifact storage is a candidate for removal after indexed
ingestion and recovery procedures have proved reliable; that removal is a separate decision. A
successful ingestion upserts each collected article and its search data into PostgreSQL. Reruns do
not delete previously indexed documents merely because a transient collection failure omitted them.

## Consequences

Questions send only a few relevant articles to Gemini instead of every stored artifact, while each
selected article retains its complete paragraph context. Search, source filtering, maximum article
count, token-budget behavior, and diagnostic logging can be tested independently of generation.

The first request that selects an article without a cached token count incurs an additional Gemini
call. Concurrent requests may calculate the same missing count, but their updates are idempotent and
do not require locking. Changing the active model can make cached counts inaccurate; because the
project deliberately has one model, invalidating all cached counts is an operational step when that
model changes.

Repository operations currently commit their own changes, and writing an artifact plus indexing its
articles is not one atomic operation across storage and PostgreSQL. Transaction ownership,
cross-store recovery, and ingestion idempotency need a separate decision before artifact storage is
removed.

PostgreSQL full-text search is lexical and may miss semantically related articles that use different
terminology. Broad prompts such as requests for an easy project may also rank irrelevant articles
because common words occur across much of the corpus. Article-level results can include irrelevant
sections. Query rewriting, synonym expansion, ranking adjustments, semantic retrieval, reranking,
and chunking are deferred until actual question behavior demonstrates a need.

Retrieval failure does not silently mix general knowledge into a stored-knowledge answer. The
existing explicit empty source list remains the way to request Gemini's general knowledge; a user
can retry with that scope when indexed knowledge does not answer the question. This preserves the
distinction between sourced answers and unsourced model knowledge.
