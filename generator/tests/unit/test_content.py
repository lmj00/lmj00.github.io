"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import json
import unittest

import generator.content.quality as quality
from generator.tests.fixtures.content import review_report


class ReviewJsonTest(unittest.TestCase):
    def test_accepts_valid_json_and_fenced_json(self) -> None:
        raw = json.dumps(review_report(), ensure_ascii=False)
        self.assertEqual(quality.parse_review_json(raw)["verdict"], "pass")
        self.assertEqual(
            quality.parse_review_json(f"```json\n{raw}\n```")["verdict"],
            "pass",
        )

    def test_low_core_score_forces_revision(self) -> None:
        issue = {
            "category": "readability",
            "severity": "minor",
            "description": "문단이 너무 길다.",
            "suggestion": "문단을 나눈다.",
        }
        report = review_report(issues=[issue])
        report["scores"]["readability"] = 3
        raw = json.dumps(report, ensure_ascii=False)
        self.assertEqual(quality.parse_review_json(raw)["verdict"], "revise")

    def test_low_score_requires_matching_issue(self) -> None:
        report = review_report(
            issues=[
                {
                    "category": "evidence",
                    "severity": "major",
                    "description": "근거가 부족하다.",
                    "suggestion": "근거 없는 문장을 제거한다.",
                }
            ]
        )
        report["scores"]["coherence"] = 3
        raw = json.dumps(report, ensure_ascii=False)
        with self.assertRaisesRegex(ValueError, "coherence"):
            quality.parse_review_json(raw)

    def test_revision_requires_actionable_issue(self) -> None:
        raw = json.dumps(review_report(verdict="revise"), ensure_ascii=False)
        with self.assertRaisesRegex(ValueError, "구체적인 issue"):
            quality.parse_review_json(raw)


class ArticleStructureTest(unittest.TestCase):
    def test_rejects_too_many_primary_sections(self) -> None:
        headings = ["### 개요"] + [f"### 항목 {i}" for i in range(1, 7)] + ["### 정리"]
        article = (
            "제목: 테스트\n\n> 한 줄 요약: 요약\n\n"
            + "\n\n내용입니다.\n\n".join(headings)
            + "\n\n마칩니다."
        )
        valid, reason = quality.output_has_required_structure(article)
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
        self.assertEqual(
            quality.output_has_required_structure(article),
            (True, "ok"),
        )
