"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import generator.publishing.post_writer as post_writer
from generator.contracts import Article, ArticleScene, Presentation
from generator.design.scene_document import render_document
from generator.publishing.jekyll import JekyllPublisher
from generator.tests.fixtures.design import (
    DESIGN_BODY,
    design_article,
    design_candidate,
)


class DesignPublisherTest(unittest.TestCase):
    def test_d2_settings_belong_to_each_publisher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = JekyllPublisher(d2_theme=1, d2_sketch=False, output_dir=root / "a")
            second = JekyllPublisher(d2_theme=4, output_dir=root / "b")
            article = Article("diagram", "```d2\na -> b\n```", "writer", (), ())
            with (
                mock.patch.object(post_writer, "ASSETS_DIR", root / "assets/diagrams"),
                mock.patch.object(
                    post_writer.subprocess, "run", side_effect=FileNotFoundError
                ) as render,
            ):
                first.publish(article)
                second.publish(article)
                first.publish(article)
                post_writer.render_d2_blocks(
                    article.body, "default", root / "standalone"
                )
            flags = [call.args[0][1:-2] for call in render.call_args_list]
            self.assertEqual(
                flags,
                [
                    ["--theme=1", "--pad=40"],
                    ["--theme=4", "--sketch", "--pad=40"],
                    ["--theme=1", "--pad=40"],
                    list(post_writer.DEFAULT_D2_FLAGS),
                ],
            )

    def test_required_attachment_failure_preserves_existing_post(self):
        from generator.contracts import ModelGatewayError

        decorated = Article(
            "title",
            DESIGN_BODY,
            "writer",
            (),
            (),
            Presentation(
                (ArticleScene("missing", "title", "caption", "document"),),
                "summary",
                "designer",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(post_writer, "OUT_DIR", root / "posts"),
                mock.patch.object(post_writer, "ASSETS_DIR", root / "assets/diagrams"),
            ):
                first = JekyllPublisher().publish(
                    Article("title", DESIGN_BODY, "writer", (), ())
                )
                original = first.path.read_bytes()
                with self.assertRaises(ModelGatewayError):
                    JekyllPublisher(require_design=True).publish(decorated)
                self.assertEqual(first.path.read_bytes(), original)
                self.assertEqual(list((root / "posts").iterdir()), [first.path])

    def test_failed_final_write_preserves_old_diagram(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diagrams = root / "assets/diagrams"
            diagrams.mkdir(parents=True)
            old_svg = diagrams / "post-1.svg"
            old_svg.write_text("old SVG")
            posts = root / "posts"
            posts.mkdir()
            old_post = posts / "post.md"
            old_post.write_text("old post")

            def staged_write(**kwargs):
                self.assertNotEqual(kwargs["out_dir"], posts)
                kwargs["assets_dir"].mkdir()
                (kwargs["assets_dir"] / "post-1.svg").write_text("new SVG")
                output = kwargs["out_dir"] / "post.md"
                output.write_text("![diagram](/assets/diagrams/post-1.svg)")
                return output

            with (
                mock.patch.object(post_writer, "ASSETS_DIR", diagrams),
                mock.patch.object(post_writer, "write_post", side_effect=staged_write),
                mock.patch(
                    "generator.publishing.jekyll.os.replace",
                    side_effect=OSError("disk error"),
                ),
            ):
                with self.assertRaises(OSError):
                    JekyllPublisher(output_dir=posts).publish(design_article())
            self.assertEqual(old_post.read_text(), "old post")
            self.assertEqual(old_svg.read_text(), "old SVG")
            self.assertEqual(list(diagrams.iterdir()), [old_svg])
            self.assertEqual(list(posts.iterdir()), [old_post])

    def test_publish_assets_and_discard_only_owned_files(self):
        scene = design_candidate()["scenes"][0]
        decorated = Article(
            design_article().title,
            DESIGN_BODY,
            "writer",
            (),
            (),
            Presentation(
                (
                    ArticleScene(
                        scene["after_heading"],
                        scene["title"],
                        "{% endraw %} {{ site.title }}",
                        render_document(scene),
                    ),
                ),
                "design summary",
                "designer",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(post_writer, "OUT_DIR", root / "posts"),
                mock.patch.object(post_writer, "ASSETS_DIR", root / "assets/diagrams"),
            ):
                publisher = JekyllPublisher()
                publication = publisher.publish(decorated)
                content = publication.path.read_text()
                self.assertIn("interactive_design: true", content)
                self.assertIn('sandbox="allow-scripts"', content)
                self.assertNotIn("allow-same-origin", content)
                self.assertIn("&#123;% endraw %&#125;", content)
                self.assertEqual(len(publication.assets), 2)
                self.assertTrue(all(asset.exists() for asset in publication.assets))
                self.assertLess(content.index("<figure"), content.index("### 정리"))
                unrelated = root / "assets/generated/designs/other.html"
                unrelated.write_text("keep")
                publisher.discard(publication)
                self.assertFalse(publication.path.exists())
                self.assertTrue(all(not asset.exists() for asset in publication.assets))
                self.assertTrue(unrelated.exists())

    def test_asset_failure_keeps_plain_post(self):
        scene = ArticleScene("missing", "title", "caption", "document")
        decorated = Article(
            design_article().title,
            DESIGN_BODY,
            "writer",
            (),
            (),
            Presentation((scene,), "summary", "designer"),
        )
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.object(post_writer, "OUT_DIR", Path(directory) / "posts"),
                mock.patch.object(
                    post_writer, "ASSETS_DIR", Path(directory) / "assets/diagrams"
                ),
            ):
                publication = JekyllPublisher().publish(decorated)
                self.assertIn(DESIGN_BODY, publication.path.read_text())
                self.assertNotIn("interactive_design", publication.path.read_text())
                self.assertEqual(publication.assets, ())

    def test_post_replacement_failure_preserves_previous_assets(self):
        scene = design_candidate()["scenes"][0]
        decorated = Article(
            design_article().title,
            DESIGN_BODY,
            "writer",
            (),
            (),
            Presentation(
                (
                    ArticleScene(
                        scene["after_heading"],
                        scene["title"],
                        scene["caption"],
                        render_document(scene),
                    ),
                ),
                "first summary",
                "designer",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(post_writer, "OUT_DIR", root / "posts"),
                mock.patch.object(post_writer, "ASSETS_DIR", root / "assets/diagrams"),
            ):
                publisher = JekyllPublisher()
                first = publisher.publish(decorated)
                previous_post = first.path.read_bytes()
                previous = {asset: asset.read_bytes() for asset in first.assets}
                from dataclasses import replace

                second = replace(
                    decorated,
                    presentation=replace(
                        decorated.presentation, summary="second summary"
                    ),
                )
                with mock.patch(
                    "generator.publishing.jekyll.os.replace",
                    side_effect=OSError("disk error"),
                ):
                    with self.assertRaises(OSError):
                        publisher.publish(second)
                self.assertEqual(first.path.read_bytes(), previous_post)
                self.assertEqual(
                    previous, {asset: asset.read_bytes() for asset in previous}
                )
                self.assertEqual(
                    set(previous), set((root / "assets/generated/designs").iterdir())
                )
                self.assertEqual(list((root / "posts").glob(".design-*.tmp")), [])
