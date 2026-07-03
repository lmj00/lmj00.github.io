"""OpenRouter 무료모델 호출 + fallback 체인."""
from __future__ import annotations

import os
import re
import requests

# 일본어 가나(히라가나·가타카나) = 명백한 언어 누출 신호
_JP_KANA = re.compile(r"[぀-ヿ]")
# 한자(CJK 표의문자) — 현대 한국어 기술 글엔 거의 없음
_CJK = re.compile(r"[一-鿿]")


MIN_BODY_CHARS = 900  # 이보다 짧으면 얕거나 끊긴 글로 보고 다음 모델 시도


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


def generate(system_prompt: str, user_prompt: str, model_fallback: list[str]) -> tuple[str, str]:
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
            # 연결은 빨리 실패시키되, 느린 무료모델의 생성은 넉넉히 기다린다.
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload,
                                 timeout=(10, 300))
        except requests.RequestException as e:
            errors.append(f"{model}: request_error {e}")
            continue
        if resp.status_code != 200:
            errors.append(f"{model}: http_{resp.status_code} {resp.text[:200]}")
            continue
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, ValueError, IndexError) as e:
            errors.append(f"{model}: parse_error {e}")
            continue
        if not content:
            errors.append(f"{model}: empty_content")
            continue
        clean, reason = output_is_clean_korean(content)
        if not clean:
            errors.append(f"{model}: 품질 게이트 탈락({reason})")
            print(f"  [스킵] {model} — {reason}, 다음 모델로")
            continue
        # 너무 짧으면 내용이 얕거나 중간에 끊긴 것 → 다음 모델로
        if len(content) < MIN_BODY_CHARS:
            errors.append(f"{model}: 본문 과소({len(content)}자)")
            print(f"  [스킵] {model} — 본문 {len(content)}자로 너무 짧음, 다음 모델로")
            continue
        # 마크다운 표가 중간에 끊긴 흔적(헤더 구분선 뒤 내용 없음) 감지
        if _looks_truncated(content):
            errors.append(f"{model}: 잘린 출력 의심")
            print(f"  [스킵] {model} — 출력이 중간에 끊긴 듯, 다음 모델로")
            continue
        return content, model

    raise LLMError("모든 무료모델 실패:\n" + "\n".join(errors))
