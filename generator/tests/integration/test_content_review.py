"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import generator.content.quality as quality
import generator.content.review_pipeline as review_pipeline
import generator.main as main
import generator.sources.source_context as source_context
from generator.tests.fixtures.content import review_report


class ReviewPromptAndArtifactsTest(unittest.TestCase):
    def test_writer_is_excluded_from_review_models_when_possible(self) -> None:
        models = ["qwen", "luna"]
        self.assertEqual(
            review_pipeline.independent_review_models(models, "qwen"),
            ["luna"],
        )
        self.assertEqual(
            review_pipeline.independent_review_models(["qwen"], "qwen"),
            ["qwen"],
        )

    def test_source_quality_rejects_short_index_like_evidence(self) -> None:
        # 총 길이는 충분해도 짧은 링크 제목만 반복되는 색인형 문서는 제외한다.
        thin = [{"ok": True, "text": "짧은 링크 제목\n" * 400}]
        self.assertFalse(quality.source_quality(thin, 2500, 1200)[0])

        rich = [{"ok": True, "text": ("충분히 구체적인 설명 문장 " * 8 + "\n") * 30}]
        self.assertTrue(quality.source_quality(rich, 2500, 1200)[0])

    def test_review_and_revision_prompts_remain_valid_xml(self) -> None:
        fetched = [
            {
                "ok": True,
                "fetch": "https://example.com/a?x=1&y=2",
                "cite": "https://example.com/a?x=1&y=2",
                "text": "원문 <태그> & 값 ]]> 다음",
            }
        ]
        sources, _ = source_context.build_sources_block(fetched)
        draft = source_context.as_cdata("제목: 테스트\n\n본문 ]]> 다음")
        report = source_context.as_cdata(
            json.dumps(review_report(), ensure_ascii=False)
        )

        review_template = main.load_prompt("review_template.md")
        revision_template = main.load_prompt("revision_template.md")
        ET.fromstring(
            review_template.format(
                sources_block=sources,
                draft_article=draft,
            )
        )
        ET.fromstring(
            revision_template.format(
                sources_block=sources,
                draft_article=draft,
                review_report=report,
            )
        )

    def test_comparison_artifacts_are_written_only_when_requested(self) -> None:
        report = review_report()
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                os.environ,
                {"REVIEW_ARTIFACT_DIR": temp_dir},
            ):
                review_pipeline.save_review_artifacts(
                    Path(temp_dir),
                    "topic::sample",
                    "<document />",
                    "제목: 전",
                    report,
                    "제목: 후",
                    report,
                    [report, report],
                )
            run_dirs = list(Path(temp_dir).iterdir())
            self.assertEqual(len(run_dirs), 1)
            names = {path.name for path in run_dirs[0].iterdir()}
            self.assertEqual(
                names,
                {
                    "source-documents.xml",
                    "before.md",
                    "review.json",
                    "final-review.json",
                    "review-history.json",
                    "after.md",
                    "changes.diff",
                },
            )
            self.assertIn("제목: 후", (run_dirs[0] / "after.md").read_text())
