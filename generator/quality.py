"""출처·생성문·검수 응답을 판정하는 순수 품질 규칙."""

from __future__ import annotations

import json
import re

_JP_KANA = re.compile(r"[぀-ヿ]")
_CJK = re.compile(r"[一-鿿]")
_TITLE_LINE = re.compile(r"^제목\s*[:：]\s*\S(?:.*\S)?$", re.MULTILINE)
_SUMMARY_LINE = re.compile(r"^>\s*한 줄 요약\s*[:：]\s*\S+", re.MULTILINE)
_OVERVIEW_HEADING = re.compile(r"^###\s+개요\s*$", re.MULTILINE)
_WRAP_UP_HEADING = re.compile(r"^###\s+정리\s*$", re.MULTILINE)
_PRIMARY_HEADING = re.compile(r"^###\s+\S.*$", re.MULTILINE)
_VISUAL_BLOCK_OPEN = re.compile(r"^:::(key-point|flow|caution)\s*$", re.MULTILINE)
_VISUAL_BLOCK_CLOSE = re.compile(r"^:::\s*$", re.MULTILINE)

MIN_BODY_CHARS = 900

REVIEW_SCORE_KEYS = (
    "grounding",
    "coverage",
    "coherence",
    "readability",
    "visual_clarity",
)

REVIEW_RESPONSE_FORMAT = {
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
                        for key in REVIEW_SCORE_KEYS
                    },
                    "required": list(REVIEW_SCORE_KEYS),
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


def extract_title(body: str, fallback: str) -> tuple[str, str]:
    """모델 출력 첫 줄의 제목을 추출하고 본문에서는 제거한다."""
    stripped = body.lstrip()
    first, _, rest = stripped.partition("\n")
    match = re.match(r"^\s*(?:#+\s*)?제목\s*[:：]\s*(.+)$", first.strip())
    if match:
        title = match.group(1).strip().strip('"').strip("'").strip("#").strip()
        if title:
            return title, rest.lstrip("\n")
    return fallback, body


def looks_truncated(text: str) -> bool:
    """중간에 끊긴 출력을 감지한다."""
    tail = text.rstrip()
    if not tail:
        return True
    last = tail.split("\n")[-1].strip()
    if re.search(r"\|\s*:?-{2,}", last):
        return True
    if last and not last.startswith(("#", "|", "-", "*", ">", "`", "!")):
        if not last.endswith((".", "다", "요", "!", "?", ":", ")", "]", "`", "”", '"')):
            return True
    return False


def output_is_clean_korean(text: str) -> tuple[bool, str]:
    """생성 결과가 외국어 누출 없는 한국어인지 검증한다."""
    if _JP_KANA.search(text):
        return False, "일본어 가나 포함"
    cjk = _CJK.findall(text)
    if len(cjk) > 5:
        return False, f"한자 과다({len(cjk)}자)"
    return True, "ok"


def output_has_required_structure(text: str) -> tuple[bool, str]:
    """프롬프트의 최소 출력 계약을 지켰는지 검증한다."""
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


def source_quality(
    fetched: list[dict],
    min_total_chars: int,
    min_substantive_chars: int,
) -> tuple[bool, str]:
    """출처가 설명형 글을 뒷받침할 만큼 충분한지 판정한다."""
    texts = [str(item.get("text", "")).strip() for item in fetched if item.get("ok")]
    total_chars = sum(len(text) for text in texts)
    substantive_chars = sum(
        len(line)
        for text in texts
        for raw_line in text.splitlines()
        if len(line := raw_line.strip()) >= 50
    )
    if total_chars < min_total_chars:
        return False, f"전체 근거 {total_chars}자 < {min_total_chars}자"
    if substantive_chars < min_substantive_chars:
        return False, (
            f"설명형 근거 {substantive_chars}자 < "
            f"{min_substantive_chars}자(색인·목차형 문서 가능성)"
        )
    return True, (f"전체 근거 {total_chars}자 / 설명형 근거 {substantive_chars}자")


def parse_review_json(content: str) -> dict:
    """구조화 출력의 검수 JSON을 파싱하고 최소 계약을 확인한다."""
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

    if not isinstance(result, dict):
        raise ValueError("검수 JSON 최상위 형식은 객체여야 함")
    if result.get("verdict") not in {"pass", "revise"}:
        raise ValueError("검수 verdict 누락 또는 오류")
    scores = result.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("검수 scores 누락")
    for key in REVIEW_SCORE_KEYS:
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

    must_revise = any(scores[key] <= 3 for key in REVIEW_SCORE_KEYS) or any(
        issue["severity"] == "major" for issue in issues
    )
    if must_revise:
        result["verdict"] = "revise"
    if result["verdict"] == "revise" and not issues:
        raise ValueError("수정 판정에 구체적인 issue가 없음")
    return result
