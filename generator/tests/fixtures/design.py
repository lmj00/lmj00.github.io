"""Reusable fictional inputs and test doubles; never test cases."""

from __future__ import annotations


from generator.design.compact_scenes import compile_compact_design


HEADINGS = {"section_1": "조건 적용", "section_2": "데이터 변환"}


EXCERPTS = [
    {
        "excerpt_id": "source-1-excerpt-1",
        "source_url": "https://example.test/official",
        "quote": "Requests are checked against the configured policy.",
    },
    {
        "excerpt_id": "source-1-excerpt-2",
        "source_url": "https://example.test/official",
        "quote": "The result depends on the input.",
    },
]


COMPACT_BODY = (
    "### 조건 적용\n\n입력에 따른 결과이다.\n\n### 데이터 변환\n\n변환을 비교한다."
)


def compact_design():
    return {
        "summary": "조건에 따른 처리 결과 비교",
        "scenes": [
            {
                "title": "요청 조건과 결과",
                "heading_id": "section_1",
                "caption": "설명용 예시이며 실제 시스템과 연결하지 않는다.",
                "html": (
                    '<section class="policy-card" data-entity="request">'
                    '<span data-icon="server"></span><h3>요청 조건</h3>'
                    "<p>{{condition}}</p><strong>{{result}}</strong></section>"
                ),
                "css": (
                    ".scene-content .policy-card {display:grid;gap:16px;padding:20px}"
                    ".scene-content .is-success {color:#17694c}"
                    ".scene-content .is-error {color:#923624}"
                ),
                "initial": "ready",
                "playback": {"steps": ["ready", "allowed"], "interval_ms": 2000},
                "explanation": {
                    "mode": "interactive",
                    "learning_goal": "조건에 따라 결과가 어떻게 달라지는가?",
                    "reader_action": "조건을 선택한다.",
                    "observable_change": "조건과 결과가 함께 바뀐다.",
                    "takeaway": "같은 요청도 조건에 따라 결과가 다르다.",
                    "assumptions": ["정책 설정은 설명용 예시이다."],
                    "key_entities": ["request"],
                    "excerpt_ids": ["source-1-excerpt-1"],
                },
                "states": [
                    {
                        "id": "ready",
                        "description": "조건을 선택하기 전이다.",
                        "values": [
                            {"binding": "condition", "value": "조건 미정"},
                            {"binding": "result", "value": "대기"},
                        ],
                        "entity_classes": [],
                        "actions": [
                            {"label": "조건 충족", "target": "allowed"},
                            {"label": "조건 미충족", "target": "denied"},
                        ],
                    },
                    {
                        "id": "allowed",
                        "description": "조건이 충족되어 허용된다.",
                        "values": [
                            {"binding": "condition", "value": "조건 충족"},
                            {"binding": "result", "value": "허용"},
                        ],
                        "entity_classes": [
                            {"entity": "request", "classes": ["is-success"]}
                        ],
                        "actions": [],
                    },
                    {
                        "id": "denied",
                        "description": "조건이 충족되지 않아 거절된다.",
                        "values": [
                            {"binding": "condition", "value": "조건 미충족"},
                            {"binding": "result", "value": "거절"},
                        ],
                        "entity_classes": [
                            {"entity": "request", "classes": ["is-error"]}
                        ],
                        "actions": [],
                    },
                ],
                "scenarios": [
                    {"id": "accept", "label": "허용", "steps": ["ready", "allowed"]},
                    {"id": "deny", "label": "거절", "steps": ["ready", "denied"]},
                ],
            }
        ],
    }


DESIGN_BODY = "### 개요\n\n공식문서 설명이다.\n\n### 두 확인의 차이\n\n두 확인은 독립적이다.\n\n### 정리\n\n책임을 구분한다."


def design_candidate():
    return {
        "summary": "확인 전후를 비교하는 독립 상태판",
        "scenes": [
            {
                "title": "확인 상태 비교",
                "after_heading": "두 확인의 차이",
                "caption": "브로커 확인은 소비자 확인과 독립적이다.",
                "explanation": {
                    "mode": "interactive",
                    "learning_goal": "브로커 확인이 소비자 확인까지 뜻하는가?",
                    "reader_action": "브로커 확인 버튼을 누른다.",
                    "observable_change": "브로커만 완료로 바뀌고 소비자는 확인 전이다.",
                    "takeaway": "두 확인은 독립적이다.",
                    "assumptions": [],
                    "key_entities": ["broker"],
                    "evidence": [
                        {
                            "source_url": "https://example.com/docs",
                            "quote": "테스트 공식문서 근거",
                        }
                    ],
                },
                "css": ".scene-content .board { display: grid; gap: 12px; color: #d6dae0; font-size: 15px; }",
                "initial": "start",
                "playback": {"steps": [], "interval_ms": 3000},
                "states": [
                    {
                        "id": "start",
                        "html": '<div class="board"><p data-entity="broker">브로커 확인 전 · 소비자 확인 전</p></div>',
                        "description": "두 확인 전이다.",
                        "actions": [{"label": "브로커 확인", "target": "confirmed"}],
                    },
                    {
                        "id": "confirmed",
                        "html": '<div class="board"><p data-entity="broker">브로커 확인 완료 · 소비자 확인 전</p></div>',
                        "description": "소비자 확인은 바뀌지 않는다.",
                        "actions": [],
                    },
                ],
            }
        ],
    }


def clear_compact_design():
    design = compact_design()
    scene = design["scenes"][0]
    scene["interaction_mode"] = "compare"
    scene["html"] = (
        '<section class="policy-card"><div data-entity="original">'
        "<h4>원본 요청</h4><code>app: demo-api | labels: {}</code></div>"
        '<div data-entity="request"><h4>처리 결과</h4>'
        "<code>{{labels}}</code><p>{{result}}</p></div></section>"
    )
    for state, labels, result in zip(
        scene["states"],
        ("labels: {}", "labels: {team: demo}", "labels: {}"),
        ("검사 전", "허용", "거절"),
    ):
        state["values"] = [
            {"binding": "labels", "value": labels},
            {"binding": "result", "value": result},
        ]
    scene["effects"] = [
        {
            "from": "ready",
            "to": target,
            "kind": "compare",
            "entities": ["request"],
            "duration_ms": 800,
        }
        for target in ("allowed", "denied")
    ]
    scene["change_explanations"] = [
        {
            "from": "ready",
            "to": "allowed",
            "reason": "가상의 예시 정책이 team 라벨을 추가한다.",
            "changes": [
                {
                    "entity": "request",
                    "label": "라벨",
                    "before": "labels: {}",
                    "after": "labels: {team: demo}",
                }
            ],
            "invariants": [
                {
                    "entity": "original",
                    "label": "요청 앱",
                    "value": "app: demo-api",
                }
            ],
        },
        {
            "from": "ready",
            "to": "denied",
            "reason": "가상의 검증 정책에서 필수 라벨이 없으면 거절한다.",
            "changes": [
                {
                    "entity": "request",
                    "label": "검증 결과",
                    "before": "검사 전",
                    "after": "거절",
                }
            ],
            "invariants": [
                {
                    "entity": "original",
                    "label": "요청 앱",
                    "value": "app: demo-api",
                }
            ],
        },
    ]
    return design


def clear_design():
    return compile_compact_design(clear_compact_design(), HEADINGS, EXCERPTS)
