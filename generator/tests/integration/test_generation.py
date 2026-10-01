"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import generator.content.review_pipeline as review_pipeline
import generator.main as main
import generator.pipeline as generator_pipeline
import generator.publishing.post_writer as post_writer
import generator.sources.topics as topics
from generator.content.review_pipeline import ReviewRejectedError
from generator.contracts import (
    Article,
    GeneratedText,
    ModelGatewayError,
    Publication,
    ReviewResult,
    SourceBundle,
)
from generator.design.design_pipeline import ArticleDesignPipeline
from generator.design.visual_contracts import source_sections, validate_review
from generator.paths import GENERATOR_DIR
from generator.pipeline import GeneratorPipeline
from generator.publishing.jekyll import JekyllPreviewPublisher
from generator.tests.fixtures.content import review_report
from generator.tests.fixtures.design import DESIGN_BODY, design_article


class PipelineDesignOrderingTest(unittest.TestCase):
    def build(self, review_enabled=True):
        models, publisher, topics, sources, designer = [mock.Mock() for _ in range(5)]
        topics.select.return_value = {
            "id": "test-topic",
            "title_hint": "확인 설명",
            "tags": [],
        }
        sources.fetch.return_value = SourceBundle(
            [{"ok": True, "text": DESIGN_BODY}],
            "official source",
            ("https://example.com",),
            "확인 설명",
        )
        publication = Publication(Path("/tmp/design-ordering-post.md"), False)
        publisher.publish.return_value = publication
        app = GeneratorPipeline(
            cfg={
                "user_agent": "test",
                "review_enabled": review_enabled,
                "design_enabled": True,
            },
            prompt_loader=lambda _: "prompt",
            model_gateway=models,
            publisher=publisher,
            topic_repository=topics,
            source_gateway=sources,
            generator_dir=Path("/tmp/generator"),
            design_pipeline=designer,
        )
        app._generate_draft = mock.Mock(return_value=design_article())
        app._review = mock.Mock()
        app._review.run.return_value = design_article()
        designer.enhance.return_value = design_article()
        return app, publisher, topics, designer

    def test_design_only_receives_reviewed_content(self):
        app, _, topics, designer = self.build()
        revised = Article("검수 수정본", DESIGN_BODY + "\n검수 반영", "writer", (), ())
        app._review.run.return_value = revised
        designer.enhance.return_value = revised
        self.assertEqual(app.run(), 0)
        self.assertEqual(designer.enhance.call_args.args[0], revised)
        topics.mark_done.assert_called_once_with("test-topic")

    def test_failed_content_review_never_runs_design_or_marks_done(self):
        app, publisher, topics, designer = self.build()
        app._review.run.side_effect = ReviewRejectedError("content rejected")
        self.assertEqual(app.run(), 1)
        designer.enhance.assert_not_called()
        topics.mark_done.assert_not_called()
        publisher.publish.assert_not_called()
        publisher.discard.assert_not_called()

    def test_no_design_without_content_review(self):
        app, _, _, designer = self.build(review_enabled=False)
        self.assertEqual(app.run(), 0)
        designer.enhance.assert_not_called()

    def test_required_design_failure_never_publishes_or_marks_done(self):
        app, publisher, topics, _ = self.build()
        app._cfg["design_required"] = True
        self.assertEqual(app.run(), 1)
        publisher.publish.assert_not_called()
        topics.mark_done.assert_not_called()

    def test_publish_happens_only_after_review_and_design(self):
        app, publisher, _, designer = self.build()
        events = []
        app._review.run.side_effect = lambda *args, **kwargs: (
            events.append("review") or design_article()
        )
        designer.enhance.side_effect = lambda *args: (
            events.append("design") or design_article()
        )
        publisher.publish.side_effect = lambda *args: (
            events.append("publish") or Publication(Path("/tmp/order.md"), False)
        )
        self.assertEqual(app.run(), 0)
        self.assertEqual(events, ["review", "design", "publish"])


class GeneralAutomationTest(unittest.TestCase):
    def test_cli_preview_uses_same_pipeline_and_read_only_completion_state(self):
        with (
            mock.patch.object(main, "load_dotenv"),
            mock.patch.object(
                main, "load_config", return_value={"design_required": True}
            ),
            mock.patch.object(main, "JekyllPreviewPublisher") as preview,
            mock.patch.object(main, "JekyllPublisher") as production,
            mock.patch.object(main, "GeneratorPipeline") as pipeline,
        ):
            pipeline.return_value.run.return_value = 0
            self.assertEqual(
                main.main(
                    ["--local-preview", "local-test", "--topic-id", "kubernetes::pod"]
                ),
                0,
            )
            self.assertIs(pipeline.call_args.kwargs["publisher"], preview.return_value)
            repository = pipeline.call_args.kwargs["topic_repository"]
            with mock.patch.object(topics.dedup, "mark_done") as mark_done:
                repository.mark_done("kubernetes::pod")
                mark_done.assert_not_called()
            production.assert_not_called()
            pipeline.return_value.run.assert_called_once_with("kubernetes::pod")

    def test_three_topics_use_same_pipeline_and_do_not_mark_done_or_write_posts(self):
        for name, title, animated in [
            ("websocket", "WebSocket 연결 과정", True),
            ("postgresql", "트랜잭션 상태 비교", False),
            ("kubernetes", "Pod 상태 변화", True),
        ]:
            with self.subTest(topic=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                body = f"### 개요\n\n{title}를 살펴본다.\n\n### 핵심 동작\n\n공식문서 근거 설명이다.\n\n### 정리\n\n가정을 확인한다."
                source = f"<document><source_url>https://example.com/{name}</source_url><document_content>{body}</document_content></document>"
                states = [
                    {
                        "id": "start",
                        "html": f'<div class="board"><p data-entity="subject">{title}</p></div>',
                        "description": "설명용 초기 상태",
                        "actions": [],
                    }
                ]
                if animated:
                    states[0]["actions"] = [{"label": "다음 상태", "target": "next"}]
                    states.append(
                        {
                            "id": "next",
                            "html": '<div class="board"><p data-entity="subject">다음 단계의 상태</p></div>',
                            "description": "설명용 다음 상태",
                            "actions": [],
                        }
                    )
                candidate = {
                    "summary": title,
                    "scenes": [
                        {
                            "title": title,
                            "after_heading": "핵심 동작",
                            "caption": "설명용 가정",
                            "explanation": {
                                "mode": "interactive" if animated else "static",
                                "learning_goal": title,
                                "reader_action": "다음 상태를 확인"
                                if animated
                                else "상태 비교",
                                "observable_change": "공식문서 근거 설명",
                                "takeaway": "가정을 확인한다.",
                                "assumptions": ["설명용 가정"],
                                "key_entities": ["subject"],
                                "evidence": [
                                    {
                                        "source_url": f"https://example.com/{name}",
                                        "quote": title,
                                    }
                                ],
                            },
                            "css": ".scene-content .board {color:#d6dae0;min-height:80px}",
                            "initial": "start",
                            "states": states,
                            "playback": {
                                "steps": ["start", "next"] if animated else [],
                                "interval_ms": 3000,
                            },
                        }
                    ],
                }
                models, verifier, sources = mock.Mock(), mock.Mock(), mock.Mock()
                verifier.check.return_value = {"passed": True}
                models.generate.return_value = GeneratedText(
                    f"제목: {title}\n\n{body}", "writer"
                )
                models.review.return_value = ReviewResult(
                    {
                        "verdict": "pass",
                        "scores": {
                            key: 5
                            for key in (
                                "grounding",
                                "coverage",
                                "coherence",
                                "readability",
                                "visual_clarity",
                            )
                        },
                        "issues": [],
                    },
                    "reviewer",
                )
                models.complete_json.side_effect = [
                    GeneratedText(json.dumps(candidate), "designer"),
                    GeneratedText(
                        '{"verdict":"pass","issues":[],"previous_issues":[]}',
                        "reviewer",
                    ),
                ]
                sources.fetch.return_value = SourceBundle(
                    [{"ok": True, "text": body}],
                    source,
                    (f"https://example.com/{name}",),
                    title,
                )
                repository = topics.CatalogTopicRepository(record_done=False)
                cfg = {
                    "user_agent": "test",
                    "model_fallback": ["writer"],
                    "review_enabled": True,
                    "review_model_fallback": ["reviewer"],
                    "design_enabled": True,
                    "design_required": True,
                    "design_model_fallback": ["designer"],
                    "design_review_model_fallback": ["reviewer"],
                }
                designer = ArticleDesignPipeline(
                    models, main.load_prompt, verifier, base_dir=root / "generator"
                )
                with (
                    mock.patch.object(
                        topics,
                        "select_topic",
                        return_value={"id": name, "title_hint": title, "tags": [name]},
                    ),
                    mock.patch.object(topics.dedup, "mark_done") as mark_done,
                    mock.patch.object(
                        post_writer, "ASSETS_DIR", root / "assets/diagrams"
                    ),
                    mock.patch.object(post_writer, "OUT_DIR", root / "_posts"),
                ):
                    publisher = JekyllPreviewPublisher(
                        name, root=root, require_design=True
                    )
                    app = GeneratorPipeline(
                        cfg=cfg,
                        prompt_loader=main.load_prompt,
                        model_gateway=models,
                        publisher=publisher,
                        topic_repository=repository,
                        source_gateway=sources,
                        generator_dir=root / "generator",
                        design_pipeline=designer,
                    )
                    self.assertEqual(app.run(), 0)
                    mark_done.assert_not_called()
                self.assertFalse((root / "_posts").exists())
                page = (root / "previews" / f"{name}.md").read_text()
                self.assertIn(f"permalink: /previews/{name}/", page)
                self.assertIn('sandbox="allow-scripts"', page)
                self.assertIn("### 핵심 동작", page)
                request = json.loads(models.complete_json.call_args_list[0].args[1])
                self.assertEqual(request["article_title"], title)
                self.assertEqual(request["tags"], [name])
                self.assertNotIn("rabbitmq", json.dumps(request).lower())
                self.assertIsNotNone(
                    models.complete_json.call_args_list[0].kwargs["response_schema"]
                )
                self.assertEqual(
                    models.complete_json.call_args_list[0].kwargs["format_retries"], 1
                )
                self.assertEqual(verifier.check.call_count, 1)
                models.review.assert_called_once()

    def test_required_preflight_failure_makes_no_paid_calls(self):
        models, publisher, repository, sources, designer = [
            mock.Mock() for _ in range(5)
        ]
        designer.preflight.side_effect = ModelGatewayError("no browser")
        app = GeneratorPipeline(
            cfg={
                "design_required": True,
                "design_enabled": True,
                "review_enabled": True,
            },
            prompt_loader=main.load_prompt,
            model_gateway=models,
            publisher=publisher,
            topic_repository=repository,
            source_gateway=sources,
            generator_dir=Path("/tmp"),
            design_pipeline=designer,
        )
        self.assertEqual(app.run(), 1)
        models.generate.assert_not_called()
        repository.select.assert_not_called()
        publisher.publish.assert_not_called()

    def test_existing_preview_of_either_extension_blocks_before_generation(self):
        for suffix in ("md", "html"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "previews").mkdir()
                target = root / "previews" / f"keep.{suffix}"
                target.write_text("keep")
                with self.assertRaises(FileExistsError):
                    JekyllPreviewPublisher("keep", root=root)
                self.assertEqual(target.read_text(), "keep")

    def test_forced_catalog_topic_can_be_reused_without_random_selection(self):
        topic = {"id": "postgresql::transaction-iso", "title_hint": "트랜잭션"}
        with (
            mock.patch.object(topics.dedup, "pick_next_topic", return_value=None),
            mock.patch.object(topics.catalog, "build_pool", return_value=[topic]),
            mock.patch.object(topics, "pick_balanced") as random_pick,
        ):
            self.assertEqual(
                topics.select_topic({"topics": [], "catalogs": []}, topic["id"]), topic
            )
            self.assertIsNone(
                topics.select_topic({"topics": [], "catalogs": []}, "missing")
            )
            random_pick.assert_not_called()

    def test_source_index_preserves_multiple_documents_with_same_citation_url(self):
        sources = "".join(
            f"<document><source_url>https://example.com/docs</source_url><document_content>{text}</document_content></document>"
            for text in ("first evidence", "second evidence")
        )
        sections = source_sections(sources)
        self.assertEqual(len(sections), 2)
        report = {
            "verdict": "revise",
            "issues": [
                {
                    "id": "I1",
                    "target": "content",
                    "path": "/candidate/caption",
                    "kind": "factual",
                    "problem": "잘못된 주장",
                    "suggestion": "근거 범위로 축소",
                    "source_url": "https://example.com/docs",
                    "source_quote": "first evidence",
                }
            ],
            "previous_issues": [],
        }
        validate_review(
            json.dumps(report),
            candidate={"caption": "주장"},
            inputs={"current_official_sections": sections},
        )


class MainReviewFlowTest(unittest.TestCase):
    def test_thin_source_is_skipped_before_generation(self) -> None:
        cfg = {
            "user_agent": "test",
            "max_chars_per_source": 16000,
            "min_total_source_chars": 2000,
            "min_substantive_source_chars": 1200,
            "model_selection": "manual",
            "model_fallback": ["writer"],
            "topics": [],
        }
        topic = {
            "id": "thin-topic",
            "title_hint": "얕은 문서",
            "tags": [],
            "sources": ["https://example.com"],
        }
        fetched = [
            {
                "ok": True,
                "fetch": "https://example.com",
                "cite": "https://example.com",
                "text": "링크 제목\n" * 100,
                "reason": "ok",
            }
        ]
        model_gateway = mock.Mock()
        publisher = mock.Mock()
        topic_repository = mock.Mock()
        topic_repository.select.return_value = topic
        source_gateway = mock.Mock()
        source_gateway.fetch.return_value = SourceBundle(
            documents=fetched,
            prompt_context="<document />",
            cite_urls=("https://example.com",),
            title_hint="얕은 문서",
        )
        app = generator_pipeline.GeneratorPipeline(
            cfg=cfg,
            prompt_loader=lambda _: "unused",
            model_gateway=model_gateway,
            publisher=publisher,
            topic_repository=topic_repository,
            source_gateway=source_gateway,
            generator_dir=GENERATOR_DIR,
        )
        self.assertEqual(app.run(), 0)

        topic_repository.mark_done.assert_called_once_with("thin-topic")
        model_gateway.generate.assert_not_called()
        publisher.publish.assert_not_called()

    def test_failed_revision_gets_one_more_round_before_publish(self) -> None:
        issue = {
            "category": "readability",
            "severity": "major",
            "description": "핵심 설명이 반복된다.",
            "suggestion": "중복 문단을 합친다.",
        }
        report = review_report(verdict="revise", issues=[issue])
        report["scores"]["readability"] = 3
        cfg = {
            "user_agent": "test",
            "max_chars_per_source": 16000,
            "model_selection": "manual",
            "model_fallback": ["writer"],
            "diagram_retry_tags": [],
            "review_enabled": True,
            "review_model_fallback": ["reviewer"],
            "review_max_tokens": 4000,
            "review_reasoning_tokens": 1200,
            "review_recheck_revised": True,
            "review_max_revision_rounds": 2,
            "topics": [],
        }
        topic = {
            "id": "topic-id",
            "title_hint": "테스트 주제",
            "tags": ["test"],
            "sources": ["https://example.com"],
        }
        fetched = [
            {
                "ok": True,
                "fetch": "https://example.com",
                "cite": "https://example.com",
                "text": "공식문서",
                "reason": "ok",
            }
        ]

        def prompt(name: str) -> str:
            if name == "user_template.md":
                return "{title_hint}\n{tags}\n{sources_block}"
            if name == "review_template.md":
                return "{sources_block}\n{draft_article}"
            if name == "revision_template.md":
                return "{sources_block}\n{draft_article}\n{review_report}"
            return "system"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "post.md"

            def publish(article) -> Publication:
                output.write_text(article.body, encoding="utf-8")
                return Publication(path=output, has_diagram=False)

            generated = [
                GeneratedText(
                    "제목: 초안\n\n> 한 줄 요약: 초안\n\n"
                    "### 개요\n초안\n\n### 정리\n초안",
                    "writer",
                ),
                GeneratedText(
                    "제목: 1차 수정본\n\n> 한 줄 요약: 수정\n\n"
                    "### 개요\n수정\n\n### 정리\n수정",
                    "writer",
                ),
                GeneratedText(
                    "제목: 2차 수정본\n\n> 한 줄 요약: 수정\n\n"
                    "### 개요\n최종\n\n### 정리\n최종",
                    "writer",
                ),
            ]
            model_gateway = mock.Mock()
            model_gateway.generate.side_effect = generated
            model_gateway.review.side_effect = [
                ReviewResult(report, "reviewer"),
                ReviewResult(report, "reviewer"),
                ReviewResult(review_report(), "reviewer"),
            ]
            publisher = mock.Mock()
            publisher.publish.side_effect = publish
            publisher.discard.side_effect = lambda publication: publication.path.unlink(
                missing_ok=True
            )
            topic_repository = mock.Mock()
            topic_repository.select.return_value = topic
            source_gateway = mock.Mock()
            source_gateway.fetch.return_value = SourceBundle(
                documents=fetched,
                prompt_context="<document />",
                cite_urls=("https://example.com",),
                title_hint="테스트 주제",
            )
            app = generator_pipeline.GeneratorPipeline(
                cfg=cfg,
                prompt_loader=prompt,
                model_gateway=model_gateway,
                publisher=publisher,
                topic_repository=topic_repository,
                source_gateway=source_gateway,
                generator_dir=root / "generator",
            )
            with mock.patch.object(
                review_pipeline,
                "save_review_artifacts",
            ):
                self.assertEqual(app.run(), 0)

            self.assertEqual(model_gateway.generate.call_count, 3)
            self.assertEqual(model_gateway.review.call_count, 3)
            self.assertEqual(publisher.publish.call_count, 1)
            publisher.discard.assert_not_called()
            topic_repository.mark_done.assert_called_once_with("topic-id")
            self.assertIn("### 개요\n최종", output.read_text(encoding="utf-8"))
