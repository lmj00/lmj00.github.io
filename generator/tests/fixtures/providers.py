"""Reusable fictional inputs and test doubles; never test cases."""

from __future__ import annotations

import json
from unittest import mock

import generator.providers.openrouter as llm

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def gateway_response(
    content='{"ok":true}', *, error=None, status=200, retry_after=None
):
    result = mock.Mock(status_code=status)
    result.headers = {"Content-Type": "application/json"}
    if retry_after is not None:
        result.headers["Retry-After"] = retry_after
    data = (
        {"error": error}
        if error is not None
        else {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
    )
    result.iter_content.return_value = [json.dumps(data).encode()]
    if status >= 400:
        result.raise_for_status.side_effect = llm.requests.HTTPError(
            "private HTTP detail"
        )
    return result


def event(content=None, finish=None, **extra):
    return {
        "choices": [
            {"index": 0, "delta": {"content": content}, "finish_reason": finish}
        ],
        **extra,
    }


def wire(*events, done=True):
    text = ": OPENROUTER PROCESSING\r\n\r\n"
    text += "".join(
        "data: " + json.dumps(item, ensure_ascii=False) + "\r\n\r\n" for item in events
    )
    return (text + ("data: [DONE]\r\n\r\n" if done else "")).encode()


def stream_response(chunks, content_type="text/event-stream"):
    value = mock.Mock(status_code=200)
    value.headers = {"Content-Type": content_type, "X-Generation-Id": "gen-test"}
    value.iter_content.return_value = chunks
    return value
