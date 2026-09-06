"""공식문서 기반 게시물 생성 단계를 순서대로 조율한다."""

from __future__ import annotations

import html
import sys
from collections.abc import Callable
from pathlib import Path

from contracts import (
    Article,
    LanguageModelGateway,
    ModelGatewayError,
    Publication,
    Publisher,
    SourceGateway,
    TopicRepository,
)
from quality import extract_title, source_quality
from review_pipeline import ArticleReviewPipeline, ReviewRejectedError


class GeneratorPipeline:
    """구체적인 모델·출력 구현을 주입받아 생성 유스케이스를 실행한다."""

    def __init__(
        self,
        *,
        cfg: dict,
        prompt_loader: Callable[[str], str],
        model_gateway: LanguageModelGateway,
        publisher: Publisher,
        topic_repository: TopicRepository,
        source_gateway: SourceGateway,
        generator_dir: Path,
    ) -> None:
        self._cfg = cfg
        self._load_prompt = prompt_loader
        self._models = model_gateway
        self._publisher = publisher
        self._topics = topic_repository
        self._sources = source_gateway
        self._generator_dir = generator_dir
        self._review = ArticleReviewPipeline(
            model_gateway,
            prompt_loader,
            artifact_base_dir=generator_dir,
        )

    def run(self, forced_topic_id: str | None = None) -> int:
        cfg = self._cfg
        models = self._select_models()
        topic = self._topics.select(cfg, forced_topic_id)
        if topic is None:
            print(
                "생성할 새 주제가 없습니다(모두 소진 또는 잘못된 FORCE_TOPIC_ID). 종료."
            )
            return 0

        print(
            f"선택된 주제: {topic['id']} - "
            f"{topic.get('title_hint') or '(fetch 후 제목 추출)'}"
        )
        print("공식문서 fetch 중...")
        sources = self._sources.fetch(
            topic,
            user_agent=cfg["user_agent"],
            max_chars=cfg.get("max_chars_per_source", 16000),
        )
        if not sources.cite_urls:
            print(
                "사용 가능한 출처가 없습니다(robots 차단/오류). 이 주제는 건너뜁니다."
            )
            return 0

        enough, source_reason = source_quality(
            sources.documents,
            cfg.get("min_total_source_chars", 0),
            cfg.get("min_substantive_source_chars", 0),
        )
        if not enough:
            print(f"출처 품질 부족({source_reason}) — 억지로 글을 만들지 않습니다.")
            self._topics.mark_done(topic["id"])
            return 0
        print(f"  출처 품질: {source_reason}")

        hint = sources.title_hint
        system_prompt = self._load_prompt(cfg.get("system_prompt", "system.md"))
        user_prompt = self._load_prompt("user_template.md").format(
            title_hint=html.escape(hint, quote=True),
            tags=html.escape(", ".join(topic.get("tags", [])), quote=True),
            sources_block=sources.prompt_context,
        )

        publication = None
        try:
            article, publication = self._generate_draft(
                topic,
                hint,
                list(sources.cite_urls),
                system_prompt,
                user_prompt,
                models,
            )
            if cfg.get("review_enabled", False):
                final_article = self._review.run(
                    article,
                    topic_id=topic["id"],
                    sources_block=sources.prompt_context,
                    system_prompt=system_prompt,
                    writer_models=models,
                    cfg=cfg,
                )
                if final_article != article:
                    self._publisher.discard(publication)
                    publication = self._publisher.publish(final_article)
                    article = final_article
                    print(
                        f"  수정 완료: {article.title} / {len(article.body)}자 "
                        f"/ 모델 {article.model}"
                    )
        except (ModelGatewayError, ReviewRejectedError) as exc:
            if publication is not None:
                self._publisher.discard(publication)
            print(f"[실패] {exc}", file=sys.stderr)
            return 1

        self._topics.mark_done(topic["id"])
        try:
            displayed_path = publication.path.relative_to(self._generator_dir.parent)
        except ValueError:
            displayed_path = publication.path
        print(f"작성 완료: {displayed_path}")
        return 0

    def _select_models(self) -> list[str]:
        cfg = self._cfg
        if cfg.get("model_selection") != "auto":
            return cfg.get("model_fallback", [])
        models = self._models.build_fallback_chain(
            cfg.get("model_prefer", []),
            cfg.get("model_exclude", []),
            seed=cfg.get("model_seed", []),
        )
        print(f"무료모델 실시간 조회: {len(models)}개 (상위: {', '.join(models[:3])})")
        return models

    def _generate_draft(
        self,
        topic: dict,
        hint: str,
        source_urls: list[str],
        system_prompt: str,
        user_prompt: str,
        models: list[str],
    ) -> tuple[Article, Publication]:
        print("LLM 생성 중(fallback 체인)...")
        retry_tags = set(self._cfg.get("diagram_retry_tags", []))
        diagram_worthy = bool(retry_tags & set(topic.get("tags", [])))
        retries = self._cfg.get("diagram_retries", 0) if diagram_worthy else 0
        if retries == 0:
            print("  (다이어그램은 선택 사항 — 재시도 없이 1회 생성)")

        for attempt in range(retries + 1):
            generated = self._models.generate(
                system_prompt,
                user_prompt,
                models,
                purpose="초안 생성",
            )
            title, body = extract_title(generated.content, hint)
            article = Article(
                title=title,
                body=body,
                model=generated.model,
                tags=tuple(topic.get("tags", [])),
                source_urls=tuple(source_urls),
            )
            publication = self._publisher.publish(article)
            if publication.has_diagram or attempt == retries:
                mark = "O" if publication.has_diagram else "X(수용)"
                print(
                    f"  성공 모델: {article.model}  "
                    f"(제목: {article.title} / {len(article.body)}자 "
                    f"/ 다이어그램 {mark})"
                )
                return article, publication
            print(f"  다이어그램 없음(시도 {attempt + 1}/{retries + 1}) → 재생성")
            self._publisher.discard(publication)

        raise RuntimeError("생성 결과 파일을 찾을 수 없습니다.")
