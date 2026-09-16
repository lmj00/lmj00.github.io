"""Check claimed changes against scene HTML; never infer domain facts.

This gate proves text correspondence, not whether a rule is true or CSS makes a
node visible. Independent source review and browser checks still own those jobs.
Legacy scenes without the opt-in fields remain readable.
"""

from __future__ import annotations

from copy import deepcopy

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from generator.design.visual_contracts import SCENE_CHANGE_EXPLANATIONS_SCHEMA


def _text(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def _entities(fragment):
    """Return readable DOM text, excluding explicitly hidden/non-content nodes.

    CSS visibility cannot be established with an HTML parser. The scene's normal
    HTML allowlist rejects these hidden attributes/tags before this gate anyway.
    """
    soup = BeautifulSoup(fragment if isinstance(fragment, str) else "", "html.parser")
    for node in soup.select(
        'script, style, template, noscript, [hidden], [aria-hidden="true"]'
    ):
        node.decompose()
    result, duplicates = {}, set()
    for node in soup.select("[data-entity]"):
        identifier = str(node["data-entity"])
        if identifier in result:
            duplicates.add(identifier)
        result[identifier] = _text(node.get_text(" ", strip=True))
    for identifier in duplicates:
        result.pop(identifier, None)
    return result


def _inspect(design, *, required):
    issues, observations = [], []
    scenes = design.get("scenes", []) if isinstance(design, dict) else []
    if not isinstance(scenes, list):
        return issues, observations  # The ordinary schema owns invalid documents.
    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue

        def issue(field, message):
            issues.append(
                {
                    "kind": "clarity",
                    "scene_index": scene_index,
                    "path": f"scenes[{scene_index}].{field}",
                    "message": message,
                }
            )

        scene_issue_start = len(issues)
        explanation = scene.get("explanation")
        interactive = (
            isinstance(explanation, dict) and explanation.get("mode") == "interactive"
        )
        enforced = (
            required
            and interactive
            or any(
                field in scene for field in ("interaction_mode", "change_explanations")
            )
        )
        states = scene.get("states", [])
        if not isinstance(states, list):
            continue
        by_id = {
            state["id"]: state
            for state in states
            if isinstance(state, dict) and isinstance(state.get("id"), str)
        }
        texts = {sid: _entities(state.get("html")) for sid, state in by_id.items()}
        edges = {}
        for sid, state in by_id.items():
            actions = state.get("actions", [])
            for action in actions if isinstance(actions, list) else []:
                if not isinstance(action, dict):
                    continue
                target = action.get("target")
                if isinstance(target, str) and target != sid:
                    edges.setdefault((sid, target), []).append(
                        _text(action.get("label"))
                    )

        mode = scene.get("interaction_mode")
        if enforced and mode not in ("compare", "process", "explore"):
            issue(
                "interaction_mode",
                "compare, process 또는 explore 조작 방식을 명시해야 함",
            )
        declared = scene.get("change_explanations")
        schema_errors = []
        if declared is not None:
            schema_errors = list(
                Draft202012Validator(SCENE_CHANGE_EXPLANATIONS_SCHEMA).iter_errors(
                    declared
                )
            )
        if enforced and declared is None:
            issue(
                "change_explanations",
                "각 실제 버튼 경로에 구체적인 전후 값·유지 값·이유가 필요함",
            )
        for error in schema_errors:
            suffix = ".".join(str(part) for part in error.absolute_path)
            issue(
                "change_explanations" + (f".{suffix}" if suffix else ""),
                f"변화 설명 형식 오류: {error.message[:500]}",
            )

        records = {}
        if isinstance(declared, list) and not schema_errors:
            effects = {}
            scene_effects = scene.get("effects", [])
            for effect in scene_effects if isinstance(scene_effects, list) else []:
                if (
                    isinstance(effect, dict)
                    and isinstance(effect.get("from"), str)
                    and isinstance(effect.get("to"), str)
                    and isinstance(effect.get("entities"), list)
                ):
                    effects[(effect.get("from"), effect.get("to"))] = effect.get(
                        "entities", []
                    )
            for index, item in enumerate(declared):
                prefix = f"change_explanations[{index}]"
                edge = (item["from"], item["to"])
                if edge in records:
                    issue(prefix, "동일한 버튼 경로의 변화 설명이 중복됨")
                    # Do not expose either duplicate as a verified declaration.
                    records[edge] = None
                    continue
                records[edge] = None
                if edge not in edges or edge[0] not in texts or edge[1] not in texts:
                    issue(
                        prefix, "실제 비자기 버튼 경로와 존재하는 두 상태에 연결해야 함"
                    )
                    continue
                old, new = texts[edge[0]], texts[edge[1]]
                verified_changes, verified_invariants = [], []
                seen_changes, seen_invariants = set(), set()
                for change_index, change in enumerate(item["changes"]):
                    field = f"{prefix}.changes[{change_index}]"
                    entity = change["entity"]
                    before, after = _text(change["before"]), _text(change["after"])
                    key = (entity, _text(change["label"]))
                    if key in seen_changes:
                        issue(field, "같은 대상·이름의 변경 설명이 중복됨")
                    elif not old.get(entity) or not new.get(entity):
                        issue(
                            field,
                            f"{entity}: 두 상태에 중복 없는 읽을 수 있는 data-entity가 필요함",
                        )
                    elif before not in old[entity] or after not in new[entity]:
                        issue(
                            field,
                            f"{entity}: before/after가 해당 상태의 실제 HTML 텍스트에 없음",
                        )
                    elif (
                        before == after
                        or old[entity] == new[entity]
                        or before in new[entity]
                        and after in old[entity]
                    ):
                        issue(
                            field,
                            f"{entity}: 실제 바뀐 값이 필요함; 같은 값 또는 양쪽에 이미 있는 문구는 변경이 아님",
                        )
                    elif edge in effects and entity not in effects[edge]:
                        issue(
                            field,
                            f"{entity}: 변경 설명 대상이 해당 effects.entities와 연결되지 않음",
                        )
                    else:
                        verified_changes.append(deepcopy(change))
                    seen_changes.add(key)
                for invariant_index, invariant in enumerate(item["invariants"]):
                    field = f"{prefix}.invariants[{invariant_index}]"
                    entity, value = invariant["entity"], _text(invariant["value"])
                    key = (entity, _text(invariant["label"]))
                    if key in seen_invariants:
                        issue(field, "같은 대상·이름의 유지 설명이 중복됨")
                    elif not old.get(entity) or not new.get(entity):
                        issue(
                            field,
                            f"{entity}: 두 상태에 중복 없는 읽을 수 있는 data-entity가 필요함",
                        )
                    elif value not in old[entity] or value not in new[entity]:
                        issue(
                            field,
                            f"{entity}: 유지 값이 두 상태의 실제 HTML 텍스트에 모두 있어야 함",
                        )
                    else:
                        verified_invariants.append(deepcopy(invariant))
                    seen_invariants.add(key)
                records[edge] = {
                    "declared_reason": item["reason"],
                    "text_verified_changes": verified_changes,
                    "text_verified_invariants": verified_invariants,
                }
        if enforced and isinstance(declared, list) and not schema_errors:
            for source, target in edges.keys() - records.keys():
                issue(
                    "change_explanations",
                    f"실제 버튼 경로 {source} → {target}의 변화 설명이 누락됨",
                )

        edge_observations = []
        for (source, target), labels in edges.items():
            old, new = texts.get(source, {}), texts.get(target, {})
            entities = sorted(old.keys() | new.keys())
            edge_observations.append(
                {
                    "from": source,
                    "to": target,
                    "action_labels": labels,
                    "entity_dom_text": [
                        {
                            "entity": entity,
                            "before": old.get(entity),
                            "after": new.get(entity),
                        }
                        for entity in entities
                    ],
                    **(records.get((source, target)) or {}),
                }
            )
        observations.append(
            {
                "scene_index": scene_index,
                "title": scene.get("title"),
                "interaction_mode": mode,
                "scope": "DOM text correspondence only; not a factual or CSS-visibility verdict.",
                "action_observations": edge_observations,
                "issues": deepcopy(issues[scene_issue_start:]),
            }
        )
    return issues, observations


def collect_clarity_issues(design: dict, *, required: bool = False) -> list[dict]:
    """Check optional explanation fields, requiring them on new interactive scenes."""
    return _inspect(design, required=required)[0]


def clarity_observations(design: dict) -> list[dict]:
    """Expose actual button/entity text and text-matched claims for source review.

    Declared reasons are model claims, not verified deductions. Original source
    evidence and the independent reviewer must establish correctness and meaning.
    """
    return _inspect(design, required=False)[1]
