"""공식문서 기반 학습 노트 생성기의 CLI 진입점."""

from __future__ import annotations

import json
import os
from pathlib import Path

from llm import OpenRouterGateway
from pipeline import GeneratorPipeline
from publishing import JekyllPublisher
from source_context import OfficialDocumentSourceGateway
from topics import CatalogTopicRepository

HERE = Path(__file__).resolve().parent


def load_dotenv() -> None:
    """generator/.env가 있으면 로컬 실행 환경에 추가한다."""
    env_path = HERE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'"),
        )


def load_config() -> dict:
    return json.loads((HERE / "sources.json").read_text(encoding="utf-8"))


def load_prompt(name: str) -> str:
    return (HERE / "prompts" / name).read_text(encoding="utf-8")


def main() -> int:
    load_dotenv()
    cfg = load_config()
    app = GeneratorPipeline(
        cfg=cfg,
        prompt_loader=load_prompt,
        model_gateway=OpenRouterGateway(),
        publisher=JekyllPublisher(
            d2_theme=cfg.get("d2_theme", 3),
            d2_sketch=cfg.get("d2_sketch", True),
        ),
        topic_repository=CatalogTopicRepository(),
        source_gateway=OfficialDocumentSourceGateway(),
        generator_dir=HERE,
    )
    return app.run(os.environ.get("FORCE_TOPIC_ID") or None)


if __name__ == "__main__":
    raise SystemExit(main())
