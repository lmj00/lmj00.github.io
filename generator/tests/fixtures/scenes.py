"""Reusable fictional inputs and test doubles; never test cases."""

from __future__ import annotations

import html


from generator.tests.fixtures.design import design_candidate


def clarity_scene():
    scene = effect_scene()
    scene["title"] = "가상 라벨 규칙: 추가된 값만 비교하기"
    scene["interaction_mode"] = "compare"
    choices = [
        ("team", "team 라벨 추가", '{team: "demo"}'),
        ("env", "env 라벨 추가", '{env: "test"}'),
    ]
    scene["initial"] = "ready"
    scene["states"] = [
        {
            "id": sid,
            "html": '<div class="board"><div class="policy"><span data-icon="document"></span><p>namespace</p><code data-entity="namespace">dev</code></div>'
            f'<div class="result"><p>labels</p><code data-entity="labels">{html.escape(value)}</code></div></div>',
            "description": "아래 원본과 변경된 필드를 비교하세요."
            if sid != "ready"
            else "추가할 라벨을 선택하세요. namespace는 바뀌지 않습니다.",
            "actions": [
                {"label": label, "target": target} for target, label, _ in choices
            ]
            if sid == "ready"
            else [],
        }
        for sid, value in [
            ("ready", "{}"),
            *((target, value) for target, _, value in choices),
        ]
    ]
    scene["effects"] = [
        {
            "from": "ready",
            "to": target,
            "kind": "compare",
            "entities": ["labels"],
            "duration_ms": 900,
        }
        for target, _, _ in choices
    ]
    scene["scenarios"] = [
        {"id": target, "label": label, "steps": ["ready", target]}
        for target, label, _ in choices
    ]
    scene["playback"] = {"steps": ["ready", "team"], "interval_ms": 2000}
    scene["explanation"]["key_entities"] = ["namespace", "labels"]
    scene["change_explanations"] = [
        {
            "from": "ready",
            "to": target,
            "reason": f"가상 {target} 규칙은 빈 labels에 선택한 라벨을 추가합니다.",
            "changes": [
                {"entity": "labels", "label": "labels", "before": "{}", "after": value}
            ],
            "invariants": [
                {"entity": "namespace", "label": "namespace", "value": "dev"}
            ],
        }
        for target, _, value in choices
    ]
    return scene


def multi_change_scene():
    """Three exact fields, with descriptive placeholders before numeric data."""
    scene = clarity_scene()
    for state in scene["states"]:
        sid = state["id"]
        name, kind, value = {
            "ready": ("—", "—", "0"),
            "team": ("demo", "A", "3"),
            "env": ("test", "B", "1"),
        }[sid]
        state["html"] += (
            f'<p>name <code data-entity="name">{name}</code></p>'
            f'<p>kind <code data-entity="kind">{kind}</code></p>'
            f'<p>value <code data-entity="value">{value}</code></p>'
        )
    for edge in scene["change_explanations"]:
        target = edge["to"]
        name, kind, value = (
            ("demo", "A", "3") if target == "team" else ("test", "B", "1")
        )
        edge["changes"] = [
            {"entity": "name", "label": "name", "before": "—", "after": name},
            {"entity": "kind", "label": "kind", "before": "—", "after": kind},
            {"entity": "value", "label": "value", "before": "0", "after": value},
        ]
    for effect in scene["effects"]:
        effect["entities"] += ["name", "kind", "value"]
    return scene


def continuous_candidate():
    value = design_candidate()
    scene = value["scenes"][0]
    scene["title"] = "가상 전달 모형: 성공 응답과 거절 응답"
    scene["explanation"]["key_entities"] = ["sender", "relay", "receiver"]
    scene["css"] = (
        ".scene-content .board {display:grid;grid-template-columns:repeat(3,1fr);"
        "gap:12px;padding:20px 0;color:#d6dae0;font-size:14px}"
        ".scene-content .node {min-width:0;padding:12px 5px;border:1px solid #555;"
        "border-radius:8px;text-align:center;overflow-wrap:anywhere}"
        ".scene-content .result {grid-column:1/-1;padding:16px 0;font-size:15px}"
    )

    def state(sid, message, actions):
        return {
            "id": sid,
            "html": (
                '<div class="board">'
                '<div class="node" data-entity="sender">요청자</div>'
                '<div class="node" data-entity="relay">중계자</div>'
                '<div class="node" data-entity="receiver">처리자</div>'
                f'<p class="result">{message}</p></div>'
            ),
            "description": message,
            "actions": [
                {"label": label, "target": target} for label, target in actions
            ],
        }

    scene["initial"] = "ready"
    scene["states"] = [
        state(
            "ready",
            "아직 메시지를 보내지 않았다.",
            [("정상 전달", "delivered"), ("거절 응답", "lost")],
        ),
        state(
            "delivered",
            "처리자가 받았지만 응답하지 않았다.",
            [("처리 확인 보내기", "confirmed")],
        ),
        state("confirmed", "중계자가 처리자의 완료 응답을 받았다.", []),
        state(
            "lost",
            "이 가상 모형에서는 중계자가 요청을 거절한다.",
            [("거절 전달", "returned")],
        ),
        state("returned", "요청자에게 거절 응답을 전달했다.", []),
    ]

    def step(source, target, label):
        return {"source": source, "target": target, "label": label, "duration_ms": 1000}

    scene["transitions"] = [
        {
            "from": "ready",
            "to": "delivered",
            "steps": [
                step("sender", "relay", "메시지"),
                step("relay", "receiver", "전달"),
            ],
        },
        {
            "from": "delivered",
            "to": "confirmed",
            "steps": [step("receiver", "relay", "처리 확인")],
        },
        {
            "from": "ready",
            "to": "lost",
            "steps": [step("sender", "relay", "메시지")],
        },
        {
            "from": "lost",
            "to": "returned",
            "steps": [step("relay", "sender", "거절 응답")],
        },
    ]
    scene["playback"] = {
        "steps": ["ready", "delivered", "confirmed"],
        "interval_ms": 3000,
    }
    scene["scenarios"] = [
        {
            "id": "normal",
            "label": "정상 처리",
            "steps": ["ready", "delivered", "confirmed"],
        },
        {
            "id": "disconnect",
            "label": "거절 응답",
            "steps": ["ready", "lost", "returned"],
        },
    ]
    return value


def diagram_candidate(layout="flow"):
    value = continuous_candidate()
    scene = value["scenes"][0]
    entities = ["sender", "relay", "receiver"]
    if layout == "branch":
        entities.append("alternate")
    scene["explanation"]["key_entities"] = entities
    pairs = [(0, 1), (1, 2)] + ([(1, 3)] if layout == "branch" else [])
    scene["presentation"] = {
        "layout": layout,
        "eyebrow": "REQUEST TRACE",
        "links": [
            {"source": entities[a], "target": entities[b], "label": "전달"}
            for a, b in pairs
        ],
    }
    for state in scene["states"]:
        state["html"] = (
            '<div class="diagram-board">'
            + "".join(diagram_node(entity, detail=state["id"]) for entity in entities)
            + '</div><div class="diagram-ledger"><div><span>결과</span>'
            + f"<strong>{state['description']}</strong></div></div>"
        )
    scene["transitions"][0]["steps"][0]["kind"] = "signal"
    return value


def compact_panels_scene():
    scene = multi_change_scene()
    scene["css"] += (
        ".scene-content .board{padding:0;gap:8px}"
        ".scene-content .policy,.scene-content .result{padding:8px}"
        ".scene-content p{margin:0}"
    )
    return scene


def numeric_scene(kind="line", mode="compare"):
    """Fictional request measurements, not Prometheus facts or real telemetry."""
    return {
        "interaction_mode": mode,
        "initial": "counter",
        "states": [
            {
                "id": state,
                "html": f'<section><div data-entity="measure">선택한 설명용 수치: {label}</div></section>',
            }
            for state, label in [
                ("counter", "누적 완료 0 → 1 → 2"),
                ("gauge", "진행 중 0 → 1 → 0"),
            ]
        ],
        "charts": [
            {
                "entity": "measure",
                "kind": kind,
                "label": "같은 세 관측 지점에서 비교하는 서로 다른 값",
                "caption": "설명용 가상 수치이며 실제 측정값이 아닙니다.",
                "unit": "요청 수",
                "labels": ["관측 시작", "첫 요청 완료", "두 번째 요청 완료"],
                "series": [
                    {
                        "id": "count",
                        "label": "누적 완료 요청",
                        "values": [0, 1, 2],
                        "tone": "blue",
                    },
                    {
                        "id": "current",
                        "label": "현재 진행 중인 요청",
                        "values": [0, 1, 0],
                        "tone": "amber",
                    },
                ],
                "views": [
                    {
                        "state": "counter",
                        "active_series": ["count"],
                        "visible_points": 3,
                    },
                    {
                        "state": "gauge",
                        "active_series": ["current"],
                        "visible_points": 3,
                    },
                ],
            }
        ],
    }


def effect_scene():
    """A fictional policy workbench, deliberately not a message diagram."""
    scene = motion_scene()
    scene.pop("transitions")
    scene["title"] = "정책 실험: 조건과 결과를 나란히 읽기"
    scene["css"] = (
        ".scene-content .board {display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:18px 0}"
        ".scene-content .policy {padding:14px;background:#0c0e12;border-radius:8px;min-width:0}"
        ".scene-content .result {padding:14px;background:#202d3d;border-radius:8px;min-width:0}"
        ".scene-content code {font:14px ui-monospace,monospace}"
        "@media(max-width:560px){.scene-content .board {grid-template-columns:1fr}}"
    )
    results = {
        "ready": "판정 전: 조건을 선택하세요.",
        "accepted": "허용: 예시 정책의 조건을 충족했습니다.",
        "encoded": "변환 결과: true → 허용 (예시 데이터)",
        "expanded": "<p>세부 규칙을 펼쳤습니다.</p><p>규칙 A: 이 가상 모형에서는 조건이 참이면 허용합니다.</p><p>규칙 B: 실제 시스템의 보안 정책이나 실행 결과를 재현하지 않습니다.</p>",
    }
    labels = {"accepted": "조건 적용", "encoded": "값 변환", "expanded": "규칙 펼치기"}
    scene["states"] = [
        {
            "id": sid,
            "html": '<div class="board"><div class="policy" data-entity="policy">'
            '<span data-icon="document"></span><strong>예시 정책</strong>'
            "<p>조건과 결과를 비교합니다.</p><code>condition: true</code></div>"
            f'<div class="result" data-entity="result">{result}</div></div>',
            "description": "실제 시스템에 연결하지 않는 가상 정책 실험입니다.",
            "actions": (
                [{"label": label, "target": target} for target, label in labels.items()]
                if sid == "ready"
                else []
            ),
        }
        for sid, result in results.items()
    ]
    scene["effects"] = [
        {
            "from": "ready",
            "to": target,
            "kind": kind,
            "entities": ["result"],
            "duration_ms": 1200,
        }
        for target, kind in (
            ("accepted", "compare"),
            ("encoded", "transform"),
            ("expanded", "reveal"),
        )
    ]
    scene["scenarios"] = [
        {"id": target, "label": label, "steps": ["ready", target]}
        for target, label in labels.items()
    ]
    scene["playback"] = {"steps": ["ready", "accepted"], "interval_ms": 2000}
    scene["explanation"]["key_entities"] = ["policy", "result"]
    return scene


MOTION_BODY = "### 요청 처리\n\n조건에 따른 처리 결과를 비교한다.\n\n### 보조 설명\n\n부가 설명이다."


def motion_scene():
    def state(sid, description, actions):
        return {
            "id": sid,
            "html": (
                '<div class="board"><p data-entity="source">보내는 쪽</p>'
                '<p data-entity="destination">받는 쪽</p>'
                f'<p data-entity="result">{description}</p></div>'
            ),
            "description": description,
            "actions": actions,
        }

    def transfer(target):
        return {
            "from": "ready",
            "to": target,
            "steps": [
                {
                    "source": "source",
                    "target": "destination",
                    "label": "요청 전달",
                    "duration_ms": 1200,
                }
            ],
        }

    return {
        "title": "조건에 따른 요청 처리 비교",
        "after_heading": "요청 처리",
        "caption": "설명용 전달 과정이며 실제 시스템이나 측정 시간과 무관하다.",
        "css": ".scene-content .board {display:grid;gap:20px}",
        "initial": "ready",
        "playback": {"steps": ["ready", "accepted"], "interval_ms": 2000},
        "states": [
            state(
                "ready",
                "처리 전",
                [
                    {"label": "조건 충족", "target": "accepted"},
                    {"label": "조건 미충족", "target": "rejected"},
                ],
            ),
            state("accepted", "수락됨", []),
            state("rejected", "거절됨", []),
        ],
        "transitions": [transfer("accepted"), transfer("rejected")],
        "scenarios": [
            {"id": "accept", "label": "조건 충족", "steps": ["ready", "accepted"]},
            {"id": "reject", "label": "조건 미충족", "steps": ["ready", "rejected"]},
        ],
        "explanation": {
            "mode": "interactive",
            "learning_goal": "조건이 달라지면 결과가 어떻게 달라지는가?",
            "reader_action": "조건을 선택해서 비교한다.",
            "observable_change": "요청 전달 후 결과가 수락 또는 거절로 바뀐다.",
            "takeaway": "조건에 따라 처리 결과가 다르다.",
            "assumptions": [],
            "key_entities": ["source", "destination", "result"],
            "evidence": [{"source_url": "https://example.test", "quote": "조건 비교"}],
        },
    }


def motion_design(scene=None):
    return {"summary": "조건 비교", "scenes": [scene or motion_scene()]}


def diagram_node(entity, icon="server", *, detail="대기", modifier=""):
    classes = "diagram-node" + (f" {modifier}" if modifier else "")
    return (
        f'<section class="{classes}" data-entity="{entity}">'
        '<span class="diagram-role">처리 주체</span>'
        f'<span class="diagram-symbol" data-icon="{icon}"></span>'
        f'<strong class="diagram-label">{entity}</strong>'
        f'<span class="diagram-detail">{detail}</span></section>'
    )


def presentation_scene(layout="flow", count=3):
    entities = ["sender", "hub", "primary", "secondary"][:count]
    pairs = (
        [(0, 1), (1, 2), (1, 3)]
        if layout == "branch"
        else list(zip(range(count), range(1, count)))
    )
    html = (
        '<div class="diagram-board">' + "".join(map(diagram_node, entities)) + "</div>"
    )
    return {
        "presentation": {
            "layout": layout,
            "eyebrow": "요청의 처리 경로",
            "links": [
                {"source": entities[a], "target": entities[b], "label": "요청"}
                for a, b in pairs
            ],
        },
        "states": [{"html": html}, {"html": html.replace("대기", "완료")}],
    }
