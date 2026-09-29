"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import io
import json
import os
import time
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from unittest import mock

import generator.providers.openrouter as llm
from generator.contracts import ModelGatewayError
from generator.providers.openrouter_stream import ResponseObservation, read_response
from generator.providers.stream_deadline import FirstContentTimeout
from generator.tests.fixtures.providers import event, stream_response, wire


class StreamTest(unittest.TestCase):
    def test_fragmented_utf8_crlf_comments_and_final_usage(self):
        payload = wire(
            event('{"설명":', id="gen-test", provider="provider-test"),
            event('"좋음"}'),
            event(finish="stop"),
            event(finish="stop", usage={"completion_tokens": 12, "cost": 0.01}),
        )
        for size in (1, 7, 1024):
            with self.subTest(size=size):
                observed = []
                observation = ResponseObservation("model", "purpose", observed.append)
                record = {}
                data = read_response(
                    stream_response(
                        [payload[i : i + size] for i in range(0, len(payload), size)]
                    ),
                    observation,
                    record,
                )
                self.assertEqual(
                    data["choices"][0]["message"]["content"], '{"설명":"좋음"}'
                )
                self.assertEqual(record["usage"]["cost"], 0.01)
                self.assertEqual(observation.state["heartbeat_count"], 1)
                self.assertEqual(observation.state["received_bytes"], len(payload))
                self.assertIsNotNone(observation.state["first_content_seconds"])
                self.assertNotIn("좋음", json.dumps(observed, ensure_ascii=False))
                self.assertTrue(
                    any(item.get("response_id") == "gen-test" for item in observed)
                )

    def test_multiline_data_and_empty_choices_usage(self):
        payload = b'data: {"choices":\ndata: [{"delta":{"content":"{}"},"finish_reason":"stop"}]}\n\ndata: {"choices":[],"usage":{"cost":0.2}}\n\ndata: [DONE]\n\n'
        result = read_response(
            stream_response([payload]), ResponseObservation("m", "p"), {}
        )
        self.assertEqual(result["choices"][0]["message"]["content"], "{}")
        self.assertEqual(result["usage"], {"cost": 0.2})

    def test_whitespace_and_keepalive_are_not_output_progress(self):
        observation = ResponseObservation("m", "p")
        payload = wire(
            event("  \n"),
            event(finish="length"),
            usage_event := {
                "choices": [],
                "usage": {"completion_tokens_details": {"reasoning_tokens": 90000}},
            },
        )
        result = read_response(stream_response([payload]), observation, {})
        self.assertIsNone(observation.state["first_content_seconds"])
        self.assertEqual(observation.state["non_whitespace_content_chars"], 0)
        self.assertEqual(result["usage"], usage_event["usage"])
        self.assertIn("아직 없음", observation.describe())

    def test_bad_or_incomplete_stream_never_returns_partial_success(self):
        for payload in (
            wire(event("{}"), done=False),
            wire(event("{}", finish="stop"), done=False),
            wire(event("{}")),
            wire(event("{}", finish="content_filter")),
            wire(
                event("{}", finish="stop"),
                {"error": {"message": "private upstream error"}},
            ),
            b"data: invalid\n\ndata: [DONE]\n\n",
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                read_response(
                    stream_response([payload]), ResponseObservation("m", "p"), {}
                )

    def test_json_response_fallback_and_size_guard(self):
        payload = {
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"cost": 1},
        }
        result = read_response(
            stream_response([b" ", json.dumps(payload).encode()], "application/json"),
            ResponseObservation("m", "p"),
            {},
        )
        self.assertEqual(result, payload)
        with self.assertRaisesRegex(ValueError, "크기 제한"):
            read_response(
                stream_response([b" " * 2_000_001]), ResponseObservation("m", "p"), {}
            )

    def test_midstream_error_keeps_partial_artifact_and_reported_usage(self):
        record = {}
        payload = wire(
            event("partial"), {"error": {"message": "private"}, "usage": {"cost": 0.1}}
        )
        with self.assertRaisesRegex(ValueError, "스트림 오류"):
            read_response(
                stream_response([payload]), ResponseObservation("m", "p"), record
            )
        self.assertEqual(record["content"], "partial")
        self.assertEqual(record["usage"], {"cost": 0.1})
        self.assertEqual(record["finish_reason"], "error")


class StreamingGatewayTest(unittest.TestCase):
    def call(self, reply):
        records, progress = [], []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "private-key"}),
            mock.patch.object(llm.requests, "post", return_value=reply) as post,
            redirect_stdout(io.StringIO()),
        ):
            try:
                result = llm.OpenRouterGateway().complete_json(
                    "private-system",
                    "private-user",
                    ["designer"],
                    purpose="repair",
                    max_tokens=None,
                    reasoning_tokens=4000,
                    reasoning_efforts={"designer": "low"},
                    format_retries=1,
                    on_attempt=records.append,
                    on_progress=progress.append,
                )
            except ModelGatewayError as exc:
                result = exc
        reply.close.assert_called_once()
        return result, records, progress, post

    def test_streaming_settings_progress_before_completion_and_final_usage(self):
        reply = stream_response(
            [wire(event("{}", finish="stop", usage={"cost": 0.01}))]
        )
        result, records, progress, post = self.call(reply)
        self.assertEqual(result.content, "{}")
        self.assertTrue(post.call_args.kwargs["json"]["stream"])
        self.assertNotIn("max_tokens", post.call_args.kwargs["json"])
        self.assertEqual(progress[0]["event"], "request_started")
        self.assertEqual(progress[-1]["event"], "valid")
        self.assertTrue(any(item["event"] == "headers_received" for item in progress))
        self.assertEqual(records[0]["response_id"], "gen-test")
        for private in ("private-key", "private-system", "private-user"):
            self.assertNotIn(private, json.dumps(progress))

    def test_length_and_incomplete_stream_do_not_trigger_format_retry(self):
        for payload in (
            wire(event("{}", finish="length")),
            wire(event("{}", finish="stop"), done=False),
        ):
            with self.subTest(payload=payload):
                result, records, _, post = self.call(stream_response([payload]))
                self.assertIsInstance(result, ModelGatewayError)
                post.assert_called_once()
                self.assertEqual(records[0]["status"], "request_error")

    def test_interrupt_is_recorded_without_retry(self):
        reply = stream_response([])
        reply.iter_content.side_effect = KeyboardInterrupt
        progress, records = [], []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "key"}),
            mock.patch.object(llm.requests, "post", return_value=reply) as post,
            self.assertRaises(KeyboardInterrupt),
        ):
            llm.OpenRouterGateway().complete_json(
                "s",
                "u",
                ["d", "backup"],
                purpose="p",
                max_tokens=None,
                reasoning_tokens=1,
                on_attempt=records.append,
                on_progress=progress.append,
            )
        post.assert_called_once()
        reply.close.assert_called_once()
        self.assertEqual(records[0]["status"], "interrupted")
        self.assertEqual(progress[-1]["event"], "interrupted")


class DeadlineTest(unittest.TestCase):
    def test_real_http_keepalive_request_falls_back_within_deadline(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append(data["model"])
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                if data["model"] == "backup":
                    self.wfile.write(wire(event("{}", finish="stop")))
                    return
                try:
                    for _ in range(150):
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        Event().wait(0.02)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
            )
            worker.start()
            try:
                with (
                    mock.patch.object(
                        llm, "OPENROUTER_URL", f"http://127.0.0.1:{server.server_port}"
                    ),
                    mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"}),
                ):
                    records = []
                    started = time.monotonic()
                    result = llm.OpenRouterGateway(
                        first_content_timeout=1
                    ).complete_json(
                        "s",
                        "u",
                        ["primary", "backup"],
                        purpose="local transport test",
                        max_tokens=None,
                        reasoning_tokens=0,
                        format_retries=1,
                        on_attempt=records.append,
                    )
                    self.assertLess(time.monotonic() - started, 2.5)
                self.assertEqual(result.model, "backup")
                self.assertEqual(seen, ["primary", "backup"])
                self.assertEqual(records[0]["status"], "first_content_timeout")
                self.assertEqual(
                    records[0]["progress"]["non_whitespace_content_chars"], 0
                )
            finally:
                server.shutdown()
                worker.join(timeout=2)

    def test_silent_reader_does_not_block_fallback_and_eventually_closes(self):
        release, closed = Event(), Event()

        def stalled():
            release.wait(2)
            yield b": heartbeat\n\n"

        reply = stream_response(stalled())
        reply.close.side_effect = closed.set
        started = time.monotonic()
        try:
            with self.assertRaises(FirstContentTimeout):
                read_response(
                    reply, ResponseObservation("m", "p"), {}, first_content_timeout=0.05
                )
            self.assertLess(time.monotonic() - started, 0.5)
        finally:
            release.set()
        self.assertTrue(closed.wait(1))

    def test_keepalive_whitespace_and_reasoning_do_not_reset_deadline(self):
        stop = Event()

        def heartbeats():
            while not stop.wait(0.01):
                yield wire(event("  ", reasoning="thinking"), done=False)

        observed = ResponseObservation("m", "p")
        try:
            with self.assertRaises(FirstContentTimeout):
                read_response(
                    stream_response(heartbeats()),
                    observed,
                    {},
                    first_content_timeout=0.08,
                )
            self.assertGreater(observed.state["heartbeat_count"], 0)
            self.assertIsNone(observed.state["first_content_seconds"])
        finally:
            stop.set()

    def test_started_output_is_not_cut_at_initial_deadline(self):
        def slow_complete():
            yield wire(event('{"value":'), done=False)
            Event().wait(0.15)
            yield wire(event('"complete"}', finish="stop"))

        result = read_response(
            stream_response(slow_complete()),
            ResponseObservation("m", "p"),
            {},
            first_content_timeout=0.08,
        )
        self.assertEqual(
            result["choices"][0]["message"]["content"], '{"value":"complete"}'
        )

    def test_local_reader_preserves_schema_usage_and_json_fallback(self):
        reply = stream_response(
            [wire(event("{}", finish="stop", usage={"cost": 0.01}))]
        )
        record = {}
        result = read_response(
            reply, ResponseObservation("m", "p"), record, first_content_timeout=1
        )
        self.assertEqual(result["usage"], {"cost": 0.01})
        self.assertEqual(record["content"], "{}")
        reply = stream_response(
            [b'{"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}]}'],
            "application/json",
        )
        result = read_response(
            reply, ResponseObservation("m", "p"), {}, first_content_timeout=1
        )
        self.assertEqual(result["choices"][0]["message"]["content"], "{}")

    def test_deadline_moves_to_next_model_without_format_retry(self):
        replies = [stream_response([]), stream_response([])]
        records = []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test"}),
            mock.patch.object(llm.requests, "post", side_effect=replies) as post,
            mock.patch.object(
                llm,
                "read_response",
                side_effect=[
                    FirstContentTimeout("first output"),
                    {
                        "choices": [
                            {"message": {"content": "{}"}, "finish_reason": "stop"}
                        ]
                    },
                ],
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO),
        ):
            result = llm.OpenRouterGateway(first_content_timeout=120).complete_json(
                "s",
                "u",
                ["primary", "backup"],
                purpose="test",
                max_tokens=None,
                reasoning_tokens=4000,
                format_retries=1,
                on_attempt=records.append,
            )
        self.assertEqual(result.model, "backup")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(
            [r["status"] for r in records], ["first_content_timeout", "valid"]
        )
        self.assertTrue(all(not r["format_retry"] for r in records))
        self.assertEqual(records[0]["local_first_content_timeout_seconds"], 120)
        for call in post.call_args_list:
            self.assertNotIn("max_tokens", call.kwargs["json"])
            self.assertNotIn("first_content_timeout", call.kwargs["json"])
            self.assertEqual(call.kwargs["timeout"], (10, 120))

    def test_default_gateway_keeps_original_wait_policy(self):
        reply = stream_response([wire(event("{}", finish="stop"))])
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test"}),
            mock.patch.object(llm.requests, "post", return_value=reply) as post,
        ):
            llm.OpenRouterGateway().complete_json(
                "s",
                "u",
                ["model"],
                purpose="test",
                max_tokens=None,
                reasoning_tokens=4000,
            )
        self.assertEqual(post.call_args.kwargs["timeout"], (10, 300))
        reply.iter_content.assert_called_once_with(chunk_size=1024)
        reply.close.assert_called_once()
