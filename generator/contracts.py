"""생성 파이프라인의 교체 가능한 경계와 공통 데이터 타입."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

ReviewReport = dict[str, Any]


@dataclass(frozen=True)
class GeneratedText:
    """모델이 생성한 텍스트와 실제로 응답한 모델."""

    content: str
    model: str


@dataclass(frozen=True)
class ReviewResult:
    """독립 검수 결과와 실제로 검수한 모델."""

    report: ReviewReport
    model: str


@dataclass(frozen=True)
class Article:
    """출력 형식과 무관한 최종 게시물 데이터."""

    title: str
    body: str
    model: str
    tags: tuple[str, ...]
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class SourceBundle:
    """출처 구현이 파이프라인에 전달하는 정규화된 공식문서 묶음."""

    documents: list[dict]
    prompt_context: str
    cite_urls: tuple[str, ...]
    title_hint: str


@dataclass(frozen=True)
class Publication:
    """출력 구현이 만든 결과와 파이프라인 정책에 필요한 메타데이터."""

    path: Path
    has_diagram: bool


class ModelGatewayError(RuntimeError):
    """모델 제공자 호출 또는 응답 계약이 실패했을 때 발생한다."""


@runtime_checkable
class LanguageModelGateway(Protocol):
    """OpenRouter·직접 API·로컬 모델이 공통으로 구현할 계약."""

    def build_fallback_chain(
        self,
        prefer: list[str],
        exclude: list[str],
        seed: list[str] | None = None,
    ) -> list[str]: ...

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_fallback: list[str],
        purpose: str = "글 생성",
    ) -> GeneratedText: ...

    def review(
        self,
        system_prompt: str,
        user_prompt: str,
        model_fallback: list[str],
        max_tokens: int = 4000,
        reasoning_tokens: int = 1200,
    ) -> ReviewResult: ...


@runtime_checkable
class Publisher(Protocol):
    """Jekyll Markdown·HTML 등 게시 대상이 공통으로 구현할 계약."""

    def publish(self, article: Article) -> Publication: ...

    def discard(self, publication: Publication) -> None: ...


@runtime_checkable
class TopicRepository(Protocol):
    """수동 목록·카탈로그·DB 등 주제 저장 방식의 계약."""

    def select(self, cfg: dict, forced_id: str | None = None) -> dict | None: ...

    def mark_done(self, topic_id: str) -> None: ...


@runtime_checkable
class SourceGateway(Protocol):
    """웹·파일·API 등 공식문서를 가져오는 방식의 계약."""

    def fetch(
        self,
        topic: dict,
        *,
        user_agent: str,
        max_chars: int,
    ) -> SourceBundle: ...
