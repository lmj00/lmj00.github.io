"""OpenRouter SSE 수신과 안전한 진행 메타데이터. 재시도/시간 정책은 호출자 소유."""

from __future__ import annotations

import codecs
import json
import re
from time import monotonic

from generator.providers.stream_deadline import deadline_chunks


class ProviderResponseError(ValueError):
    """API 오류 원문은 예외 문자열로 출력하지 않고 게이트웨이에서 선별 기록한다."""

    def __init__(self, error, *, streamed=False):
        self.error = error
        super().__init__("API 스트림 오류" if streamed else "API 응답 오류")


class ResponseObservation:
    """본문/추론/인증정보 없이 수신 상태만 기록한다. 숫자는 토큰 추정치가 아니다."""

    def __init__(self, model, purpose, callback=None):
        self.started = monotonic()
        self.callback = callback
        self.last_emitted = self.started
        self.state = {
            "model": model,
            "purpose": purpose,
            "received_bytes": 0,
            "content_chars": 0,
            "non_whitespace_content_chars": 0,
            "reasoning_chars": 0,
            "heartbeat_count": 0,
            "first_byte_seconds": None,
            "first_content_seconds": None,
            "last_byte_seconds": None,
            "last_content_seconds": None,
        }
        self.emit("request_started", force=True)

    def elapsed(self):
        return round(monotonic() - self.started, 3)

    def emit(self, event, *, force=False):
        now = monotonic()
        if force or now - self.last_emitted >= 30:
            self.last_emitted = now
            if self.callback is not None:
                self.callback(
                    {**self.state, "event": event, "elapsed_seconds": self.elapsed()}
                )

    def headers(self, response):
        if type(response.status_code) is int:
            self.state["http_status"] = response.status_code
        self.state["headers_seconds"] = self.elapsed()
        self.metadata({"id": response.headers.get("X-Generation-Id")})
        self.emit("headers_received", force=True)

    def metadata(self, data):
        changed = False
        for source, target in (
            ("id", "response_id"),
            ("provider", "provider"),
            ("model", "response_model"),
        ):
            value = data.get(source)
            if isinstance(value, str):
                safe = re.sub(r"[^\w .:/-]", "", value)[:160]
                changed = changed or self.state.get(target) != safe
                self.state[target] = safe
        if changed:
            self.emit("metadata_received", force=True)

    def received(self, chunk):
        first = self.state["first_byte_seconds"] is None
        elapsed = self.elapsed()
        self.state["received_bytes"] += len(chunk)
        self.state["last_byte_seconds"] = elapsed
        if first:
            self.state["first_byte_seconds"] = elapsed
        self.emit("bytes_received", force=first)

    def content(self, text):
        if not text:
            return
        self.state["content_chars"] += len(text)
        visible = len(re.sub(r"\s", "", text))
        self.state["non_whitespace_content_chars"] += visible
        if not visible:
            return
        first = self.state["first_content_seconds"] is None
        elapsed = self.elapsed()
        self.state["last_content_seconds"] = elapsed
        if first:
            self.state["first_content_seconds"] = elapsed
        self.emit("content_received", force=first)

    def describe(self):
        state = self.state.copy()
        last = state["last_content_seconds"]
        idle = "아직 없음" if last is None else f"{self.elapsed() - last:.0f}초 전"
        return (
            f"수신 {state['received_bytes']}B / 연결 유지 {state['heartbeat_count']}회 / "
            f"결과(공백 제외) {state['non_whitespace_content_chars']}자 / 마지막 결과 {idle} "
            "(추론 진행률은 알 수 없음)"
        )


def read_response(
    response,
    observation: ResponseObservation,
    record: dict,
    *,
    first_content_timeout=None,
) -> dict:
    """완전한 SSE 종료만 성공으로 취급. JSON 응답을 돌려주는 공급자도 지원한다."""
    decoder = codecs.getincrementaldecoder("utf-8")()
    buffer = ""
    content_type = response.headers.get("Content-Type", "")
    mode = (
        "sse"
        if isinstance(content_type, str) and "text/event-stream" in content_type
        else None
    )
    fields = []
    fragments = []
    result = {
        "choices": [{"message": {"content": ""}, "finish_reason": None}],
        "usage": {},
    }
    done = False

    def dispatch():
        nonlocal done
        if not fields:
            return
        payload = "\n".join(fields)
        fields.clear()
        if payload.strip() == "[DONE]":
            done = True
            return
        try:
            event = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("SSE 이벤트 JSON 손상") from exc
        if not isinstance(event, dict):
            raise ValueError("SSE 이벤트 객체 필요")
        observation.metadata(event)
        for name in ("id", "provider", "model", "usage"):
            if event.get(name) is not None:
                result[name] = event[name]
        if event.get("error"):
            result["choices"][0]["finish_reason"] = "error"
            raise ProviderResponseError(event["error"], streamed=True)
        for choice in event.get("choices", []):
            if choice.get("index", 0) != 0:
                raise ValueError("복수 SSE 응답은 지원하지 않음")
            delta = choice.get("delta") or {}
            if delta.get("tool_calls") or delta.get("refusal"):
                raise ValueError("디자인 대신 도구 호출/거절 응답 수신")
            content = delta.get("content")
            if content is not None:
                if not isinstance(content, str):
                    raise ValueError("SSE content 문자열 필요")
                fragments.append(content)
                observation.content(content)
            reasoning = delta.get("reasoning")
            if isinstance(reasoning, str):
                observation.state["reasoning_chars"] += len(reasoning)
            finish = choice.get("finish_reason")
            if finish is not None:
                previous = result["choices"][0]["finish_reason"]
                if previous is not None and previous != finish:
                    raise ValueError("SSE 종료 사유 불일치")
                result["choices"][0]["finish_reason"] = finish
                observation.state["finish_reason"] = finish
        observation.emit("stream_event")

    def consume_lines(*, final=False):
        nonlocal buffer
        while not done:
            match = re.search(r"\r\n|\r|\n", buffer)
            if match is None:
                break
            if match.group() == "\r" and match.end() == len(buffer) and not final:
                break  # CRLF may be split across network chunks.
            line, buffer = buffer[: match.start()], buffer[match.end() :]
            if not line:
                dispatch()
            elif line.startswith(":"):
                observation.state["heartbeat_count"] += 1
                observation.emit("heartbeat")
            else:
                name, _, value = line.partition(":")
                if name == "data":
                    fields.append(value[1:] if value.startswith(" ") else value)

    chunks = (
        deadline_chunks(response, observation, first_content_timeout)
        if first_content_timeout is not None
        else response.iter_content(chunk_size=1024)
    )
    try:
        for chunk in chunks:
            if not chunk:
                continue
            observation.received(chunk)
            if observation.state["received_bytes"] > 2_000_000:
                raise ValueError("디자인 API 응답 크기 제한 초과")
            buffer += decoder.decode(chunk)
            if mode is None:
                stripped = buffer.lstrip()
                if not stripped:
                    continue
                mode = "json" if stripped[0] in "{[" else "sse"
            if mode == "sse":
                consume_lines()
                if done:
                    break
        buffer += decoder.decode(b"", final=True)
        if mode == "json":
            parsed = json.loads(buffer)
            if not isinstance(parsed, dict):
                raise ValueError("API 응답 객체 필요")
            result = parsed
            observation.metadata(result)
            choices = result.get("choices") or []
            if choices:
                text = choices[0].get("message", {}).get("content")
                if isinstance(text, str):
                    observation.content(text)
            return result
        consume_lines(final=True)
        finish = result["choices"][0]["finish_reason"]
        if not done or finish is None:
            raise ValueError("SSE 응답이 완전히 종료되지 않음")
        if finish not in {"stop", "length"}:
            raise ValueError("SSE 응답 비정상 종료")
        return result
    finally:
        if first_content_timeout is not None:
            chunks.close()
        if mode != "json":
            result["choices"][0]["message"]["content"] = "".join(fragments)
        record["usage"] = result.get("usage") or {}
        record.update(
            {
                key: observation.state.get(key)
                for key in ("response_id", "provider", "response_model")
            }
        )
        choices = result.get("choices") or []
        if choices:
            record["content"] = choices[0].get("message", {}).get("content")
            record["finish_reason"] = choices[0].get("finish_reason")
