"""전달·값 변화·펼치기와 비교 실험 경로의 계약. 도메인별 실행 코드는 없다."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def _identifier(value, field):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{field}: 유효한 ID가 필요함")
    return value


def _label(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 40:
        raise ValueError(f"{field}: 1~40자의 읽을 수 있는 이름이 필요함")
    # The renderer must use textContent, not interpret this string as HTML.
    return value.strip()


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label}: 필드 오류")


def _graph(scene):
    states = scene.get("states")
    if not isinstance(states, list) or not states:
        raise ValueError("전달 동작에는 상태 목록이 필요함")
    by_id = {}
    edges = set()
    entities = []
    for state in states:
        if not isinstance(state, dict):
            raise ValueError("전달 동작의 상태 필드 오류")
        sid = _identifier(state.get("id"), "상태 ID")
        if sid in by_id:
            raise ValueError("전달 동작의 상태 ID 중복")
        by_id[sid] = state
        actions = state.get("actions")
        if not isinstance(actions, list):
            raise ValueError("전달 동작의 버튼 목록 오류")
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError("전달 동작의 버튼 필드 오류")
            edges.add((sid, _identifier(action.get("target"), "버튼 대상")))
        fragment = state.get("html")
        if not isinstance(fragment, str):
            raise ValueError("전달 동작의 상태 HTML 오류")
        entities.append(
            {
                str(tag["data-entity"])
                for tag in BeautifulSoup(fragment, "html.parser").select(
                    "[data-entity]"
                )
                if tag.get_text(strip=True)
            }
        )
    initial = _identifier(scene.get("initial"), "초기 상태")
    if initial not in by_id or any(target not in by_id for _, target in edges):
        raise ValueError("전달 동작의 상태 또는 버튼 대상이 존재하지 않음")
    return by_id, edges, set.intersection(*entities)


def validate_scene_motion(scene: dict) -> None:
    """안전하게 정제된 장면의 선택적 전이/시나리오를 검사한다.

    CSS를 통한 실제 가시성/이동 거리는 브라우저 검사 책임이다. 여기서는
    모든 상태의 읽을 수 있는 추적 표식, 실제 버튼 경로와 실행 상한을 검사한다.
    구형 장면은 필드가 없어도 허용한다.
    """
    if not isinstance(scene, dict):
        raise ValueError("장면 필드 오류")
    if not {"transitions", "effects", "scenarios"}.intersection(scene):
        return
    states, edges, anchors = _graph(scene)
    transitions = scene.get("transitions", [])
    if not isinstance(transitions, list) or len(transitions) > 32:
        raise ValueError("전달 전이는 최대 32개 목록이어야 함")
    seen_edges = set()
    for index, transition in enumerate(transitions):
        prefix = f"transitions[{index}]"
        _object(transition, {"from", "to", "steps"}, prefix)
        before = _identifier(transition["from"], f"{prefix}.from")
        after = _identifier(transition["to"], f"{prefix}.to")
        edge = (before, after)
        if before == after or edge not in edges or edge in seen_edges:
            raise ValueError(f"{prefix}: 중복/자기 전이 또는 실제 버튼에 없는 경로")
        seen_edges.add(edge)
        steps = transition["steps"]
        if not isinstance(steps, list) or not 1 <= len(steps) <= 4:
            raise ValueError(f"{prefix}.steps: 전달 단계는 1~4개 필요")
        duration = 0
        for step_index, step in enumerate(steps):
            step_prefix = f"{prefix}.steps[{step_index}]"
            required = {"source", "target", "label", "duration_ms"}
            if not isinstance(step, dict) or set(step) - {"kind"} != required:
                raise ValueError(f"{step_prefix}: 필드 오류")
            if "kind" in step and step["kind"] not in ("signal", "message"):
                raise ValueError(f"{step_prefix}.kind: signal 또는 message 필요")
            source = _identifier(step["source"], f"{step_prefix}.source")
            target = _identifier(step["target"], f"{step_prefix}.target")
            if source == target or source not in anchors or target not in anchors:
                raise ValueError(
                    f"{step_prefix}: 서로 다른 두 전달 표식이 모든 상태에 필요함"
                )
            _label(step["label"], f"{step_prefix}.label")
            milliseconds = step["duration_ms"]
            if type(milliseconds) is not int or not 600 <= milliseconds <= 2400:
                raise ValueError(f"{step_prefix}.duration_ms: 정수 600~2400ms 필요")
            duration += milliseconds
        if duration > 8000:
            raise ValueError(f"{prefix}: 전달 단계의 합계는 8000ms 이하")

    effects = scene.get("effects", [])
    if not isinstance(effects, list) or len(effects) > 32:
        raise ValueError("상태 효과는 최대 32개 목록이어야 함")
    texts = {
        sid: {
            str(tag["data-entity"]): " ".join(tag.get_text(" ", strip=True).split())
            for tag in BeautifulSoup(state["html"], "html.parser").select(
                "[data-entity]"
            )
        }
        for sid, state in states.items()
    }
    for index, effect in enumerate(effects):
        prefix = f"effects[{index}]"
        _object(effect, {"from", "to", "kind", "entities", "duration_ms"}, prefix)
        before = _identifier(effect["from"], f"{prefix}.from")
        after = _identifier(effect["to"], f"{prefix}.to")
        edge = (before, after)
        if before == after or edge not in edges or edge in seen_edges:
            raise ValueError(f"{prefix}: 중복/자기 전이 또는 실제 버튼에 없는 경로")
        seen_edges.add(edge)
        if effect["kind"] not in ("compare", "transform", "reveal"):
            raise ValueError(f"{prefix}.kind: compare, transform 또는 reveal 필요")
        entities = effect["entities"]
        if not isinstance(entities, list) or not 1 <= len(entities) <= 6:
            raise ValueError(f"{prefix}.entities: 변화하는 표식 1~6개 필요")
        identifiers = [_identifier(entity, f"{prefix}.entities") for entity in entities]
        if len(set(identifiers)) != len(identifiers) or not set(identifiers) <= anchors:
            raise ValueError(
                f"{prefix}.entities: 중복 없는 읽을 수 있는 표식이 모든 상태에 필요함"
            )
        for entity in identifiers:
            old, new = texts[before][entity], texts[after][entity]
            if old == new:
                raise ValueError(
                    f"{prefix}.entities: {entity}의 실제 내용 변화 필요 (색상만 변경 금지)"
                )
            if effect["kind"] == "reveal" and len(old) == len(new):
                raise ValueError(
                    f"{prefix}.entities: reveal은 펼치거나 접을 내용 분량 변화 필요"
                )
        duration = effect["duration_ms"]
        if type(duration) is not int or not 600 <= duration <= 2400:
            raise ValueError(f"{prefix}.duration_ms: 정수 600~2400ms 필요")

    if "scenarios" not in scene:
        return
    scenarios = scene["scenarios"]
    if not isinstance(scenarios, list) or not 2 <= len(scenarios) <= 3:
        raise ValueError("비교 시나리오는 2~3개 필요")
    seen_ids = set()
    seen_labels = set()
    seen_routes = set()
    for index, scenario in enumerate(scenarios):
        prefix = f"scenarios[{index}]"
        _object(scenario, {"id", "label", "steps"}, prefix)
        sid = _identifier(scenario["id"], f"{prefix}.id")
        label = _label(scenario["label"], f"{prefix}.label")
        if sid in seen_ids or label in seen_labels:
            raise ValueError(f"{prefix}: 시나리오 ID 또는 이름 중복")
        seen_ids.add(sid)
        seen_labels.add(label)
        steps = scenario["steps"]
        if (
            not isinstance(steps, list)
            or not 2 <= len(steps) <= 8
            or not all(isinstance(step, str) and step in states for step in steps)
            or len(set(steps)) != len(steps)
            or steps[0] != scene["initial"]
        ):
            raise ValueError(f"{prefix}.steps: 초기 상태에서 시작하는 단순 경로 필요")
        route_edges = frozenset(zip(steps, steps[1:]))
        if not route_edges.issubset(edges):
            raise ValueError(f"{prefix}.steps: 실제 버튼 전이와 불일치")
        if route_edges in seen_routes:
            raise ValueError(f"{prefix}.steps: 이름만 다른 동일한 시나리오 경로")
        seen_routes.add(route_edges)


def interaction_issues(design: dict) -> list[dict]:
    """새 자동 생성물에 연속 변화 + 비교 가능한 조작을 요구하는 선택적 게이트.

    적어도 한 장면이 통과하면 정적인 보조 그림은 허용한다. 필수 장면은
    시나리오/실제 분기와 그 경로의 전달 또는 상태 효과를 갖춰야 하며, 단순 테두리
    변경이나 같은 경로의 이름 변경을 인터랙션으로 세지 않는다.
    """
    issues = []
    for index, scene in enumerate(design.get("scenes", [])):
        if not isinstance(scene, dict):
            continue  # The schema checker supplies the structural error.
        states = scene.get("states")
        if not isinstance(states, list) or len(states) <= 1:
            continue

        def issue(field, message):
            issues.append(
                {
                    "kind": "interaction",
                    "scene_index": index,
                    "path": f"scenes[{index}].{field}",
                    "message": message,
                }
            )

        try:
            validate_scene_motion(scene)
            by_id, edges, _ = _graph(scene)
        except ValueError as exc:
            issue(
                "effects" if str(exc).startswith("effects[") else "transitions",
                str(exc),
            )
            continue
        scene_issue_count = len(issues)
        transitions = scene.get("transitions", [])
        effects = scene.get("effects", [])
        if not transitions and not effects:
            issue(
                "transitions",
                "색상/완성 화면 교체만으로는 부족함: 실제 전달 동작 또는 내용이 변하는 비교/변환/펼치기 효과 필요",
            )
        branch_edges = {
            (sid, target)
            for sid, state in by_id.items()
            if len({action["target"] for action in state["actions"]} - {sid}) >= 2
            for target in {action["target"] for action in state["actions"]} - {sid}
        }
        scenarios = scene.get("scenarios", [])
        if not scenarios and not branch_edges:
            issue(
                "scenarios",
                "단일 경로 재생만으로는 부족함: 결과를 비교할 서로 다른 시나리오 2개 또는 실제 분기 버튼 필요",
            )
        playback = scene.get("playback")
        steps = playback.get("steps") if isinstance(playback, dict) else None
        if (
            not isinstance(steps, list)
            or not 2 <= len(steps) <= 8
            or not all(isinstance(step, str) and step in by_id for step in steps)
            or len(set(steps)) != len(steps)
            or steps[0] != scene["initial"]
            or any(edge not in edges for edge in zip(steps, steps[1:]))
        ):
            issue(
                "playback.steps",
                "첫 화면부터 재생할 수 있도록 초기 상태에서 시작하는 실제 자동 재생 경로 필요",
            )
        elif scenarios and steps not in [scenario["steps"] for scenario in scenarios]:
            issue(
                "playback.steps",
                "기본 자동 재생 경로는 제공된 비교 시나리오 중 하나와 일치해야 함",
            )
        supported = {(item["from"], item["to"]) for item in transitions + effects}
        # Every offered action remains clickable even when it is not part of the
        # selected scenario. An off-scenario edge must not fall back to a text swap.
        missing = sorted(edges - supported)
        if (transitions or effects) and missing:
            issue(
                "effects" if effects and not transitions else "transitions",
                "제공된 버튼 경로의 전달 또는 상태 효과 누락: "
                + ", ".join(f"{before} → {after}" for before, after in missing),
            )
        if len(issues) == scene_issue_count:
            return []
    return issues or [
        {
            "kind": "interaction",
            "scene_index": None,
            "path": "scenes",
            "message": "정적 그림만으로는 부족함: 연속 변화와 비교 가능한 시나리오/분기가 있는 장면 1개 필요",
        }
    ]
