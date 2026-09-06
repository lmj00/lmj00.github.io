"""게시물 출력 대상을 파이프라인 계약에 연결하는 어댑터."""

from __future__ import annotations

import post_writer
from contracts import Article, Publication


class JekyllPublisher:
    """Article을 Jekyll Markdown과 D2 SVG로 발행한다."""

    def __init__(self, *, d2_theme: int = 3, d2_sketch: bool = True) -> None:
        flags = [f"--theme={d2_theme}"]
        if d2_sketch:
            flags.append("--sketch")
        flags.append("--pad=40")
        post_writer.D2_FLAGS = flags

    def publish(self, article: Article) -> Publication:
        path = post_writer.write_post(
            title=article.title,
            body=article.body,
            model=article.model,
            tags=list(article.tags),
            source_urls=list(article.source_urls),
        )
        has_diagram = "assets/diagrams" in path.read_text(encoding="utf-8")
        return Publication(path=path, has_diagram=has_diagram)

    def discard(self, publication: Publication) -> None:
        """임시 게시물과 그 게시물에서 렌더링한 SVG를 제거한다."""
        path = publication.path
        path.unlink(missing_ok=True)
        diagrams = post_writer.ASSETS_DIR
        if diagrams.exists():
            for svg in diagrams.glob(f"{path.stem}-*.svg"):
                svg.unlink(missing_ok=True)
