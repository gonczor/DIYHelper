from uuid import uuid4

from app.knowledge.domain import KnowledgeArticle, KnowledgeSourceName


def test_article_reference_includes_taxonomy() -> None:
    article = KnowledgeArticle(
        id=uuid4(),
        source=KnowledgeSourceName.HACKADAY,
        title="Controller",
        url="https://example.test/controller",
        content="Article body.",
        categories=["Microcontrollers"],
        tags=["ATmega328P", "Arduino"],
    )

    reference = article.as_reference()

    assert "categories: Microcontrollers" in reference
    assert "tags: ATmega328P, Arduino" in reference
