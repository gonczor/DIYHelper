import time
from typing import Protocol
from uuid import UUID

import structlog

from app.knowledge.domain import (
    KnowledgeArticle,
    KnowledgeReference,
    KnowledgeSourceName,
    StoredKnowledgeReference,
)
from app.knowledge.repository import KnowledgeRepository

logger = structlog.get_logger(__name__)


class TokenCounter(Protocol):
    async def count_tokens(self, content: str) -> int: ...


class KnowledgeSelectionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        token_counter: TokenCounter,
        candidate_limit: int,
        article_limit: int,
        token_budget: int,
    ) -> None:
        self._repository = repository
        self._token_counter = token_counter
        self._candidate_limit = candidate_limit
        self._article_limit = article_limit
        self._token_budget = token_budget

    async def select(
        self,
        query: str,
        sources: list[KnowledgeSourceName] | None,
        conversation_id: UUID,
        carried_references: list[StoredKnowledgeReference] | None = None,
    ) -> list[KnowledgeArticle | KnowledgeReference]:
        started_at = time.perf_counter()
        if sources == []:
            return []
        candidates = await self._combined_candidates(query, sources, carried_references or [])
        selected: list[KnowledgeArticle | KnowledgeReference] = []
        selected_tokens = 0
        diagnostics: list[dict[str, object]] = []
        for candidate, rank in candidates[: self._candidate_limit]:
            if len(selected) >= self._article_limit:
                break
            diagnostic, token_count = await self._evaluate_candidate(
                candidate,
                rank,
                selected_tokens,
            )
            diagnostics.append(diagnostic)
            if diagnostic["selected"]:
                selected.append(candidate)
                selected_tokens += token_count

        await logger.ainfo(
            "knowledge retrieval completed",
            conversation_id=str(conversation_id),
            sources=sources,
            candidate_limit=self._candidate_limit,
            article_limit=self._article_limit,
            token_budget=self._token_budget,
            candidates=diagnostics,
            selected_count=len(selected),
            selected_token_count=selected_tokens,
            duration_ms=round((time.perf_counter() - started_at) * 1_000, 2),
        )
        return selected

    async def _combined_candidates(
        self,
        query: str,
        sources: list[KnowledgeSourceName] | None,
        carried_references: list[StoredKnowledgeReference],
    ) -> list[tuple[KnowledgeArticle | KnowledgeReference, float | None]]:
        current = await self._repository.search(query, sources, self._candidate_limit)
        current_articles = [candidate.article for candidate in current]
        allowed_carried = self._allowed_references(carried_references, sources)
        stored_articles = await self._repository.find_by_references(allowed_carried)
        stored_by_key = {(article.source, article.url): article for article in stored_articles}
        combined: list[tuple[KnowledgeArticle | KnowledgeReference, float | None]] = [
            (candidate.article, candidate.rank) for candidate in current
        ]
        seen = {(article.source, article.url) for article in current_articles}
        for reference in allowed_carried:
            key = (reference.source, reference.url)
            if key in seen:
                continue
            combined.append(
                (stored_by_key.get(key) or KnowledgeReference(**reference.model_dump()), None)
            )
            seen.add(key)
        return combined

    @staticmethod
    def _allowed_references(
        references: list[StoredKnowledgeReference],
        sources: list[KnowledgeSourceName] | None,
    ) -> list[StoredKnowledgeReference]:
        if sources is None:
            return references
        return [reference for reference in references if reference.source in sources]

    async def _evaluate_candidate(
        self,
        candidate: KnowledgeArticle | KnowledgeReference,
        rank: float | None,
        selected_tokens: int,
    ) -> tuple[dict[str, object], int]:
        cached = candidate.token_count is not None
        token_count = candidate.token_count or 0
        if not cached:
            token_count = await self._token_counter.count_tokens(candidate.as_reference())
            if isinstance(candidate, KnowledgeArticle):
                await self._repository.set_token_count(candidate.id, token_count)

        exclusion_reason = self._exclusion_reason(selected_tokens, token_count)
        return (
            {
                "title": candidate.title,
                "url": candidate.url,
                "rank": round(rank, 6) if rank is not None else None,
                "token_count": token_count,
                "token_count_cached": cached,
                "selected": exclusion_reason is None,
                "exclusion_reason": exclusion_reason,
            },
            token_count,
        )

    def _exclusion_reason(
        self,
        selected_tokens: int,
        token_count: int,
    ) -> str | None:
        if selected_tokens + token_count > self._token_budget:
            return "token_budget"
        return None
