"""서로 독립적으로 검사 가능한 디자인 오류를 모은다. 발행 검증을 대체하지 않는다."""

from __future__ import annotations

from copy import deepcopy
import json

from jsonschema import Draft202012Validator

from generator.contracts import SceneVerifier
from generator.design.design_quality import collect_explanation_issues
from generator.design.scene_document import (
    clean_css,
    clean_html,
    render_document,
    section_ends,
    validate_design,
)
from generator.design.visual_contracts import DESIGN_SCHEMA


class DesignValidationError(ValueError):
    def __init__(self, design: dict, issues: list[dict]):
        self.design = design
        self.issues = issues
        super().__init__(
            "; ".join(f"{item['path']}: {item['message']}" for item in issues)
        )


def inspect_design(
    raw: str, body: str, sections: list[dict]
) -> tuple[dict, list[dict]]:
    """파싱 불가/루트 구조 오류는 전체 재요청 대상, 위치가 분명하면 장면 수정 대상."""
    if len(raw) > 100000:
        raise ValueError("디자인 응답 크기 제한 초과")
    design = json.loads(raw)
    if not isinstance(design, dict) or set(design) != {"summary", "scenes"}:
        raise ValueError("summary와 scenes가 필요함")
    if not isinstance(design["scenes"], list) or not 1 <= len(design["scenes"]) <= 2:
        raise ValueError("시각화는 1~2개 필요")
    issues = []
    schema_errors = list(Draft202012Validator(DESIGN_SCHEMA).iter_errors(design))
    for error in schema_errors:
        path = list(error.absolute_path)
        index = (
            path[1]
            if len(path) > 1 and path[0] == "scenes" and type(path[1]) is int
            else None
        )
        # Explanation validation below supplies its own detailed paths.
        if len(path) > 2 and path[2] == "explanation":
            continue
        issues.append(
            {
                "kind": "schema",
                "scene_index": index,
                "path": error.json_path,
                "message": f"디자인 필드 오류 ({error.validator})",
            }
        )
    headings = section_ends(body)
    used = set()
    for index, scene in enumerate(design["scenes"]):
        if not isinstance(scene, dict):
            continue

        def add(kind, path, message):
            issues.append(
                {"kind": kind, "scene_index": index, "path": path, "message": message}
            )

        anchor = scene.get("after_heading")
        if isinstance(anchor, str):
            if anchor not in headings or anchor in used:
                add(
                    "placement",
                    f"scenes[{index}].after_heading",
                    f"본문 배치 제목이 없거나 중복됨: {anchor}",
                )
            used.add(anchor)
        safe = True
        if isinstance(scene.get("css"), str):
            try:
                clean_css(scene["css"])
            except ValueError as exc:
                safe = False
                add("css", f"scenes[{index}].css", str(exc))
        if isinstance(scene.get("states"), list):
            for state_index, state in enumerate(scene["states"]):
                if not isinstance(state, dict) or not isinstance(
                    state.get("html"), str
                ):
                    continue
                try:
                    clean_html(state["html"])
                except ValueError as exc:
                    safe = False
                    add("html", f"scenes[{index}].states[{state_index}].html", str(exc))
        # Probe the scene graph independently of article placement. This copy is
        # diagnostic-only; the real candidate still must pass validate_design(body).
        scene_schema = DESIGN_SCHEMA["properties"]["scenes"]["items"]
        if safe and headings and Draft202012Validator(scene_schema).is_valid(scene):
            probe = deepcopy(scene)
            probe["after_heading"] = next(iter(headings))
            try:
                validate_design(
                    json.dumps({"summary": "검사", "scenes": [probe]}), body
                )
            except ValueError as exc:
                add("structure", f"scenes[{index}]", str(exc))
    issues.extend(collect_explanation_issues(design, sections))
    return design, issues


def inspect_scene_browsers(
    design: dict, body: str, verifier: SceneVerifier
) -> tuple[list[str | None], list[dict], list[dict]]:
    """출처/배치 오류와 별개로 안전한 장면만 실행해 화면 오류도 함께 모은다.

    진단용 배치 대체는 원본에 적용하지 않는다. 발행 시 실제 본문 배치와
    출처/설명 검증을 포함한 모든 검사를 별도로 통과해야 한다.
    """
    documents = []
    reports = []
    issues = []
    headings = section_ends(body)
    validator = Draft202012Validator(DESIGN_SCHEMA["properties"]["scenes"]["items"])
    for index, scene in enumerate(design["scenes"]):
        if not headings or not validator.is_valid(scene):
            documents.append(None)
            reports.append(
                {"status": "skipped", "reason": "장면 스키마/본문 구조 오류"}
            )
            continue
        probe = deepcopy(scene)
        probe["after_heading"] = next(iter(headings))
        try:
            safe_scene = validate_design(
                json.dumps({"summary": "검사", "scenes": [probe]}), body
            )["scenes"][0]
        except ValueError as exc:
            documents.append(None)
            reports.append({"status": "skipped", "reason": str(exc)})
            continue
        safe_scene["after_heading"] = scene["after_heading"]
        document = render_document(safe_scene)
        documents.append(document)
        try:
            reports.append(verifier.check(safe_scene, document))
        except ValueError as exc:
            report = {"status": "failed", "reason": str(exc)}
            issue = {
                    "kind": "browser",
                    "scene_index": index,
                    "path": f"scenes[{index}]",
                    "message": str(exc),
            }
            diagnostics = getattr(exc, "layout_diagnostics", None)
            if diagnostics:
                report["layout_diagnostics"] = deepcopy(diagnostics)
                issue["layout_diagnostics"] = deepcopy(diagnostics)
            reports.append(report)
            issues.append(issue)
    return documents, reports, issues
