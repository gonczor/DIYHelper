from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.knowledge.domain import KnowledgeArticle, KnowledgeSourceName, RankedKnowledgeArticle
from app.knowledge.service import KnowledgeSelectionService


def candidate(number: int, rank: float, token_count: int | None = None) -> RankedKnowledgeArticle:
    return RankedKnowledgeArticle(
        article=KnowledgeArticle(
            id=uuid4(),
            source=KnowledgeSourceName.HACKADAY,
            url=f"https://example.test/{number}",
            title=f"Article {number}",
            content=f"Content {number}",
            published_at=None,
            token_count=token_count,
        ),
        rank=rank,
    )


class StubRepository:
    def __init__(self, candidates: list[RankedKnowledgeArticle]) -> None:
        self.candidates = candidates
        self.search_calls = []
        self.saved_counts = []

    async def search(self, query, sources, limit):
        self.search_calls.append((query, sources, limit))
        return self.candidates[:limit]

    async def set_token_count(self, article_id, token_count):
        self.saved_counts.append((article_id, token_count))


class StubTokenCounter:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts
        self.calls = []

    async def count_tokens(self, content: str) -> int:
        self.calls.append(content)
        return self.counts[content]


@pytest.fixture(autouse=True)
def async_logger(monkeypatch: pytest.MonkeyPatch) -> Mock:
    logger = Mock()
    logger.ainfo = AsyncMock()
    monkeypatch.setattr("app.knowledge.service.logger", logger)
    return logger


@pytest.mark.asyncio
async def test_selects_ranked_articles_with_lazy_token_counts_and_limits() -> None:
    candidates = [candidate(1, 0.9), candidate(2, 0.8, 30), candidate(3, 0.7)]
    first_reference = candidates[0].article.as_reference()
    counter = StubTokenCounter({first_reference: 40})
    repository = StubRepository(candidates)
    service = KnowledgeSelectionService(
        repository,
        counter,
        candidate_limit=10,
        article_limit=2,
        token_budget=100,
    )

    selected = await service.select("easy project", [KnowledgeSourceName.HACKADAY], uuid4())

    assert selected == [candidates[0].article, candidates[1].article]
    assert counter.calls == [first_reference]
    assert repository.saved_counts == [(candidates[0].article.id, 40)]
    assert repository.search_calls == [("easy project", [KnowledgeSourceName.HACKADAY], 10)]


@pytest.mark.asyncio
async def test_skips_article_that_exceeds_remaining_budget_and_tries_next() -> None:
    candidates = [candidate(1, 0.9, 80), candidate(2, 0.8, 30), candidate(3, 0.7, 15)]
    service = KnowledgeSelectionService(
        StubRepository(candidates),
        StubTokenCounter({}),
        candidate_limit=10,
        article_limit=3,
        token_budget=100,
    )

    selected = await service.select("project", None, uuid4())

    assert selected == [candidates[0].article, candidates[2].article]


@pytest.mark.asyncio
async def test_stops_and_logs_asynchronously_after_reaching_article_limit(
    async_logger: Mock,
) -> None:
    candidates = [candidate(1, 0.9, 25), candidate(2, 0.8)]
    repository = StubRepository(candidates)
    counter = StubTokenCounter({candidates[1].article.as_reference(): 50})
    service = KnowledgeSelectionService(
        repository,
        counter,
        candidate_limit=10,
        article_limit=1,
        token_budget=100,
    )
    conversation_id = uuid4()
    await service.select("private question text", [KnowledgeSourceName.HACKADAY], conversation_id)

    async_logger.ainfo.assert_awaited_once()
    call = async_logger.ainfo.await_args
    assert call.args == ("knowledge retrieval completed",)
    assert call.kwargs["conversation_id"] == str(conversation_id)
    assert call.kwargs["sources"] == [KnowledgeSourceName.HACKADAY]
    assert call.kwargs["candidate_limit"] == 10
    assert call.kwargs["article_limit"] == 1
    assert call.kwargs["token_budget"] == 100
    assert call.kwargs["selected_count"] == 1
    assert call.kwargs["selected_token_count"] == 25
    assert call.kwargs["candidates"] == [
        {
            "title": "Article 1",
            "url": "https://example.test/1",
            "rank": 0.9,
            "token_count": 25,
            "token_count_cached": True,
            "selected": True,
            "exclusion_reason": None,
        }
    ]
    assert counter.calls == []
    assert "private question text" not in str(call.kwargs)
    assert "Content 1" not in str(call.kwargs)
