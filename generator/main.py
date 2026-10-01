"""공식문서 기반 학습 노트 생성기의 CLI 진입점."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Keep the existing `python generator/main.py` command alongside `python -m generator`.
# Internal modules use package imports and never depend on the working directory.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.bootstrap import load_config, load_dotenv, load_prompt
from generator.contracts import ModelGatewayError
from generator.design.design_browser import BrowserSceneVerifier
from generator.design.design_pipeline import ArticleDesignPipeline
from generator.design.design_resume import load_saved_design
from generator.paths import GENERATOR_DIR as HERE
from generator.pipeline import GeneratorPipeline
from generator.providers.openrouter import OpenRouterGateway
from generator.publishing.jekyll import JekyllPreviewPublisher, JekyllPublisher
from generator.sources.source_context import OfficialDocumentSourceGateway
from generator.sources.topics import CatalogTopicRepository
from generator.tools.local_profile import add_local_options, local_settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-preview",
        metavar="NAME",
        help="일반 자동 생성 사이클을 실행하되 결과는 로컬 previews에만 저장",
    )
    parser.add_argument(
        "--topic-id", help="수동/카탈로그 주제 ID. 로컬에서 기존 주제 재생성에도 사용"
    )
    parser.add_argument(
        "--resume-design-run",
        type=Path,
        help="기존 .design-runs 폴더의 본문과 후보를 재사용 (--local-preview 필수)",
    )
    parser.add_argument(
        "--render-design-run",
        type=Path,
        help="저장 후보를 API 호출 없이 로컬 작업 화면으로 표시 (--local-preview 필수)",
    )
    parser.add_argument(
        "--preview-port", type=int, help="API 없는 작업 화면 포트 (기본 4011)"
    )
    add_local_options(parser)
    args = parser.parse_args(argv)
    if args.resume_design_run and (not args.local_preview or args.topic_id):
        parser.error(
            "--resume-design-run은 --local-preview와 함께 사용하며 주제 선택 옵션과 혼합할 수 없습니다."
        )
    local_options = (
        args.local_fast
        or args.preview_design_model
        or args.first_content_timeout is not None
    )
    if local_options and not args.local_preview:
        parser.error("로컬 속도 옵션은 --local-preview와 함께 사용하세요.")
    if args.preview_port is not None and (
        not args.render_design_run or not 1 <= args.preview_port <= 65535
    ):
        parser.error(
            "--preview-port는 --render-design-run 전용이며 1~65535여야 합니다."
        )
    if args.render_design_run:
        if (
            not args.local_preview
            or args.resume_design_run
            or args.topic_id
            or local_options
        ):
            parser.error(
                "--render-design-run은 --local-preview와만 사용하세요. API 생성 옵션과 혼합할 수 없습니다."
            )
        from generator.tools.local_preview import serve_saved_design

        try:
            # No dotenv, config, gateway, browser verifier or publisher on this path.
            serve_saved_design(
                args.render_design_run.resolve(),
                args.local_preview,
                args.preview_port or 4011,
            )
            return 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"로컬 화면 시작 실패: {exc}")
            return 1
    load_dotenv()
    cfg = load_config()
    try:
        cfg, deadline = local_settings(
            cfg,
            fast=args.local_fast,
            model=args.preview_design_model,
            timeout=args.first_content_timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))
    gateway_options = {}
    if deadline is not None:
        gateway_options["first_content_timeout"] = deadline
    if cfg.get("design_provider_preferences"):
        gateway_options["provider_preferences"] = cfg["design_provider_preferences"]
    models = OpenRouterGateway(**gateway_options)
    if local_options:
        print(
            f"로컬 디자인 모델 순서: {cfg.get('design_model_fallback', [])} / 첫 출력 대기: {deadline or '기본'}초 / 독립 검수 유지"
        )
    publisher_options = {
        "d2_theme": cfg.get("d2_theme", 3),
        "d2_sketch": cfg.get("d2_sketch", True),
        "require_design": cfg.get("design_required", False),
    }
    try:
        publisher = (
            JekyllPreviewPublisher(args.local_preview, **publisher_options)
            if args.local_preview
            else JekyllPublisher(**publisher_options)
        )
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    if args.resume_design_run:
        try:
            if not (
                cfg.get("review_enabled")
                and cfg.get("design_enabled")
                and cfg.get("design_required")
            ):
                raise ModelGatewayError(
                    "저장 후보 이어 실행에도 본문 검수·필수 시각화 설정이 필요합니다."
                )
            saved = load_saved_design(args.resume_design_run.resolve())
            print(f"저장된 본문 재사용: {saved.article.title}")
            result = ArticleDesignPipeline(
                models, load_prompt, BrowserSceneVerifier(), base_dir=HERE
            ).enhance(
                saved.article,
                saved.sources,
                cfg,
                initial_candidate=saved.candidate,
                initial_author_models=saved.author_models,
                initial_review_context=saved.review_context,
                initial_compact_candidate=saved.compact_candidate,
            )
            publication = publisher.publish(result)
            print(f"작성 완료: {publication.path}")
            return 0
        except ModelGatewayError as exc:
            print(f"디자인 이어 실행 보류: {exc}")
            return 1
    app = GeneratorPipeline(
        cfg=cfg,
        prompt_loader=load_prompt,
        model_gateway=models,
        publisher=publisher,
        topic_repository=CatalogTopicRepository(
            record_done=not bool(args.local_preview),
            gateway=models,
        ),
        source_gateway=OfficialDocumentSourceGateway(
            supporting_documents=cfg.get("supporting_documents", 0)
        ),
        generator_dir=HERE,
        design_pipeline=ArticleDesignPipeline(
            models, load_prompt, BrowserSceneVerifier(), base_dir=HERE
        ),
    )
    return app.run(args.topic_id or os.environ.get("FORCE_TOPIC_ID") or None)


if __name__ == "__main__":
    raise SystemExit(main())
