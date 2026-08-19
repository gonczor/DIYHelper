import time
from typing import Protocol
from uuid import UUID

import structlog

from app.knowledge.domain import KnowledgeArticle, RankedKnowledgeArticle
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
        sources: list[str] | None,
        conversation_id: UUID,
    ) -> list[KnowledgeArticle]:
        started_at = time.perf_counter()
        result = await self._repository.search(query, sources, self._candidate_limit)
        selected: list[KnowledgeArticle] = []
        selected_tokens = 0
        diagnostics: list[dict[str, object]] = []
        for candidate in result.candidates:
            diagnostic, token_count = await self._evaluate_candidate(
                candidate,
                len(selected),
                selected_tokens,
            )
            diagnostics.append(diagnostic)
            if diagnostic["selected"]:
                selected.append(candidate.article)
                selected_tokens += token_count

        logger.info(
            "knowledge retrieval completed",
            conversation_id=str(conversation_id),
            sources=sources,
            search_expression=result.search_expression,
            candidate_limit=self._candidate_limit,
            article_limit=self._article_limit,
            token_budget=self._token_budget,
            candidates=diagnostics,
            selected_count=len(selected),
            selected_token_count=selected_tokens,
            duration_ms=round((time.perf_counter() - started_at) * 1_000, 2),
        )
        return selected

    async def _evaluate_candidate(
        self,
        candidate: RankedKnowledgeArticle,
        selected_count: int,
        selected_tokens: int,
    ) -> tuple[dict[str, object], int]:
        cached = candidate.article.token_count is not None
        token_count = candidate.article.token_count or 0
        if selected_count < self._article_limit and not cached:
            token_count = await self._token_counter.count_tokens(candidate.article.as_reference())
            await self._repository.set_token_count(candidate.article.id, token_count)

        exclusion_reason = self._exclusion_reason(selected_count, selected_tokens, token_count)
        return (
            {
                "title": candidate.article.title,
                "url": candidate.article.url,
                "rank": round(candidate.rank, 6),
                "token_count": (
                    token_count if cached or selected_count < self._article_limit else None
                ),
                "token_count_cached": cached,
                "selected": exclusion_reason is None,
                "exclusion_reason": exclusion_reason,
            },
            token_count,
        )

    def _exclusion_reason(
        self,
        selected_count: int,
        selected_tokens: int,
        token_count: int,
    ) -> str | None:
        if selected_count >= self._article_limit:
            return "article_limit"
        if selected_tokens + token_count > self._token_budget:
            return "token_budget"
        return None
