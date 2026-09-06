"""OpenRouter 무료모델 호출 + fallback 체인."""

from __future__ import annotations

import os
import time
import requests

from contracts import GeneratedText, ModelGatewayError, ReviewResult
from quality import (
    MIN_BODY_CHARS,
    REVIEW_RESPONSE_FORMAT,
    looks_truncated,
    output_has_required_structure,
    output_is_clean_korean,
    parse_review_json,
)


def _print_usage(data: dict, model: str, purpose: str) -> None:
    """OpenRouter 응답에 포함된 실제 토큰·비용을 한 줄로 출력."""
    usage = data.get("usage") or {}
    if not usage:
        return

    prompt_tokens = usage.get("prompt_tokens", "?")
    completion_tokens = usage.get("completion_tokens", "?")
    details = usage.get("completion_tokens_details") or {}
    reasoning_tokens = details.get("reasoning_tokens", 0)
    cost = usage.get("cost")
    try:
        cost_text = f"${float(cost):.6f}" if cost is not None else "비용 미제공"
    except (TypeError, ValueError):
        cost_text = str(cost)
    print(
        f"  [사용량] {purpose} / {model}: "
        f"입력 {prompt_tokens}, 출력 {completion_tokens}"
        f"(reasoning {reasoning_tokens}), {cost_text}"
    )


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class LLMError(ModelGatewayError):
    pass


def fetch_free_models() -> list[str]:
    """OpenRouter에서 현재 살아있는 무료모델 id 목록을 실시간으로 가져온다."""
    resp = requests.get(OPENROUTER_MODELS_URL, timeout=30)
    resp.raise_for_status()
    out = []
    for m in resp.json().get("data", []):
        mid = m.get("id", "")
        # OpenRouter 무료 티어 규약: id가 ':free'로 끝남
        if not mid.endswith(":free"):
            continue
        # 텍스트 출력 모델만 (음악/이미지 생성 모델 제외)
        arch = m.get("architecture", {}) or {}
        out_mod = arch.get("output_modalities") or ["text"]
        if "text" not in out_mod:
            continue
        out.append(mid)
    return out


def _matches(mid: str, patterns: list[str]) -> bool:
    low = mid.lower()
    return any(p.lower() in low for p in patterns)


def build_fallback_chain(
    prefer: list[str], exclude: list[str], seed: list[str] | None = None
) -> list[str]:
    """실시간 무료모델을 가져와 선호순으로 정렬한 fallback 체인 생성.

    - exclude 패턴(소형/특수 모델 등)은 제외
    - prefer 패턴 순서대로 앞에 배치, 나머지는 뒤에
    - 실시간 조회 실패 시 seed(정적 목록) 사용
    """
    try:
        live = fetch_free_models()
    except requests.RequestException:
        return list(seed or [])
    if not live:
        return list(seed or [])

    usable = [m for m in live if not _matches(m, exclude)]

    def rank(mid: str) -> int:
        for i, p in enumerate(prefer):
            if p.lower() in mid.lower():
                return i
        return len(prefer)

    usable.sort(key=lambda m: (rank(m), m))
    return usable


def generate(
    system_prompt: str,
    user_prompt: str,
    model_fallback: list[str],
    purpose: str = "글 생성",
) -> tuple[str, str]:
    """fallback 체인을 순서대로 시도. (생성텍스트, 성공모델명) 반환.

    모든 모델 실패 시 LLMError.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY 환경변수가 없습니다.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # OpenRouter 권장 헤더 (선택)
        "HTTP-Referer": "https://lmj00.github.io",
        "X-Title": "lmj00-blog-generator",
    }

    # 큰 모델이 rate limit이면 작은 걸로 안 떨어지고, 잠깐 기다렸다 체인을 재시도한다.
    max_rounds = 4
    wait_seconds = 25
    all_errors = []
    for rnd in range(max_rounds):
        errors = []
        for model in model_fallback:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.4,
            }
            try:
                # (연결 타임아웃, 읽기 타임아웃)
                resp = requests.post(
                    OPENROUTER_URL, headers=headers, json=payload, timeout=(10, 300)
                )
            except requests.RequestException as e:
                errors.append(f"{model}: request_error {e}")
                continue
            if resp.status_code != 200:
                errors.append(f"{model}: http_{resp.status_code} {resp.text[:120]}")
                continue
            try:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
            except (KeyError, ValueError, IndexError) as e:
                errors.append(f"{model}: parse_error {e}")
                continue
            _print_usage(data, model, purpose)
            if not content:
                errors.append(f"{model}: empty_content")
                continue
            clean, reason = output_is_clean_korean(content)
            if not clean:
                errors.append(f"{model}: 품질 게이트 탈락({reason})")
                print(f"  [스킵] {model} — {reason}, 다음 모델로")
                continue
            structured, reason = output_has_required_structure(content)
            if not structured:
                errors.append(f"{model}: 출력 계약 탈락({reason})")
                print(f"  [스킵] {model} — {reason}, 다음 모델로")
                continue
            if len(content) < MIN_BODY_CHARS:
                errors.append(f"{model}: 본문 과소({len(content)}자)")
                print(
                    f"  [스킵] {model} — 본문 {len(content)}자로 너무 짧음, 다음 모델로"
                )
                continue
            if looks_truncated(content):
                errors.append(f"{model}: 잘린 출력 의심")
                print(f"  [스킵] {model} — 출력이 중간에 끊긴 듯, 다음 모델로")
                continue
            return content, model

        # 체인 한 바퀴 실패. rate limit이 많으면 기다렸다 재시도(작은 모델로 안 떨어짐).
        all_errors = errors
        rate_limited = sum(1 for e in errors if "http_429" in e)
        if rnd < max_rounds - 1 and rate_limited >= max(1, len(model_fallback) // 2):
            print(
                f"  대부분 rate limit — {wait_seconds}초 대기 후 재시도 (round {rnd + 2}/{max_rounds})"
            )
            time.sleep(wait_seconds)
            continue
        break

    raise LLMError("모든 모델 실패:\n" + "\n".join(all_errors))


def review(
    system_prompt: str,
    user_prompt: str,
    model_fallback: list[str],
    max_tokens: int = 4000,
    reasoning_tokens: int = 1200,
) -> tuple[dict, str]:
    """독립 모델로 초안을 검수하고 구조화된 판정과 사용 모델을 반환."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY 환경변수가 없습니다.")
    if not model_fallback:
        raise LLMError("검수 모델 목록이 비어 있습니다.")
    if reasoning_tokens < 0 or max_tokens <= reasoning_tokens:
        raise LLMError("검수 max_tokens는 reasoning_tokens보다 커야 합니다.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://lmj00.github.io",
        "X-Title": "lmj00-blog-generator",
    }
    errors = []
    for model in model_fallback:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "reasoning": {
                "max_tokens": reasoning_tokens,
                "exclude": True,
            },
            "response_format": REVIEW_RESPONSE_FORMAT,
        }
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=(10, 300),
            )
        except requests.RequestException as exc:
            errors.append(f"{model}: request_error {exc}")
            print(f"  [검수 재시도] {model} — 요청 실패")
            continue
        if resp.status_code != 200:
            errors.append(f"{model}: http_{resp.status_code} {resp.text[:120]}")
            print(f"  [검수 재시도] {model} — HTTP {resp.status_code}")
            continue
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError, TypeError) as exc:
            errors.append(f"{model}: parse_error {exc}")
            print(f"  [검수 재시도] {model} — 응답 본문 오류")
            continue
        _print_usage(data, model, "독립 검수")
        try:
            result = parse_review_json(content)
        except (ValueError, TypeError) as exc:
            errors.append(f"{model}: parse_error {exc}")
            print(f"  [검수 재시도] {model} — {exc}")
            continue
        return result, model

    raise LLMError("모든 검수 모델 실패:\n" + "\n".join(errors))


class OpenRouterGateway:
    """OpenRouter 구현을 파이프라인의 모델 계약에 맞추는 어댑터."""

    def build_fallback_chain(
        self,
        prefer: list[str],
        exclude: list[str],
        seed: list[str] | None = None,
    ) -> list[str]:
        return build_fallback_chain(prefer, exclude, seed)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_fallback: list[str],
        purpose: str = "글 생성",
    ) -> GeneratedText:
        content, model = generate(
            system_prompt,
            user_prompt,
            model_fallback,
            purpose=purpose,
        )
        return GeneratedText(content=content, model=model)

    def review(
        self,
        system_prompt: str,
        user_prompt: str,
        model_fallback: list[str],
        max_tokens: int = 4000,
        reasoning_tokens: int = 1200,
    ) -> ReviewResult:
        report, model = review(
            system_prompt,
            user_prompt,
            model_fallback,
            max_tokens=max_tokens,
            reasoning_tokens=reasoning_tokens,
        )
        return ReviewResult(report=report, model=model)
