from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from app.knowledge.domain import KnowledgeArticle, KnowledgeSearchResult, RankedKnowledgeArticle
from app.knowledge.service import KnowledgeSelectionService


def candidate(number: int, rank: float, token_count: int | None = None) -> RankedKnowledgeArticle:
    return RankedKnowledgeArticle(
        article=KnowledgeArticle(
            id=uuid4(),
            source="hackaday",
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
        return KnowledgeSearchResult(
            search_expression="'easi' & 'project'",
            candidates=self.candidates[:limit],
        )

    async def set_token_count(self, article_id, token_count):
        self.saved_counts.append((article_id, token_count))


class StubTokenCounter:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts
        self.calls = []

    async def count_tokens(self, content: str) -> int:
        self.calls.append(content)
        return self.counts[content]


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

    selected = await service.select("easy project", ["hackaday"], uuid4())

    assert selected == [candidates[0].article, candidates[1].article]
    assert counter.calls == [first_reference]
    assert repository.saved_counts == [(candidates[0].article.id, 40)]
    assert repository.search_calls == [("easy project", ["hackaday"], 10)]


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
async def test_logs_rank_and_selection_without_article_content() -> None:
    candidates = [candidate(1, 0.9, 25), candidate(2, 0.8, 50)]
    service = KnowledgeSelectionService(
        StubRepository(candidates),
        StubTokenCounter({}),
        candidate_limit=10,
        article_limit=1,
        token_budget=100,
    )
    conversation_id = uuid4()

    with capture_logs() as logs:
        await service.select("private question text", ["hackaday"], conversation_id)

    event = next(log for log in logs if log["event"] == "knowledge retrieval completed")
    assert event["conversation_id"] == str(conversation_id)
    assert event["sources"] == ["hackaday"]
    assert event["search_expression"] == "'easi' & 'project'"
    assert event["candidate_limit"] == 10
    assert event["article_limit"] == 1
    assert event["token_budget"] == 100
    assert event["selected_count"] == 1
    assert event["selected_token_count"] == 25
    assert event["candidates"] == [
        {
            "title": "Article 1",
            "url": "https://example.test/1",
            "rank": 0.9,
            "token_count": 25,
            "token_count_cached": True,
            "selected": True,
            "exclusion_reason": None,
        },
        {
            "title": "Article 2",
            "url": "https://example.test/2",
            "rank": 0.8,
            "token_count": 50,
            "token_count_cached": True,
            "selected": False,
            "exclusion_reason": "article_limit",
        },
    ]
    assert "private question text" not in str(event)
    assert "Content 1" not in str(event)
