"""설명 계획과 생성 장면의 기계적 일관성 검사. 의미의 타당성은 독립 검수한다."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from generator.design.visual_contracts import EXPLANATION_SCHEMA


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class EvidenceMismatch(ValueError):
    """구조는 유효하지만 원문에 없는 인용. 부분 수정할 정확한 위치를 보존한다."""

    def __init__(self, issues: list[dict]):
        self.issues = issues
        paths = ", ".join(issue["path"] for issue in issues)
        super().__init__(f"설명 계획 근거가 제공된 공식 원문과 일치하지 않음: {paths}")


def find_evidence_issues(design: dict, sections: list[dict]) -> list[dict]:
    """인용 대조만 수행한다. 빈 목록은 화면 구조/의미 검수 통과를 뜻하지 않는다."""
    documents = {}
    for section in sections:
        documents.setdefault(section["url"], []).append(_normalized(section["content"]))
    issues = []
    for index, scene in enumerate(design["scenes"]):
        for evidence_index, evidence in enumerate(scene["explanation"]["evidence"]):
            quote = _normalized(evidence["quote"])
            if not quote or not any(
                quote in text for text in documents.get(evidence["source_url"], [])
            ):
                issues.append(
                    {
                        "scene_index": index,
                        "evidence_index": evidence_index,
                        "path": f"scenes[{index}].explanation.evidence[{evidence_index}]",
                        **evidence,
                    }
                )
    return issues


def collect_explanation_issues(design: dict, sections: list[dict]) -> list[dict]:
    """안전하게 검사 가능한 모든 장면/상태의 설명 오류를 한 번에 수집한다."""
    issues = []
    for index, scene in enumerate(design["scenes"]):
        if not isinstance(scene, dict):
            continue  # Outer scene schema validation reports this.
        plan = scene.get("explanation")
        prefix = f"scenes[{index}].explanation"

        def add(kind, path, message, **details):
            issues.append(
                {
                    "kind": kind,
                    "scene_index": index,
                    "path": path,
                    "message": message,
                    **details,
                }
            )

        errors = list(Draft202012Validator(EXPLANATION_SCHEMA).iter_errors(plan))
        if errors:
            for error in errors:
                add(
                    "explanation",
                    prefix + error.json_path[1:],
                    f"explanation 설명 계획 오류 ({error.validator})",
                )
            continue
        for field in (
            "learning_goal",
            "reader_action",
            "observable_change",
            "takeaway",
        ):
            if not plan[field].strip():
                add("explanation", f"{prefix}.{field}", f"{field}가 비어 있음")
        entities = plan["key_entities"]
        if len(set(entities)) != len(entities):
            add("explanation", f"{prefix}.key_entities", "key_entities 중복")
        for issue in find_evidence_issues({"scenes": [scene]}, sections):
            issues.append(
                {
                    **issue,
                    "kind": "evidence",
                    "scene_index": index,
                    "path": f"{prefix}.evidence[{issue['evidence_index']}]",
                    "message": "인용이 제공된 공식 원문과 일치하지 않음",
                }
            )
        states = scene.get("states")
        if not isinstance(states, list):
            continue
        interactive = len(states) > 1
        if (plan["mode"] == "interactive") != interactive:
            add("explanation", f"{prefix}.mode", "mode와 실제 상태 개수 불일치")
        fingerprints = {}
        for state_index, state in enumerate(states):
            if not isinstance(state, dict) or not isinstance(state.get("html"), str):
                continue
            soup = BeautifulSoup(state["html"], "html.parser")
            present = {
                str(node["data-entity"]) for node in soup.select("[data-entity]")
            }
            if not set(entities) <= present:
                missing = sorted(set(entities) - present)
                add(
                    "missing_entities",
                    f"scenes[{index}].states[{state_index}].html",
                    "추적할 핵심 대상 data-entity 누락: " + ", ".join(missing),
                    state_id=state.get("id"),
                    missing_entities=missing,
                )
            # IDs alone cannot manufacture a visual change. Browser checks also
            # compare rendered pixels, including class-only / hidden changes.
            for node in soup.select("[data-entity]"):
                del node["data-entity"]
            if isinstance(state.get("id"), str):
                fingerprints[state["id"]] = _normalized(str(soup))
        for state_index, state in enumerate(states):
            if not isinstance(state, dict) or not isinstance(
                state.get("actions"), list
            ):
                continue
            for action_index, action in enumerate(state["actions"]):
                if not isinstance(action, dict):
                    continue
                before, after = state.get("id"), action.get("target")
                if not isinstance(before, str) or not isinstance(after, str):
                    continue
                if (
                    before in fingerprints
                    and after in fingerprints
                    and fingerprints[before] == fingerprints[after]
                ):
                    add(
                        "no_visible_change",
                        f"scenes[{index}].states[{state_index}].actions[{action_index}]",
                        f"{before} → {after}: 화면 변화 없는 버튼 전이",
                    )
    return issues


def validate_explanations(design: dict, sections: list[dict]) -> dict:
    """신규 자동 생성에만 필수 적용; 기존 저장 장면의 렌더링은 유지한다."""
    issues = collect_explanation_issues(design, sections)
    if issues:
        if all(issue["kind"] == "evidence" for issue in issues):
            raise EvidenceMismatch(issues)
        raise ValueError(
            "; ".join(f"{issue['path']}: {issue['message']}" for issue in issues)
        )
    checks = [
        {
            "title": scene["title"],
            "mode": scene["explanation"]["mode"],
            "entities": scene["explanation"]["key_entities"],
            "evidence_matched": len(scene["explanation"]["evidence"]),
        }
        for scene in design["scenes"]
    ]
    return {"scenes": checks, "semantic_review_required": True}
