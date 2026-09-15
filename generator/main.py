"""공식문서 기반 학습 노트 생성기의 CLI 진입점."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Keep both direct script execution and `python -m generator` working.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.bootstrap import load_config, load_dotenv, load_prompt
from generator.paths import GENERATOR_DIR as HERE
from generator.providers.openrouter import OpenRouterGateway
from generator.pipeline import GeneratorPipeline
from generator.publishing.jekyll import JekyllPublisher
from generator.sources.source_context import OfficialDocumentSourceGateway
from generator.sources.topics import CatalogTopicRepository

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
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
