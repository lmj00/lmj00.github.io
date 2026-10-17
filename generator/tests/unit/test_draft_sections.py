"""소제목 권장 개수는 초안을 폐기하지 않고 한 번의 정리 기회만 제공한다."""

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from generator.providers import openrouter as llm


def article(count):
    headings = ["개요", *(f"본문 {i}" for i in range(count - 2)), "정리"]
    return "제목: 테스트\n\n> 한 줄 요약: 테스트 요약이다.\n\n" + "\n\n".join(
        f"### {heading}\n\n" + "근거를 바탕으로 동작 원리를 설명한다. " * 20
        for heading in headings
    )


class DraftSectionRepairTest(unittest.TestCase):
    def run_generation(self, responses):
        with (
            mock.patch.object(llm, "_api_key", return_value="test-key"),
            mock.patch.object(llm, "_request_text", side_effect=responses) as request,
            redirect_stdout(io.StringIO()),
        ):
            result = llm.generate("system", "original sources", ["first", "fallback"])
        return result, request

    def test_target_or_fewer_sections_need_no_extra_request(self):
        for count in (3, 7):
            with self.subTest(count=count):
                original = article(count)
                result, request = self.run_generation([({}, original)])
                self.assertEqual(result, (original, "first"))
                request.assert_called_once()

    def test_extra_sections_are_repaired_once_with_original_source_context(self):
        original, revised = article(9), article(7)
        result, request = self.run_generation([({}, original), ({}, revised)])
        self.assertEqual(result, (revised, "first"))
        self.assertEqual(request.call_count, 2)
        payload = request.call_args.args[0]
        self.assertEqual(payload["model"], "first")
        self.assertEqual(payload["messages"][1]["content"], "original sources")
        self.assertEqual(payload["messages"][2], {"role": "assistant", "content": original})
        self.assertIn("개요·정리 포함 7개", payload["messages"][-1]["content"])

    def test_failed_or_invalid_repair_keeps_valid_original_without_fallback(self):
        original = article(9)
        cases = [
            llm._CompletionError("http_429", "HTTP 429"),
            ({}, ""),
            ({}, "제목: 짧음\n\n> 한 줄 요약: 요약\n\n### 개요\n\n### 정리\n끝이다."),
            ({}, article(7).replace("### 정리", "### 다른 제목")),
            ({}, article(7) + "あ"),
            ({}, article(7) + "\n미완성"),
            ({}, original),
            ({}, article(10)),
        ]
        for response in cases:
            with self.subTest(response=type(response).__name__):
                result, request = self.run_generation([({}, original), response])
                self.assertEqual(result, (original, "first"))
                self.assertEqual(request.call_count, 2)
                self.assertEqual(
                    [call.args[0]["model"] for call in request.call_args_list],
                    ["first", "first"],
                )

    def test_improved_but_over_target_draft_does_not_loop(self):
        result, request = self.run_generation([({}, article(9)), ({}, article(8))])
        self.assertEqual(result, (article(8), "first"))
        self.assertEqual(request.call_count, 2)

    def test_invalid_original_still_falls_back_without_section_repair(self):
        invalid = article(9).replace("### 개요", "### 다른 제목")
        result, request = self.run_generation([({}, invalid), ({}, article(7))])
        self.assertEqual(result, (article(7), "fallback"))
        self.assertEqual(
            [call.args[0]["model"] for call in request.call_args_list],
            ["first", "fallback"],
        )

    def test_repair_interrupt_is_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_generation([({}, article(9)), KeyboardInterrupt()])
