import pytest
from pydantic import ValidationError

from app.knowledge.domain import KnowledgeSourceName
from app.questions.schemas import AskQuestionRequest


def test_omitted_sources_remains_none_to_select_all_sources() -> None:
    request = AskQuestionRequest(question="question")

    assert request.sources is None


def test_empty_sources_remains_empty_to_select_broad_knowledge() -> None:
    request = AskQuestionRequest(question="question", sources=[])

    assert request.sources == []


def test_sources_are_normalized_and_deduplicated() -> None:
    request = AskQuestionRequest(question="question", sources=[" Hackaday ", "hackaday"])

    assert request.sources == [KnowledgeSourceName.HACKADAY]


def test_rejects_unknown_source() -> None:
    with pytest.raises(ValidationError):
        AskQuestionRequest(question="question", sources=["unknown"])
