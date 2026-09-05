from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

GENERATOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATOR_DIR))

import llm  # noqa: E402
import main  # noqa: E402


def _report(*, verdict: str = "pass", score: int = 5,
            issues: list[dict] | None = None) -> dict:
    return {
        "verdict": verdict,
        "scores": {
            "grounding": score,
            "coverage": score,
            "coherence": score,
            "readability": score,
            "visual_clarity": score,
        },
        "issues": issues or [],
    }


class ReviewJsonTest(unittest.TestCase):
    def test_accepts_valid_json_and_fenced_json(self) -> None:
        raw = json.dumps(_report(), ensure_ascii=False)
        self.assertEqual(llm._parse_review_json(raw)["verdict"], "pass")
        self.assertEqual(
            llm._parse_review_json(f"```json\n{raw}\n```")["verdict"],
            "pass",
        )

    def test_low_core_score_forces_revision(self) -> None:
        issue = {
            "category": "readability",
            "severity": "minor",
            "description": "문단이 너무 길다.",
            "suggestion": "문단을 나눈다.",
        }
        report = _report(issues=[issue])
        report["scores"]["readability"] = 3
        raw = json.dumps(report, ensure_ascii=False)
        self.assertEqual(llm._parse_review_json(raw)["verdict"], "revise")

    def test_low_score_requires_matching_issue(self) -> None:
        report = _report(issues=[{
            "category": "evidence",
            "severity": "major",
            "description": "근거가 부족하다.",
            "suggestion": "근거 없는 문장을 제거한다.",
        }])
        report["scores"]["coherence"] = 3
        raw = json.dumps(report, ensure_ascii=False)
        with self.assertRaisesRegex(ValueError, "coherence"):
            llm._parse_review_json(raw)

    def test_revision_requires_actionable_issue(self) -> None:
        raw = json.dumps(_report(verdict="revise"), ensure_ascii=False)
        with self.assertRaisesRegex(ValueError, "구체적인 issue"):
            llm._parse_review_json(raw)


class ArticleStructureTest(unittest.TestCase):
    def test_rejects_too_many_primary_sections(self) -> None:
        headings = ["### 개요"] + [f"### 항목 {i}" for i in range(1, 7)] + ["### 정리"]
        article = (
            "제목: 테스트\n\n> 한 줄 요약: 요약\n\n"
            + "\n\n내용입니다.\n\n".join(headings)
            + "\n\n마칩니다."
        )
        valid, reason = llm.output_has_required_structure(article)
        self.assertFalse(valid)
        self.assertIn("1차 섹션 과다", reason)

    def test_accepts_compact_primary_section_structure(self) -> None:
        article = """제목: 테스트

> 한 줄 요약: 요약

### 개요

내용이다.

### 핵심 동작

내용이다.

### 주의점

내용이다.

### 정리

마칩니다."""
        self.assertEqual(llm.output_has_required_structure(article), (True, "ok"))


class ReviewApiTest(unittest.TestCase):
    def test_falls_back_and_sends_structured_low_reasoning_request(self) -> None:
        good_report = json.dumps(_report(), ensure_ascii=False)
        failed = mock.Mock(status_code=500, text="provider error")
        succeeded = mock.Mock(status_code=200, text="")
        succeeded.json.return_value = {
            "choices": [{"message": {"content": good_report}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "cost": 0.0001,
            },
        }
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", side_effect=[failed, succeeded]) as post,
        ):
            report, model = llm.review("system", "user", ["first", "second"])

        self.assertEqual(model, "second")
        self.assertEqual(report["verdict"], "pass")
        payload = post.call_args_list[1].kwargs["json"]
        self.assertEqual(payload["max_tokens"], 4000)
        self.assertEqual(payload["reasoning"]["max_tokens"], 1200)
        self.assertEqual(payload["response_format"]["type"], "json_schema")

    def test_empty_structured_output_falls_back(self) -> None:
        empty = mock.Mock(status_code=200, text="")
        empty.json.return_value = {
            "choices": [{"message": {"content": None}}],
            "usage": {"completion_tokens": 1200},
        }
        good = mock.Mock(status_code=200, text="")
        good.json.return_value = {
            "choices": [{"message": {"content": json.dumps(_report())}}],
        }
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", side_effect=[empty, good]),
        ):
            _, model = llm.review("system", "user", ["first", "second"])
        self.assertEqual(model, "second")


class ReviewPromptAndArtifactsTest(unittest.TestCase):
    def test_writer_is_excluded_from_review_models_when_possible(self) -> None:
        models = ["qwen", "luna"]
        self.assertEqual(main._independent_review_models(models, "qwen"), ["luna"])
        self.assertEqual(main._independent_review_models(["qwen"], "qwen"), ["qwen"])

    def test_source_quality_rejects_short_index_like_evidence(self) -> None:
        # 총 길이는 충분해도 짧은 링크 제목만 반복되는 색인형 문서는 제외한다.
        thin = [{"ok": True, "text": "짧은 링크 제목\n" * 400}]
        self.assertFalse(main.source_quality(thin, 2500, 1200)[0])

        rich = [{"ok": True, "text": ("충분히 구체적인 설명 문장 " * 8 + "\n") * 30}]
        self.assertTrue(main.source_quality(rich, 2500, 1200)[0])

    def test_review_and_revision_prompts_remain_valid_xml(self) -> None:
        fetched = [{
            "ok": True,
            "fetch": "https://example.com/a?x=1&y=2",
            "cite": "https://example.com/a?x=1&y=2",
            "text": "원문 <태그> & 값 ]]> 다음",
        }]
        sources, _ = main.build_sources_block(fetched)
        draft = main._as_cdata("제목: 테스트\n\n본문 ]]> 다음")
        report = main._as_cdata(json.dumps(_report(), ensure_ascii=False))

        review_template = main.load_prompt("review_template.md")
        revision_template = main.load_prompt("revision_template.md")
        ET.fromstring(review_template.format(
            sources_block=sources,
            draft_article=draft,
        ))
        ET.fromstring(revision_template.format(
            sources_block=sources,
            draft_article=draft,
            review_report=report,
        ))

    def test_comparison_artifacts_are_written_only_when_requested(self) -> None:
        report = _report()
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                os.environ,
                {"REVIEW_ARTIFACT_DIR": temp_dir},
            ):
                main._save_review_artifacts(
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
            self.assertEqual(names, {
                "source-documents.xml",
                "before.md",
                "review.json",
                "final-review.json",
                "review-history.json",
                "after.md",
                "changes.diff",
            })
            self.assertIn("제목: 후", (run_dirs[0] / "after.md").read_text())


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
        fetched = [{
            "ok": True,
            "fetch": "https://example.com",
            "cite": "https://example.com",
            "text": "링크 제목\n" * 100,
            "reason": "ok",
        }]
        with (
            mock.patch.object(main, "load_dotenv"),
            mock.patch.object(main, "load_config", return_value=cfg),
            mock.patch.object(main.dedup, "pick_next_topic", return_value=topic),
            mock.patch.object(main.dedup, "mark_done") as mark_done,
            mock.patch.object(main.fetcher, "fetch_topic_sources", return_value=fetched),
            mock.patch.object(main.llm, "generate") as generate,
        ):
            self.assertEqual(main.main(), 0)

        mark_done.assert_called_once_with("thin-topic")
        generate.assert_not_called()

    def test_failed_revision_gets_one_more_round_before_publish(self) -> None:
        issue = {
            "category": "readability",
            "severity": "major",
            "description": "핵심 설명이 반복된다.",
            "suggestion": "중복 문단을 합친다.",
        }
        report = _report(verdict="revise", issues=[issue])
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
        fetched = [{
            "ok": True,
            "fetch": "https://example.com",
            "cite": "https://example.com",
            "text": "공식문서",
            "reason": "ok",
        }]

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

            def write_post(**kwargs) -> Path:
                output.write_text(kwargs["body"], encoding="utf-8")
                return output

            generated = [
                ("제목: 초안\n\n> 한 줄 요약: 초안\n\n### 개요\n초안\n\n### 정리\n초안", "writer"),
                ("제목: 1차 수정본\n\n> 한 줄 요약: 수정\n\n### 개요\n수정\n\n### 정리\n수정", "writer"),
                ("제목: 2차 수정본\n\n> 한 줄 요약: 수정\n\n### 개요\n최종\n\n### 정리\n최종", "writer"),
            ]
            with (
                mock.patch.object(main, "HERE", root / "generator"),
                mock.patch.object(main, "load_dotenv"),
                mock.patch.object(main, "load_config", return_value=cfg),
                mock.patch.object(main, "load_prompt", side_effect=prompt),
                mock.patch.object(main.dedup, "pick_next_topic", return_value=topic),
                mock.patch.object(main.dedup, "mark_done") as mark_done,
                mock.patch.object(main.fetcher, "fetch_topic_sources", return_value=fetched),
                mock.patch.object(main.llm, "generate", side_effect=generated) as generate,
                mock.patch.object(
                    main.llm,
                    "review",
                    side_effect=[
                        (report, "reviewer"),
                        (report, "reviewer"),
                        (_report(), "reviewer"),
                    ],
                ) as review,
                mock.patch.object(main.post_writer, "write_post", side_effect=write_post),
                mock.patch.object(main, "_save_review_artifacts"),
            ):
                self.assertEqual(main.main(), 0)

            self.assertEqual(generate.call_count, 3)
            self.assertEqual(review.call_count, 3)
            mark_done.assert_called_once_with("topic-id")
            self.assertIn("### 개요\n최종", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
