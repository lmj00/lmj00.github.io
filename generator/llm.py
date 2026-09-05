"""OpenRouter 무료모델 호출 + fallback 체인."""
from __future__ import annotations

import json
import os
import time
import re
import requests

# 일본어 가나(히라가나·가타카나) = 명백한 언어 누출 신호
_JP_KANA = re.compile(r"[぀-ヿ]")
# 한자(CJK 표의문자) — 현대 한국어 기술 글엔 거의 없음
_CJK = re.compile(r"[一-鿿]")
_TITLE_LINE = re.compile(r"^제목\s*[:：]\s*\S(?:.*\S)?$", re.MULTILINE)
_SUMMARY_LINE = re.compile(r"^>\s*한 줄 요약\s*[:：]\s*\S+", re.MULTILINE)
_OVERVIEW_HEADING = re.compile(r"^###\s+개요\s*$", re.MULTILINE)
_WRAP_UP_HEADING = re.compile(r"^###\s+정리\s*$", re.MULTILINE)
_PRIMARY_HEADING = re.compile(r"^###\s+\S.*$", re.MULTILINE)
_VISUAL_BLOCK_OPEN = re.compile(r"^:::(key-point|flow|caution)\s*$", re.MULTILINE)
_VISUAL_BLOCK_CLOSE = re.compile(r"^:::\s*$", re.MULTILINE)


MIN_BODY_CHARS = 900  # 이보다 짧으면 얕거나 끊긴 글로 보고 다음 모델 시도

_REVIEW_SCORE_KEYS = (
    "grounding",
    "coverage",
    "coherence",
    "readability",
    "visual_clarity",
)

_REVIEW_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_quality_review",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["pass", "revise"]},
                "scores": {
                    "type": "object",
                    "properties": {
                        key: {"type": "integer", "minimum": 1, "maximum": 5}
                        for key in _REVIEW_SCORE_KEYS
                    },
                    "required": list(_REVIEW_SCORE_KEYS),
                    "additionalProperties": False,
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": [
                                    "evidence",
                                    "coverage",
                                    "coherence",
                                    "readability",
                                    "structure",
                                    "visual",
                                    "diagram",
                                ],
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["major", "minor"],
                            },
                            "description": {"type": "string", "minLength": 1},
                            "suggestion": {"type": "string", "minLength": 1},
                        },
                        "required": [
                            "category",
                            "severity",
                            "description",
                            "suggestion",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["verdict", "scores", "issues"],
            "additionalProperties": False,
        },
    },
}


def _looks_truncated(text: str) -> bool:
    """중간에 끊긴 출력 감지."""
    tail = text.rstrip()
    if not tail:
        return True
    last = tail.split("\n")[-1].strip()
    # 1) 표 구분선(| :--- |)이나 미완성 표 헤더로 끝남 → 데이터 행이 안 온 것
    if re.search(r"\|\s*:?-{2,}", last):
        return True
    # 2) 서술 문장이 끝맺음 없이 뚝 끊김 (표/코드/헤딩/목록 줄은 제외)
    if last and not last.startswith(("#", "|", "-", "*", ">", "`", "!")):
        if not last.endswith((".", "다", "요", "!", "?", ":", ")", "]", "`", "”", "\"")):
            return True
    return False


def output_is_clean_korean(text: str) -> tuple[bool, str]:
    """생성 결과가 외국어 누출 없는 한국어인지 검증."""
    if _JP_KANA.search(text):
        return False, "일본어 가나 포함"
    cjk = _CJK.findall(text)
    if len(cjk) > 5:
        return False, f"한자 과다({len(cjk)}자)"
    return True, "ok"


def output_has_required_structure(text: str) -> tuple[bool, str]:
    """프롬프트의 최소 출력 계약을 지켰는지 검증."""
    stripped = text.lstrip()
    first_line = stripped.partition("\n")[0].strip()
    if not _TITLE_LINE.fullmatch(first_line):
        return False, "첫 줄 제목 누락"

    required = [
        ("한 줄 요약", _SUMMARY_LINE),
        ("개요", _OVERVIEW_HEADING),
        ("정리", _WRAP_UP_HEADING),
    ]
    positions = [0]
    for name, pattern in required:
        matches = list(pattern.finditer(stripped))
        if not matches:
            return False, f"{name} 누락"
        if len(matches) > 1:
            return False, f"{name} 중복"
        positions.append(matches[0].start())
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        return False, "필수 섹션 순서 오류"
    primary_count = len(_PRIMARY_HEADING.findall(stripped))
    if primary_count > 7:
        return False, f"1차 섹션 과다({primary_count}개 > 7개)"

    visual_types = _VISUAL_BLOCK_OPEN.findall(stripped)
    if len(visual_types) > 2:
        return False, f"시각 블록 과다({len(visual_types)}개 > 2개)"
    if len(set(visual_types)) != len(visual_types):
        return False, "같은 시각 블록 중복"
    if len(_VISUAL_BLOCK_CLOSE.findall(stripped)) != len(visual_types):
        return False, "시각 블록 닫힘 오류"
    return True, "ok"


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


def _parse_review_json(content: str) -> dict:
    """구조화 출력의 검수 JSON을 파싱하고 최소 계약을 확인."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("검수 JSON 본문이 비어 있음")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        result = json.loads(stripped)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"검수 JSON 파싱 실패: {exc}") from exc

    if result.get("verdict") not in {"pass", "revise"}:
        raise ValueError("검수 verdict 누락 또는 오류")
    scores = result.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("검수 scores 누락")
    for key in _REVIEW_SCORE_KEYS:
        value = scores.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
            raise ValueError(f"검수 점수 오류: {key}")
    issues = result.get("issues")
    if not isinstance(issues, list):
        raise ValueError("검수 issues 누락")
    valid_categories = {
        "evidence",
        "coverage",
        "coherence",
        "readability",
        "structure",
        "visual",
        "diagram",
    }
    for issue in issues:
        if not isinstance(issue, dict):
            raise ValueError("검수 issue 형식 오류")
        if issue.get("category") not in valid_categories:
            raise ValueError("검수 issue category 오류")
        if issue.get("severity") not in {"major", "minor"}:
            raise ValueError("검수 issue severity 오류")
        if not str(issue.get("description", "")).strip():
            raise ValueError("검수 issue description 누락")
        if not str(issue.get("suggestion", "")).strip():
            raise ValueError("검수 issue suggestion 누락")

    score_issue_categories = {
        "grounding": {"evidence"},
        "coverage": {"coverage"},
        "coherence": {"coherence", "structure"},
        "readability": {"readability", "structure"},
        "visual_clarity": {"visual", "diagram"},
    }
    for key, categories in score_issue_categories.items():
        if scores[key] <= 3 and not any(
            issue["category"] in categories for issue in issues
        ):
            raise ValueError(f"낮은 점수에 대응하는 issue 누락: {key}")

    must_revise = (
        any(scores[key] <= 3 for key in _REVIEW_SCORE_KEYS)
        or any(issue["severity"] == "major" for issue in issues)
    )
    if must_revise:
        result["verdict"] = "revise"
    if result["verdict"] == "revise" and not issues:
        raise ValueError("수정 판정에 구체적인 issue가 없음")
    return result

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class LLMError(RuntimeError):
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


def build_fallback_chain(prefer: list[str], exclude: list[str],
                         seed: list[str] | None = None) -> list[str]:
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


def generate(system_prompt: str, user_prompt: str, model_fallback: list[str],
             purpose: str = "글 생성") -> tuple[str, str]:
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
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload,
                                     timeout=(10, 300))
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
                print(f"  [스킵] {model} — 본문 {len(content)}자로 너무 짧음, 다음 모델로")
                continue
            if _looks_truncated(content):
                errors.append(f"{model}: 잘린 출력 의심")
                print(f"  [스킵] {model} — 출력이 중간에 끊긴 듯, 다음 모델로")
                continue
            return content, model

        # 체인 한 바퀴 실패. rate limit이 많으면 기다렸다 재시도(작은 모델로 안 떨어짐).
        all_errors = errors
        rate_limited = sum(1 for e in errors if "http_429" in e)
        if rnd < max_rounds - 1 and rate_limited >= max(1, len(model_fallback) // 2):
            print(f"  대부분 rate limit — {wait_seconds}초 대기 후 재시도 (round {rnd + 2}/{max_rounds})")
            time.sleep(wait_seconds)
            continue
        break

    raise LLMError("모든 모델 실패:\n" + "\n".join(all_errors))


def review(system_prompt: str, user_prompt: str, model_fallback: list[str],
           max_tokens: int = 4000,
           reasoning_tokens: int = 1200) -> tuple[dict, str]:
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
            "response_format": _REVIEW_RESPONSE_FORMAT,
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
            result = _parse_review_json(content)
        except (ValueError, TypeError) as exc:
            errors.append(f"{model}: parse_error {exc}")
            print(f"  [검수 재시도] {model} — {exc}")
            continue
        return result, model

    raise LLMError("모든 검수 모델 실패:\n" + "\n".join(errors))
