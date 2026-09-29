"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import io
import os
import unittest
from contextlib import ExitStack, redirect_stdout
from threading import Thread
from unittest import mock

import generator.providers.openrouter as llm
import generator.providers.request_progress as progress
import generator.sources.difficulty as difficulty


class RequestProgressTest(unittest.TestCase):
    def test_long_request_is_observed_without_cancelling_or_repeating_it(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "본문" * 2000}}]
        }
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(
                mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-key"})
            )
            stack.enter_context(
                mock.patch.object(
                    llm, "output_is_clean_korean", return_value=(True, "ok")
                )
            )
            stack.enter_context(
                mock.patch.object(
                    llm, "output_has_required_structure", return_value=(True, "ok")
                )
            )
            stack.enter_context(
                mock.patch.object(llm, "looks_truncated", return_value=False)
            )
            post = stack.enter_context(
                mock.patch.object(llm.requests, "post", return_value=response)
            )
            clock = stack.enter_context(
                mock.patch.object(progress, "monotonic", side_effect=[0, 960, 961])
            )
            stopped = stack.enter_context(
                mock.patch.object(progress, "Event")
            ).return_value
            stopped.wait.side_effect = [False, True]
            thread = stack.enter_context(mock.patch.object(progress, "Thread"))
            # 16분의 대기를 실제로 기다리지 않고 주기 로그 한 번으로 재현한다.
            thread.return_value.start.side_effect = lambda: thread.call_args.kwargs[
                "target"
            ]()
            _, model = llm.generate(
                "private-system",
                "private-user",
                ["first", "second"],
                purpose="초안 생성",
            )

        self.assertEqual(model, "first")
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["timeout"], (10, 300))
        self.assertNotIn("stream", post.call_args.kwargs)
        self.assertEqual(clock.call_count, 3)
        stopped.wait.assert_has_calls([mock.call(30), mock.call(30)])
        stopped.set.assert_called_once()
        thread.return_value.join.assert_called_once()
        log = output.getvalue()
        self.assertIn("[응답 대기] 초안 생성 / first: 16분 00초", log)
        self.assertIn("응답 수신 완료, 961.0초", log)
        for private in ["secret-key", "private-system", "private-user"]:
            self.assertNotIn(private, log)

    def test_real_reporter_stops_on_success_failure_and_interrupt(self):
        for error in [
            None,
            llm.requests.ReadTimeout("private-error"),
            KeyboardInterrupt(),
        ]:
            with (
                self.subTest(error=type(error).__name__),
                mock.patch.object(progress, "Thread") as factory,
            ):
                created = []

                def create(**kwargs):
                    thread = Thread(**kwargs)
                    created.append(thread)
                    return thread

                factory.side_effect = create
                output = io.StringIO()
                with redirect_stdout(output):
                    if error is None:
                        with progress.request_progress("model", "초안 생성"):
                            pass
                    else:
                        with self.assertRaises(type(error)) as raised:
                            with progress.request_progress("model", "초안 생성"):
                                raise error
                        self.assertIs(raised.exception, error)
                self.assertEqual(len(created), 1)
                self.assertFalse(created[0].is_alive())
                self.assertNotIn("private-error", output.getvalue())
                expected = (
                    "응답 수신 완료"
                    if error is None
                    else "로컬 실행 중단"
                    if isinstance(error, KeyboardInterrupt)
                    else "요청 실패 (ReadTimeout)"
                )
                self.assertIn(expected, output.getvalue())


class DraftProgressTest(unittest.TestCase):
    def test_failure_is_logged_before_next_model_starts(self):
        null = mock.Mock(status_code=200)
        null.json.return_value = {"choices": [{"message": {"content": None}}]}
        empty = mock.Mock(status_code=200)
        empty.json.return_value = {"choices": [{"message": {"content": ""}}]}
        for failed, reason in [
            (mock.Mock(status_code=429, text="provider rate limit"), "HTTP 429"),
            (llm.requests.ReadTimeout("timeout"), "ReadTimeout"),
            (null, "응답 본문 오류"),
            (empty, "빈 응답"),
        ]:
            with self.subTest(reason=reason), ExitStack() as stack:
                good = mock.Mock(status_code=200)
                good.json.return_value = {
                    "choices": [{"message": {"content": "본문" * 2000}}]
                }
                output = io.StringIO()
                stack.enter_context(redirect_stdout(output))
                stack.enter_context(
                    mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
                )
                stack.enter_context(
                    mock.patch.object(
                        llm, "output_is_clean_korean", return_value=(True, "ok")
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        llm, "output_has_required_structure", return_value=(True, "ok")
                    )
                )
                stack.enter_context(
                    mock.patch.object(llm, "looks_truncated", return_value=False)
                )
                post = stack.enter_context(
                    mock.patch.object(llm.requests, "post", side_effect=[failed, good])
                )
                _, model = llm.generate(
                    "system", "user", ["first", "second"], purpose="초안 생성"
                )
                self.assertEqual(model, "second")
                self.assertEqual(post.call_count, 2)
                self.assertLess(
                    output.getvalue().index(f"[생성 후보 실패] first — {reason}"),
                    output.getvalue().index("[요청 시작] 초안 생성 / second"),
                )

    def test_interrupt_does_not_fall_back_or_retry(self):
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(
                llm.requests, "post", side_effect=KeyboardInterrupt
            ) as post,
            redirect_stdout(io.StringIO()),
            self.assertRaises(KeyboardInterrupt),
        ):
            llm.generate("system", "user", ["first", "second"])
        post.assert_called_once()


class DifficultyProgressTest(unittest.TestCase):
    def test_batch_numbers_do_not_change_scoring_or_cache(self):
        topics = [{"id": f"topic-{i}"} for i in range(31)]
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(difficulty, "load_cache", return_value={}),
            mock.patch.object(difficulty, "_save_cache") as save,
            mock.patch.object(
                difficulty, "_score_chunk_with_llm", return_value={}
            ) as score,
            redirect_stdout(output),
        ):
            result = difficulty.score(
                topics, {"difficulty_model_fallback": ["scorer"]}, gateway=mock.Mock()
            )
        self.assertEqual(score.call_count, 2)
        self.assertEqual(len(result), 31)
        save.assert_called_once_with(result)
        self.assertIn("묶음 1/2 (30개)", output.getvalue())
        self.assertIn("묶음 2/2 (1개)", output.getvalue())
