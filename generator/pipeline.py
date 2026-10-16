"""공식문서 기반 게시물 생성 단계를 순서대로 조율한다."""

from __future__ import annotations

import html
import sys
from collections.abc import Callable
from pathlib import Path

from generator.contracts import (
    Article,
    ArticleDesigner,
    LanguageModelGateway,
    ModelGatewayError,
    Publisher,
    SourceBundle,
    SourceGateway,
    TopicRepository,
)
from generator.content.quality import extract_title, source_quality
from generator.content.review_pipeline import ArticleReviewPipeline, ReviewRejectedError
from generator.pending_post import PendingPostStore


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
        design_pipeline: ArticleDesigner | None = None,
        pending_store: PendingPostStore | None = None,
    ) -> None:
        self._cfg = cfg
        self._load_prompt = prompt_loader
        self._models = model_gateway
        self._publisher = publisher
        self._topics = topic_repository
        self._sources = source_gateway
        self._generator_dir = generator_dir
        self._design = design_pipeline
        self._pending = pending_store
        self._review = ArticleReviewPipeline(
            model_gateway,
            prompt_loader,
            artifact_base_dir=generator_dir,
        )

    def run(self, forced_topic_id: str | None = None) -> int:
        cfg = self._cfg
        retries = cfg.get("source_topic_retries", 2)
        if type(retries) is not int or not 0 <= retries <= 2:
            print(
                "[실패] source_topic_retries는 0~2의 정수여야 합니다.", file=sys.stderr
            )
            return 1
        if cfg.get("design_required", False):
            if (
                not cfg.get("review_enabled")
                or not cfg.get("design_enabled")
                or self._design is None
            ):
                print(
                    "[실패] 필수 시각화에는 내용 검수와 디자인 단계가 필요합니다.",
                    file=sys.stderr,
                )
                return 1
            try:
                # A missing browser must not waste paid drafting/review calls.
                self._design.preflight()
            except ModelGatewayError as exc:
                print(f"[실패] {exc}", file=sys.stderr)
                return 1
        store = (
            self._pending
            if not forced_topic_id
            and cfg.get("review_enabled")
            and cfg.get("design_required")
            else None
        )
        pending = store.resume() if store else None
        if pending:
            topic = {"id": pending.topic_id}
            article = pending.article
            hint = article.title
            sources_block = pending.sources
            source_urls = list(article.source_urls)
        else:
            selected = self._select_supported_topic(
                forced_topic_id,
                retries=retries,
                excluded_ids=store.excluded_ids if store else (),
            )
            if selected is None:
                return 0
            topic, sources = selected
            article = None
            hint = sources.title_hint
            sources_block = sources.prompt_context
            source_urls = list(sources.cite_urls)
        models = self._select_models()

        system_prompt = self._load_prompt(cfg.get("system_prompt", "system.md"))
        user_prompt = self._load_prompt("user_template.md").format(
            title_hint=html.escape(hint, quote=True),
            tags=html.escape(", ".join(topic.get("tags", [])), quote=True),
            sources_block=sources_block,
        )

        try:
            if article is None:
                article = self._generate_draft(
                    topic,
                    hint,
                    source_urls,
                    system_prompt,
                    user_prompt,
                    models,
                )
            if cfg.get("review_enabled", False):
                final_article = self._review.run(
                    article,
                    topic_id=topic["id"],
                    sources_block=sources_block,
                    system_prompt=system_prompt,
                    writer_models=models,
                    cfg=cfg,
                )
                if store:
                    store.save(topic["id"], final_article, sources_block)
                if self._design is not None and cfg.get("design_enabled", False):
                    final_article = self._design.enhance(
                        final_article, sources_block, cfg
                    )
                article = final_article
            # No draft is written to the live Jekyll tree before review completes.
            if cfg.get("design_required", False) and (
                not cfg.get("review_enabled", False)
                or not article.presentation
                or not article.presentation.scenes
            ):
                raise ReviewRejectedError("필수 시각화 미통과 — 발행 보류")
            publication = self._publisher.publish(article)
        except (ModelGatewayError, ReviewRejectedError) as exc:
            print(f"[실패] {exc}", file=sys.stderr)
            return 1

        self._topics.mark_done(topic["id"])
        # Git push may still fail after local publication. Keep the checkpoint
        # until the next run sees this topic in the persisted completion record.
        try:
            displayed_path = publication.path.relative_to(self._generator_dir.parent)
        except ValueError:
            displayed_path = publication.path
        print(f"작성 완료: {displayed_path}")
        return 0

    def _select_supported_topic(
        self, forced_topic_id: str | None, *, retries: int, excluded_ids=()
    ) -> tuple[dict, SourceBundle] | None:
        """자동 선택의 출처 부족만 재선택한다. 검수·생성 실패의 재시도는 별도다."""
        cfg = self._cfg
        limit = 1 if forced_topic_id else 1 + retries
        tried: set[str] = set(excluded_ids)
        for attempt in range(1, limit + 1):
            topic = self._topics.select(
                cfg, forced_topic_id, excluded_ids=frozenset(tried)
            )
            if topic is None:
                print(
                    "생성할 새 주제가 없습니다(모두 소진 또는 잘못된 FORCE_TOPIC_ID). 종료."
                )
                return None
            if topic["id"] in tried:
                print("이미 확인한 주제가 다시 선택되어 재선택을 중단합니다.")
                return None
            tried.add(topic["id"])
            print(
                f"선택된 주제 ({attempt}/{limit}): {topic['id']} - "
                f"{topic.get('title_hint') or '(fetch 후 제목 추출)'}"
            )
            print("공식문서 fetch 중...")
            sources = self._sources.fetch(
                topic,
                user_agent=cfg["user_agent"],
                max_chars=cfg.get("max_chars_per_source", 16000),
            )
            if not sources.cite_urls:
                # 일시적인 수집 실패는 이번 실행에서만 제외하고 다음 날 재확인한다.
                print(
                    "사용 가능한 출처가 없습니다(robots 차단/오류). 완료로 기록하지 않습니다."
                )
            else:
                enough, reason = source_quality(
                    sources.documents,
                    cfg.get("min_total_source_chars", 0),
                    cfg.get("min_substantive_source_chars", 0),
                )
                if enough:
                    print(f"  출처 품질: {reason}")
                    return topic, sources
                print(f"출처 품질 부족({reason}) — 억지로 글을 만들지 않습니다.")
                if sources.documents and all(
                    item.get("ok") for item in sources.documents
                ):
                    self._topics.mark_done(topic["id"])
                else:
                    print(
                        "  일부 출처 수집 실패 — 완료로 기록하지 않고 다음 실행에 재확인합니다."
                    )
            if attempt < limit:
                print(f"  다른 주제로 재선택합니다. (추가 시도 {attempt}/{retries})")
        print(f"출처 검사 {limit}개 주제 미통과 — 이번 실행은 발행 없이 종료합니다.")
        return None

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
    ) -> Article:
        print("LLM 생성 중(fallback 체인)...")
        generated = self._models.generate(
            system_prompt, user_prompt, models, purpose="초안 생성"
        )
        title, body = extract_title(generated.content, hint)
        # D2 rendering belongs to final publication. Do not publish a draft merely
        # to detect a missing diagram and then delete it for a generation retry.
        return Article(
            title=title,
            body=body,
            model=generated.model,
            tags=tuple(topic.get("tags", [])),
            source_urls=tuple(source_urls),
        )
