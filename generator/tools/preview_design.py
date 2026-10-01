"""이미 검수한 초안으로 디자인 단계만 실행한다. 주제 상태·기존 게시물은 변경하지 않는다."""

from __future__ import annotations

import argparse
from pathlib import Path

from generator.contracts import Article, ModelGatewayError
from generator.design.design_browser import BrowserSceneVerifier
from generator.design.design_pipeline import ArticleDesignPipeline
from generator.providers.openrouter import OpenRouterGateway
from generator.bootstrap import load_config, load_dotenv, load_prompt
from generator.paths import GENERATOR_DIR as HERE
from generator.tools.local_profile import add_local_options, local_settings
from generator.publishing.jekyll import JekyllPreviewPublisher
from generator.content.quality import extract_title
from generator.design.visual_contracts import source_sections


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--draft",
        type=Path,
        required=True,
        help="검수 비교 자료의 after.md (제목: ... 형식)",
    )
    parser.add_argument(
        "--sources", type=Path, required=True, help="같은 실행의 source-documents.xml"
    )
    parser.add_argument(
        "--name", default="auto-design", help="새 미리보기 이름, 영문/숫자/하이픈"
    )
    parser.add_argument(
        "--generation-format",
        choices=("compact", "legacy"),
        help="같은 본문·모델로 생성 계약을 비교 (설정 파일은 변경하지 않음)",
    )
    parser.add_argument(
        "--provider-order",
        nargs="+",
        help="동일 모델의 공급자 slug 우선순위 실험 (다른 공급자로 fallback 가능)",
    )
    parser.add_argument(
        "--provider-sort",
        choices=("latency", "throughput", "price"),
        help="동일 모델 공급자 라우팅 실험; 품질을 보장하는 옵션은 아님",
    )
    add_local_options(parser)
    args = parser.parse_args(argv)
    try:
        publisher = JekyllPreviewPublisher(
            args.name, root=HERE.parent, require_design=True
        )
        cfg, deadline = local_settings(
            load_config(),
            fast=args.local_fast,
            model=args.preview_design_model,
            timeout=args.first_content_timeout,
        )
        if args.generation_format:
            cfg["design_generation_format"] = args.generation_format
        if args.provider_order or args.provider_sort:
            preferences = dict(cfg.get("design_provider_preferences", {}))
            if args.provider_order:
                preferences["order"] = args.provider_order
            if args.provider_sort:
                preferences["sort"] = args.provider_sort
            cfg["design_provider_preferences"] = preferences
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    sources = args.sources.read_text(encoding="utf-8")
    urls = tuple(section["url"] for section in source_sections(sources))
    title, body = extract_title(
        args.draft.read_text(encoding="utf-8"), "디자인 미리보기"
    )
    original = Article(title, body, "existing-reviewed-draft", (), urls)
    load_dotenv()
    gateway_options = {"first_content_timeout": deadline}
    if cfg.get("design_provider_preferences"):
        gateway_options["provider_preferences"] = cfg["design_provider_preferences"]
    designer = ArticleDesignPipeline(
        OpenRouterGateway(**gateway_options),
        load_prompt,
        BrowserSceneVerifier(),
        base_dir=HERE,
    )
    try:
        result = designer.enhance(original, sources, cfg)
    except ModelGatewayError as exc:
        print(f"디자인 보류: {exc}")
        return 1
    if result.presentation is None:
        print(
            "디자인 미통과: 미리보기는 생성하지 않았습니다. .design-runs 기록을 확인하세요."
        )
        return 1
    publisher.publish(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
