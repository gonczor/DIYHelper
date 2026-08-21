from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.domain import (
    KnowledgeArticle,
    KnowledgeDocument,
    KnowledgeSourceName,
    RankedKnowledgeArticle,
    StoredKnowledgeReference,
)
from app.knowledge.models import KnowledgeArticleRecord


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_documents(self, documents: list[KnowledgeDocument]) -> None:
        for document in documents:
            statement = insert(KnowledgeArticleRecord).values(**document.model_dump())
            existing = statement.excluded
            unchanged = (
                (KnowledgeArticleRecord.title == existing.title)
                & (KnowledgeArticleRecord.content == existing.content)
                & (KnowledgeArticleRecord.published_at.is_not_distinct_from(existing.published_at))
            )
            statement = statement.on_conflict_do_update(
                constraint="uq_knowledge_articles_source_url",
                set_={
                    "title": existing.title,
                    "content": existing.content,
                    "published_at": existing.published_at,
                    "token_count": case(
                        (unchanged, KnowledgeArticleRecord.token_count),
                        else_=None,
                    ),
                    "updated_at": func.now(),
                },
            )
            await self._session.execute(statement)
        await self._session.commit()

    async def search(
        self,
        query: str,
        sources: list[KnowledgeSourceName] | None,
        limit: int,
    ) -> list[RankedKnowledgeArticle]:
        """Return complete articles ranked by relevance to a user's query.

        ``websearch_to_tsquery`` converts ordinary user text into PostgreSQL's safe full-text query
        representation. ``ts_rank_cd`` scores matching rows against the weighted vector generated
        from each title and body. Optional source filtering is applied before the result limit, and
        publication time plus URL provide deterministic tie-breaking for equal ranks.
        """
        search_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(KnowledgeArticleRecord.search_vector, search_query).label("rank")
        statement = (
            select(KnowledgeArticleRecord, rank)
            .where(KnowledgeArticleRecord.search_vector.op("@@")(search_query))
            .order_by(
                rank.desc(),
                KnowledgeArticleRecord.published_at.desc().nullslast(),
                KnowledgeArticleRecord.url.asc(),
            )
            .limit(limit)
        )
        if sources is not None:
            statement = statement.where(KnowledgeArticleRecord.source.in_(sources))
        rows = (await self._session.execute(statement)).all()
        return [
            RankedKnowledgeArticle(
                article=self._to_domain(row.KnowledgeArticleRecord),
                rank=float(row.rank),
            )
            for row in rows
        ]

    async def set_token_count(self, article_id: UUID, token_count: int) -> None:
        article = await self._session.get(KnowledgeArticleRecord, article_id)
        if article is None:
            raise LookupError(str(article_id))
        article.token_count = token_count
        await self._session.commit()

    async def find_by_references(
        self,
        references: list[StoredKnowledgeReference],
    ) -> list[KnowledgeArticle]:
        if not references:
            return []
        filters = [
            and_(
                KnowledgeArticleRecord.source == reference.source,
                KnowledgeArticleRecord.url == reference.url,
            )
            for reference in references
        ]
        records = (
            await self._session.scalars(select(KnowledgeArticleRecord).where(or_(*filters)))
        ).all()
        articles_by_key = {
            (record.source, record.url): self._to_domain(record) for record in records
        }
        return [
            articles_by_key[(reference.source, reference.url)]
            for reference in references
            if (reference.source, reference.url) in articles_by_key
        ]

    @staticmethod
    def _to_domain(record: KnowledgeArticleRecord) -> KnowledgeArticle:
        return KnowledgeArticle(
            id=record.id,
            source=KnowledgeSourceName(record.source),
            url=record.url,
            title=record.title,
            content=record.content,
            published_at=record.published_at,
            token_count=record.token_count,
        )
