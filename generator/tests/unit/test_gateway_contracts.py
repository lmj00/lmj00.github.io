"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

import generator.providers.openrouter as llm
from generator.contracts import GeneratedText, ModelGatewayError
from generator.tests.fixtures.content import review_report


class TextTransportTest(unittest.TestCase):
    def test_short_completion_keeps_scoring_request_policy_and_closes_response(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": ' {"overview": 1} '}}],
            "usage": {"prompt_tokens": 10},
        }
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response) as post,
        ):
            result = llm.OpenRouterGateway().complete_text(
                "system", "user", "scorer", purpose="채점"
            )
        self.assertEqual(
            result, GeneratedText('{"overview": 1}', "scorer", {"prompt_tokens": 10})
        )
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["timeout"], (10, 120))
        self.assertEqual(post.call_args.kwargs["json"]["temperature"], 0)
        self.assertNotIn("max_tokens", post.call_args.kwargs["json"])
        self.assertNotIn("stream", post.call_args.kwargs)
        response.close.assert_called_once()

    def test_all_text_paths_redact_http_transport_and_parse_errors(self):
        secret = "synthetic-credential-for-redaction"
        for purpose in ("draft", "review", "score"):
            for failure in ("http", "transport", "parse"):
                with self.subTest(purpose=purpose, failure=failure):
                    output = io.StringIO()
                    response = mock.Mock(status_code=401 if failure == "http" else 200)
                    response.headers = {}
                    response.iter_content.return_value = [
                        json.dumps(
                            {
                                "error": {
                                    "message": f"Bearer {secret} private-system private-user",
                                    "metadata": {"raw": secret},
                                }
                            }
                        ).encode()
                    ]
                    response.json.side_effect = ValueError(secret)
                    effect = (
                        llm.requests.ReadTimeout(secret)
                        if failure == "transport"
                        else None
                    )
                    with (
                        mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": secret}),
                        mock.patch.object(
                            llm.requests,
                            "post",
                            side_effect=effect,
                            return_value=response,
                        ) as post,
                        redirect_stdout(output),
                        self.assertRaises(ModelGatewayError) as raised,
                    ):
                        if purpose == "draft":
                            llm.generate("private-system", "private-user", ["model"])
                        elif purpose == "review":
                            llm.review("private-system", "private-user", ["model"])
                        else:
                            llm.OpenRouterGateway().complete_text(
                                "private-system",
                                "private-user",
                                "model",
                                purpose="채점",
                            )
                    for private in (secret, "private-system", "private-user"):
                        self.assertNotIn(
                            private, str(raised.exception) + output.getvalue()
                        )
                    post.assert_called_once()
                    if failure != "transport":
                        response.close.assert_called_once()

    def test_draft_rate_limit_rounds_and_wait_are_unchanged(self):
        response = mock.Mock(status_code=429, headers={})
        response.iter_content.return_value = []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response) as post,
            mock.patch.object(llm.time, "sleep") as sleep,
            self.assertRaises(ModelGatewayError),
        ):
            llm.generate("system", "user", ["a", "b"])
        self.assertEqual(post.call_count, 8)
        self.assertEqual(sleep.call_args_list, [mock.call(25)] * 3)
        self.assertEqual(response.close.call_count, 8)

    def test_stream_callbacks_redact_echoed_keys_without_mutating_model_output(self):
        secret = "synthetic-credential-for-redaction"
        payload = {
            "id": secret,
            "provider": secret,
            "model": secret,
            "choices": [
                {"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}
            ],
            "usage": {"cost": secret, "prompt_tokens": secret},
        }
        response = mock.Mock(status_code=200, headers={"X-Generation-Id": secret})
        response.iter_content.return_value = [json.dumps(payload).encode()]
        records, progress, output = [], [], io.StringIO()
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": secret}),
            mock.patch.object(llm.requests, "post", return_value=response),
            redirect_stdout(output),
        ):
            result = llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["model"],
                purpose="design",
                max_tokens=None,
                reasoning_tokens=0,
                on_attempt=records.append,
                on_progress=progress.append,
            )
        self.assertEqual(result.content, '{"ok": true}')
        self.assertNotIn(
            secret, json.dumps(records) + json.dumps(progress) + output.getvalue()
        )


class DesignGatewayTest(unittest.TestCase):
    def call_structured(
        self,
        contents,
        models=None,
        reasoning_efforts=None,
        max_tokens=4000,
        finish_reason="stop",
    ):
        schema = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }
        responses = []
        for content in contents:
            response = mock.Mock()
            response.iter_content.return_value = [
                json.dumps(
                    {
                        "id": "test-response-id",
                        "provider": "test-provider",
                        "model": "test-response-model",
                        "choices": [
                            {
                                "finish_reason": finish_reason,
                                "message": {"content": content},
                            }
                        ],
                        "usage": {"cost": 0.01},
                    }
                ).encode()
            ]
            responses.append(response)
        records = []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", side_effect=responses) as post,
        ):
            try:
                result = llm.OpenRouterGateway().complete_json(
                    "system",
                    "user",
                    models or ["reviewer"],
                    purpose="design",
                    max_tokens=max_tokens,
                    reasoning_tokens=1000,
                    reasoning_efforts=reasoning_efforts,
                    response_schema=schema,
                    format_retries=1,
                    on_attempt=records.append,
                )
            except ModelGatewayError as exc:
                result = exc
        for response in responses[: post.call_count]:
            response.close.assert_called_once()
        return result, records, post.call_args_list

    def test_no_request_limit_on_initial_retry_or_fallback(self):
        result, records, calls = self.call_structured(
            ["bad json", "{}", '{"ok":true}'],
            models=["deepseek", "qwen"],
            reasoning_efforts={"deepseek": "low"},
            max_tokens=None,
        )
        self.assertIsInstance(result, GeneratedText)
        self.assertEqual(len(calls), 3)
        for call, record in zip(calls, records):
            self.assertNotIn("max_tokens", call.kwargs["json"])
            self.assertNotIn("max_completion_tokens", call.kwargs["json"])
            self.assertNotIn("max_tokens", record["request_parameters"])
            self.assertTrue(call.kwargs["json"]["provider"]["require_parameters"])
        self.assertEqual(
            calls[0].kwargs["json"]["reasoning"], {"effort": "low", "exclude": True}
        )
        self.assertEqual(
            calls[-1].kwargs["json"]["reasoning"], {"max_tokens": 1000, "exclude": True}
        )

    def test_explicit_limit_above_old_ceiling_is_preserved(self):
        result, records, calls = self.call_structured(['{"ok":true}'], max_tokens=64000)
        self.assertIsInstance(result, GeneratedText)
        self.assertEqual(calls[0].kwargs["json"]["max_tokens"], 64000)
        self.assertEqual(records[0]["request_parameters"]["max_tokens"], 64000)

    def test_provider_truncation_is_still_rejected_without_request_limit(self):
        result, records, calls = self.call_structured(
            ['{"ok":'], models=["designer"], max_tokens=None, finish_reason="length"
        )
        self.assertIsInstance(result, ModelGatewayError)
        self.assertIn("출력 토큰 한도 도달", str(result))
        self.assertEqual(len(calls), 1)
        self.assertEqual(records[0]["finish_reason"], "length")

    def test_invalid_explicit_limit_fails_before_http(self):
        for value in (0, -1, True, "64000", 64000.5, 1000):
            with self.subTest(limit=value):
                result, records, calls = self.call_structured([], max_tokens=value)
                self.assertIsInstance(result, ModelGatewayError)
                self.assertEqual(records, [])
                self.assertEqual(calls, [])

    def test_effort_applies_only_to_selected_model_and_survives_format_retry(self):
        result, records, calls = self.call_structured(
            ["bad json", "{}", '{"ok":true}'],
            models=["deepseek", "qwen"],
            reasoning_efforts={"deepseek": "low"},
        )
        self.assertIsInstance(result, GeneratedText)
        self.assertEqual(
            [c.kwargs["json"]["reasoning"] for c in calls],
            [{"effort": "low", "exclude": True}] * 2
            + [{"max_tokens": 1000, "exclude": True}],
        )
        for record, call in zip(records, calls):
            self.assertEqual(
                record["request_parameters"],
                {
                    "max_tokens": 4000,
                    "reasoning": call.kwargs["json"]["reasoning"],
                    "stream": True,
                },
            )
            self.assertEqual(record["response_id"], "test-response-id")
            self.assertEqual(record["provider"], "test-provider")
            self.assertEqual(record["finish_reason"], "stop")
            self.assertNotIn("test-key", json.dumps(record))

    def test_invalid_effort_fails_before_http(self):
        for value in ({"designer": "invalid"}, {"designer": 4}, ["low"]):
            result, records, calls = self.call_structured([], reasoning_efforts=value)
            self.assertIsInstance(result, ModelGatewayError)
            self.assertEqual(records, [])
            self.assertEqual(calls, [])

    def test_schema_retry_keeps_strict_provider_contract(self):
        result, records, calls = self.call_structured(['{"ok":"yes"}', '{"ok":true}'])
        self.assertIsInstance(result, GeneratedText)
        self.assertEqual(len(calls), 2)
        self.assertEqual([r["status"] for r in records], ["format_error", "valid"])
        for call in calls:
            request = call.kwargs["json"]
            self.assertTrue(request["provider"]["require_parameters"])
            self.assertEqual(request["response_format"]["type"], "json_schema")
            self.assertTrue(request["response_format"]["json_schema"]["strict"])
        self.assertEqual(
            calls[0].kwargs["json"]["messages"], calls[1].kwargs["json"]["messages"][:2]
        )

    def test_format_retry_budget_is_shared_across_fallbacks(self):
        result, records, calls = self.call_structured(
            ['{"broken"', "{}", "[]"],
            ["first", "first", "second", "third"],
        )
        self.assertIsInstance(result, ModelGatewayError)
        self.assertEqual(
            [c.kwargs["json"]["model"] for c in calls], ["first", "first", "second"]
        )
        self.assertEqual([r["format_retry"] for r in records], [False, True, False])
        self.assertEqual(len(records), 3)

    def test_fallback_after_exhausted_format_retry_can_succeed(self):
        result, _, calls = self.call_structured(
            ["{", "{}", '{"ok":true}'], ["first", "second"]
        )
        self.assertEqual(result.model, "second")
        self.assertEqual(len(calls), 3)

    def test_http_error_does_not_trigger_format_retry_or_weaken_schema(self):
        records = []
        response = mock.Mock(status_code=400)
        response.raise_for_status.side_effect = llm.requests.HTTPError(
            "private response"
        )
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response) as post,
            self.assertRaises(ModelGatewayError),
        ):
            llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["first", "second"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
                response_schema={"type": "object"},
                format_retries=1,
                on_attempt=records.append,
            )
        self.assertEqual(post.call_count, 2)
        self.assertTrue(
            all(
                c.kwargs["json"]["provider"]["require_parameters"]
                for c in post.call_args_list
            )
        )
        self.assertEqual(
            [r["status"] for r in records], ["request_error", "request_error"]
        )
        self.assertNotIn("private response", json.dumps(records))

    def test_invalid_retry_budget_or_schema_makes_no_request(self):
        from jsonschema import SchemaError

        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post") as post,
        ):
            for options in [
                {"format_retries": 2},
                {"response_schema": {"type": "invalid"}},
            ]:
                with self.assertRaises((ModelGatewayError, SchemaError)):
                    llm.OpenRouterGateway().complete_json(
                        "system",
                        "user",
                        ["reviewer"],
                        purpose="design",
                        max_tokens=4000,
                        reasoning_tokens=1000,
                        **options,
                    )
            post.assert_not_called()

    def test_json_output_bypasses_markdown_gate_and_keeps_usage(self):
        response = mock.Mock()
        payload = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"summary":"design"}'},
                }
            ],
            "usage": {"cost": 0.001},
        }
        response.iter_content.return_value = [json.dumps(payload).encode()]
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response),
        ):
            result = llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["designer"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
            )
        self.assertEqual(result.usage["cost"], 0.001)
        response.close.assert_called_once()

    def test_truncated_output_is_rejected(self):
        response = mock.Mock()
        payload = {
            "choices": [{"finish_reason": "length", "message": {"content": "{}"}}]
        }
        response.iter_content.return_value = [json.dumps(payload).encode()]
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response),
            self.assertRaises(ModelGatewayError),
        ):
            llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["designer"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
            )

    def test_long_response_finishes_without_elapsed_timeout_or_fallback(self):
        response = mock.Mock()
        records = []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response) as post,
            mock.patch.object(llm.time, "monotonic", return_value=0) as clock,
            mock.patch.object(
                llm, "request_progress", wraps=llm.request_progress
            ) as progress,
        ):

            def chunks(chunk_size):
                clock.return_value = 301
                yield b" "
                clock.return_value = 960
                yield json.dumps(
                    {
                        "choices": [
                            {"finish_reason": "stop", "message": {"content": "{}"}}
                        ],
                        "usage": {"cost": 0.001},
                    }
                ).encode()

            response.iter_content.side_effect = chunks
            result = llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["designer", "backup"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
                on_attempt=records.append,
            )
        self.assertEqual(result.model, "designer")
        post.assert_called_once()
        progress.assert_called_once_with("designer", "design", detail=mock.ANY)
        self.assertTrue(post.call_args.kwargs["json"]["stream"])
        self.assertEqual(post.call_args.kwargs["timeout"], (10, 300))
        self.assertTrue(post.call_args.kwargs["stream"])
        self.assertEqual(records[0]["status"], "valid")
        self.assertEqual(records[0]["elapsed_seconds"], 960)
        response.close.assert_called_once()

    def test_read_timeout_falls_back_without_format_retry(self):
        stalled = mock.Mock()
        stalled.iter_content.side_effect = llm.requests.ReadTimeout("private-error")
        good = mock.Mock()
        good.iter_content.return_value = [
            json.dumps(
                {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
            ).encode()
        ]
        records = []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(
                llm.requests, "post", side_effect=[stalled, good]
            ) as post,
        ):
            result = llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["designer", "backup"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
                format_retries=1,
                on_attempt=records.append,
            )
        self.assertEqual(result.model, "backup")
        self.assertEqual(post.call_count, 2)
        self.assertEqual([r["status"] for r in records], ["request_error", "valid"])
        self.assertIn("ReadTimeout", records[0]["error"])
        self.assertNotIn("private-error", json.dumps(records))
        stalled.close.assert_called_once()
        good.close.assert_called_once()

    def test_large_response_is_still_rejected(self):
        response = mock.Mock()
        response.iter_content.return_value = [b" " * 2_000_001]
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response) as post,
            self.assertRaisesRegex(ModelGatewayError, "응답 크기 제한"),
        ):
            llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["designer"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
                format_retries=1,
            )
        post.assert_called_once()
        response.close.assert_called_once()

    def test_interrupt_closes_response_and_does_not_retry(self):
        response = mock.Mock()
        response.iter_content.side_effect = KeyboardInterrupt
        records = []
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response) as post,
            self.assertRaises(KeyboardInterrupt),
        ):
            llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["designer", "backup"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
                format_retries=1,
                on_attempt=records.append,
            )
        post.assert_called_once()
        response.close.assert_called_once()
        self.assertEqual(records[0]["status"], "interrupted")
        self.assertIn("elapsed_seconds", records[0])

    def test_http_status_survives_in_failure_report(self):
        response = mock.Mock(status_code=429)
        response.raise_for_status.side_effect = llm.requests.HTTPError(
            "private response"
        )
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", return_value=response),
            self.assertRaisesRegex(ModelGatewayError, "HTTP 429") as raised,
        ):
            llm.OpenRouterGateway().complete_json(
                "system",
                "user",
                ["designer"],
                purpose="design",
                max_tokens=4000,
                reasoning_tokens=1000,
            )
        self.assertNotIn("private response", str(raised.exception))
        response.close.assert_called_once()


class ReviewApiTest(unittest.TestCase):
    def test_falls_back_and_sends_structured_low_reasoning_request(self) -> None:
        good_report = json.dumps(review_report(), ensure_ascii=False)
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
            mock.patch.object(
                llm.requests, "post", side_effect=[failed, succeeded]
            ) as post,
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
            "choices": [{"message": {"content": json.dumps(review_report())}}],
        }
        with (
            mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            mock.patch.object(llm.requests, "post", side_effect=[empty, good]),
        ):
            _, model = llm.review("system", "user", ["first", "second"])
        self.assertEqual(model, "second")
