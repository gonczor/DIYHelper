import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup, Tag

from app.knowledge.domain import KnowledgeDocument, KnowledgeSourceName
from app.knowledge_ingestion.domain import CollectionResult
from app.knowledge_ingestion.sources.base import CollectionProgressCallback, KnowledgeSource

logger = structlog.get_logger(__name__)


class HackadaySource(KnowledgeSource):
    def __init__(
        self,
        client: httpx.AsyncClient,
        request_delay_seconds: float = 1.0,
        max_articles: int | None = None,
    ) -> None:
        self._client = client
        self._delay = request_delay_seconds
        self._max_articles = max_articles

    async def collect(
        self,
        start: datetime,
        end: datetime,
        on_progress: CollectionProgressCallback | None = None,
    ) -> CollectionResult:
        article_urls: dict[str, datetime] = {}
        day = start
        while day < end:
            page = 1
            while True:
                archive_url = f"https://hackaday.com/{day:%Y/%m/%d}/"
                if page > 1:
                    archive_url += f"page/{page}/"
                try:
                    response = await self._get(archive_url)
                except httpx.HTTPStatusError as error:
                    if page > 1 and error.response.status_code == httpx.codes.NOT_FOUND:
                        break
                    raise

                entries = [
                    (url, published_at)
                    for url, published_at in self._parse_archive(response.text, day)
                    if published_at.date() == day.date() and start <= published_at < end
                ]
                previous_count = len(article_urls)
                for url, published_at in entries:
                    article_urls[url] = published_at
                    if self._at_article_limit(article_urls):
                        break
                if self._at_article_limit(article_urls):
                    break
                if not entries or len(article_urls) == previous_count:
                    break
                page += 1

            if self._at_article_limit(article_urls):
                break
            day += timedelta(days=1)

        documents: list[KnowledgeDocument] = []
        failed = 0
        if on_progress is not None:
            await on_progress(len(article_urls), 0, 0)
        for url, published_at in article_urls.items():
            try:
                response = await self._get(url)
                documents.append(self._parse_article(response.text, url, published_at))
            except httpx.HTTPError, ValueError:
                failed += 1
                await logger.aexception("could not collect Hackaday article", url=url)
            if on_progress is not None:
                await on_progress(len(article_urls), len(documents), failed)

        return CollectionResult(documents=documents, discovered=len(article_urls), failed=failed)

    async def _get(self, url: str) -> httpx.Response:
        if self._delay:
            await asyncio.sleep(self._delay)
        response = await self._client.get(url)
        response.raise_for_status()
        return response

    def _parse_archive(self, html: str, archive_day: datetime) -> list[tuple[str, datetime]]:
        soup = BeautifulSoup(html, "html.parser")
        found: list[tuple[str, datetime]] = []
        for article in soup.select("article"):
            link = article.select_one("h1.entry-title a, h2.entry-title a")
            if not isinstance(link, Tag):
                continue
            url = link.get("href")
            if isinstance(url, str):
                published_at = self._published_at_from_url(url, archive_day)
                if published_at is not None:
                    found.append((url, published_at))
        return found

    def _published_at_from_url(self, url: str, archive_day: datetime) -> datetime | None:
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) < 3:
            return None
        try:
            return datetime(
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                tzinfo=archive_day.tzinfo,
            )
        except ValueError:
            return None

    def _at_article_limit(self, article_urls: dict[str, datetime]) -> bool:
        return self._max_articles is not None and len(article_urls) >= self._max_articles

    def _parse_article(self, html: str, url: str, published_at: datetime) -> KnowledgeDocument:
        soup = BeautifulSoup(html, "html.parser")
        article = soup.select_one("article")
        if not isinstance(article, Tag):
            raise ValueError("article element is missing")

        title = article.select_one("h1.entry-title, h2.entry-title")
        content = article.select_one(".entry-content")
        if not isinstance(title, Tag) or not isinstance(content, Tag):
            raise ValueError("article title or content is missing")

        for unwanted in content.select("script, style, .sharedaddy, .jp-relatedposts"):
            unwanted.decompose()
        text = content.get_text("\n", strip=True)
        if not text:
            raise ValueError("article content is empty")

        published_meta = soup.select_one('meta[property="article:published_time"][content]')
        if isinstance(published_meta, Tag):
            timestamp = published_meta.get("content")
            if isinstance(timestamp, str):
                published_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return KnowledgeDocument(
            source=KnowledgeSourceName.HACKADAY,
            title=title.get_text(" ", strip=True),
            url=url,
            content=text,
            published_at=published_at,
        )
