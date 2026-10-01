"""게시물 출력 대상을 파이프라인 계약에 연결하는 어댑터."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from dataclasses import replace
from pathlib import Path

import generator.publishing.post_writer as post_writer
from generator.contracts import Article, Publication
from generator.paths import PROJECT_ROOT


class JekyllPreviewPublisher:
    """Use the normal publisher, but keep the finished post in local previews only."""

    def __init__(self, name: str, *, root: Path | None = None, **options):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", name):
            raise ValueError("미리보기 이름은 영문 소문자·숫자·하이픈으로 지정하세요.")
        self._name = name
        self._root = root or PROJECT_ROOT
        self._options = options
        self._target = self._root / "previews" / f"{name}.md"
        self.preflight()

    def preflight(self):
        for target in (self._target, self._target.with_suffix(".html")):
            if target.exists():
                raise FileExistsError(f"기존 미리보기 보존: {target}")

    def publish(self, article: Article) -> Publication:
        self.preflight()
        # Prefix only the asset/post filename to avoid collision with real posts.
        preview_article = replace(article, title=f"{self._name} {article.title}")
        with tempfile.TemporaryDirectory(prefix="local-post-preview-") as temporary:
            publisher = JekyllPublisher(output_dir=Path(temporary), **self._options)
            publication = publisher.publish(preview_article)
            content = publication.path.read_text(encoding="utf-8").replace(
                "layout: post\n",
                f"layout: post\nsitemap: false\npermalink: /previews/{self._name}/\n",
                1,
            )
            self.preflight()
            self._target.parent.mkdir(parents=True, exist_ok=True)
            staging = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self._target.parent, prefix=".preview-", delete=False
                ) as handle:
                    staging = Path(handle.name)
                    handle.write(content.encode("utf-8"))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.link(staging, self._target)
            finally:
                if staging is not None:
                    staging.unlink(missing_ok=True)
        print(f"로컬 미리보기: http://localhost:4000/previews/{self._name}/")
        return replace(publication, path=self._target)

    def discard(self, publication: Publication) -> None:
        # Shared immutable assets may belong to another preview; do not delete them.
        if publication.path != self._target:
            raise ValueError("이 미리보기의 게시물이 아닙니다.")
        self._target.unlink(missing_ok=True)


class JekyllPublisher:
    """Article을 Jekyll Markdown과 D2 SVG로 발행한다."""

    def __init__(
        self,
        *,
        d2_theme: int = 3,
        d2_sketch: bool = True,
        output_dir: Path | None = None,
        require_design: bool = False,
    ) -> None:
        self._output_dir = output_dir
        self._require_design = require_design
        flags = [f"--theme={d2_theme}"]
        if d2_sketch:
            flags.append("--sketch")
        flags.append("--pad=40")
        self._d2_flags = tuple(flags)

    def publish(self, article: Article) -> Publication:
        from generator.contracts import ModelGatewayError

        if self._require_design and (
            not article.presentation or not article.presentation.scenes
        ):
            raise ModelGatewayError("필수 시각화 없음 — 발행 보류")
        output = self._output_dir or post_writer.OUT_DIR
        design_dir = post_writer.ASSETS_DIR.parent / "generated/designs"
        previous_assets = set(design_dir.glob("*"))
        previous_assets.update(post_writer.ASSETS_DIR.glob("*"))
        assets = ()
        # Render/attach away from the live post tree; publish the completed file once.
        with tempfile.TemporaryDirectory(prefix="jekyll-publication-") as staging:
            path = post_writer.write_post(
                title=article.title,
                body=article.body,
                model=article.model,
                tags=list(article.tags),
                source_urls=list(article.source_urls),
                out_dir=Path(staging),
                assets_dir=Path(staging) / "diagrams",
                d2_flags=self._d2_flags,
            )
            has_diagram = "assets/diagrams" in path.read_text(encoding="utf-8")
            assets = self._attach_design(path, article) if article.presentation else ()
            if self._require_design and not assets:
                raise ModelGatewayError("필수 시각화 저장 실패 — 발행 보류")
            final = output / path.name
            temporary = None
            try:
                output.mkdir(parents=True, exist_ok=True)
                content = path.read_text(encoding="utf-8")
                for svg in (Path(staging) / "diagrams").glob("*.svg"):
                    digest = hashlib.sha256(svg.read_bytes()).hexdigest()[:16]
                    asset = post_writer.ASSETS_DIR / f"{svg.stem}-{digest}.svg"
                    assets = (*assets, asset)
                    asset.parent.mkdir(parents=True, exist_ok=True)
                    if not asset.exists():
                        asset.write_bytes(svg.read_bytes())
                    content = content.replace(
                        f"/assets/diagrams/{svg.name}", f"/assets/diagrams/{asset.name}"
                    )
                # A temp file on the destination filesystem makes replacement atomic.
                with tempfile.NamedTemporaryFile(
                    dir=output, prefix=".publish-", delete=False
                ) as handle:
                    temporary = Path(handle.name)
                    handle.write(content.encode("utf-8"))
                os.replace(temporary, final)
            except OSError:
                for asset in assets:
                    if asset not in previous_assets:
                        asset.unlink(missing_ok=True)
                raise
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return Publication(path=final, has_diagram=has_diagram, assets=assets)

    def _attach_design(self, path: Path, article: Article) -> tuple[Path, ...]:
        """본문 저장 후 선택적 시각화를 원자적으로 부착한다. 실패하면 기존 파일 유지."""
        from generator.design.scene_document import section_ends

        presentation = article.presentation
        assert presentation is not None
        original = path.read_text(encoding="utf-8")
        # Match actual normalized/rendered headings, not offsets from the model's draft.
        locations = section_ends(original)
        directory = post_writer.ASSETS_DIR.parent / "generated/designs"
        created = []
        assets = []
        temporary = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            additions = []
            for index, scene in enumerate(presentation.scenes, 1):
                if scene.after_heading not in locations:
                    raise ValueError("렌더링 후 디자인 배치 제목을 찾을 수 없음")
                digest = hashlib.sha256(scene.document.encode()).hexdigest()[:16]
                asset = directory / f"{path.stem}-{digest}-{index}.html"
                if not asset.exists():
                    created.append(asset)
                    asset.write_text(scene.document, encoding="utf-8")
                assets.append(asset)

                # Escape Liquid delimiters as well as HTML in model-provided captions.
                def safe(value):
                    return (
                        html.escape(value, quote=True)
                        .replace("{", "&#123;")
                        .replace("}", "&#125;")
                    )

                fragment = (
                    '\n\n{% raw %}\n<figure class="ai-scene">'
                    f"<figcaption>{safe(scene.title)} · 설명용 시각화</figcaption>"
                    f'<iframe class="ai-scene-frame" src="/assets/generated/designs/{asset.name}" '
                    f'title="{safe(scene.title)}" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe>'
                    f'<p class="ai-scene-summary">{safe(scene.caption)}</p>'
                    "</figure>\n{% endraw %}\n\n"
                )
                additions.append((locations[scene.after_heading], fragment))
            updated = original
            for position, fragment in sorted(additions, reverse=True):
                updated = updated[:position] + fragment + updated[position:]
            updated = updated.replace(
                "layout: post\n", "layout: post\ninteractive_design: true\n", 1
            )
            metadata = json.dumps(
                {
                    "summary": presentation.summary,
                    "model": presentation.model,
                    "post": path.name,
                    "assets": [asset.name for asset in assets],
                },
                ensure_ascii=False,
                indent=2,
            )
            digest = hashlib.sha256(metadata.encode()).hexdigest()[:16]
            manifest = directory / f"{path.stem}-{digest}-design.json"
            # Immutable metadata also preserves an older publication if attachment fails.
            if not manifest.exists():
                created.append(manifest)
                manifest.write_text(metadata, encoding="utf-8")
            assets.append(manifest)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=".design-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(updated)
            os.replace(temporary, path)
            return tuple(assets)
        except (OSError, ValueError) as exc:
            for asset in created:
                asset.unlink(missing_ok=True)
            print(f"  [디자인 저장 실패 → 기본 본문 유지] {exc}")
            return ()
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def discard(self, publication: Publication) -> None:
        """임시 게시물과 그 게시물에서 렌더링한 SVG를 제거한다."""
        path = publication.path
        path.unlink(missing_ok=True)
        for asset in publication.assets:
            asset.unlink(missing_ok=True)
