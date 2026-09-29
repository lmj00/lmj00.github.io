"""Concrete, fictional format examples; never article evidence."""

from copy import deepcopy


def _example(
    *,
    kind,
    mode,
    title,
    html,
    css,
    original,
    rule,
    question,
    reader_action,
    takeaway,
    initial,
    outcomes,
):
    """Keep a fixed object visible while comparing two explicit alternatives."""
    states = [
        {
            "id": "start",
            "values": [
                {"binding": key, "value": value} for key, value in initial.items()
            ],
            "entity_classes": [],
            "description": f"{original} 두 선택을 같은 원본에서 비교한다.",
            "actions": [
                {"label": item["label"], "target": item["id"]} for item in outcomes
            ],
        }
    ]
    changes = []
    for item in outcomes:
        states.append(
            {
                "id": item["id"],
                "values": [
                    {"binding": key, "value": value}
                    for key, value in item["values"].items()
                ],
                "entity_classes": [],
                "description": item["reason"],
                "actions": [],
            }
        )
        changes.append(
            {
                "from": "start",
                "to": item["id"],
                "reason": item["reason"],
                "changes": [
                    {
                        "entity": key,
                        "label": "선택 조건" if key == "condition" else "결과",
                        "before": value,
                        "after": item["values"][key],
                    }
                    for key, value in initial.items()
                ],
                "invariants": [
                    {"entity": "original", "label": "고정 원본", "value": original}
                ],
            }
        )
    return {
        "example_only": True,
        "input": {
            "headings": {"example_section": "가상 조건"},
            "source_excerpts": [
                {
                    "excerpt_id": "example_evidence",
                    "source_url": "https://example.com/fictional-format",
                    "quote": rule,
                }
            ],
        },
        "output": {
            "summary": title,
            "scenes": [
                {
                    "title": title,
                    "heading_id": "example_section",
                    "caption": "형식 학습용 가상 규칙이다. 실제 제품·프로토콜의 동작이 아니며 본문의 사실 근거로 쓰지 않는다.",
                    "html": html,
                    "css": css,
                    "interaction_mode": mode,
                    "change_explanations": changes,
                    "explanation": {
                        "mode": "interactive",
                        "learning_goal": question,
                        "reader_action": reader_action,
                        "observable_change": "원본은 그대로 남고 선택한 규칙과 결과의 구체적인 값이 바뀐다.",
                        "takeaway": takeaway,
                        "assumptions": ["화면에 명시한 가상 규칙만 적용한다."],
                        "key_entities": ["original", *initial],
                        "excerpt_ids": ["example_evidence"],
                    },
                    "initial": "start",
                    "states": states,
                    "playback": {
                        "steps": ["start", outcomes[0]["id"]],
                        "interval_ms": 2200,
                    },
                    "effects": [
                        {
                            "from": "start",
                            "to": item["id"],
                            "kind": kind,
                            "entities": list(initial),
                            "duration_ms": 900,
                        }
                        for item in outcomes
                    ],
                    "scenarios": [
                        {
                            "id": item["id"],
                            "label": item["label"],
                            "steps": ["start", item["id"]],
                        }
                        for item in outcomes
                    ],
                }
            ],
        },
    }


def examples() -> list[dict]:
    return [
        _example(
            kind="compare",
            mode="compare",
            title="같은 파일인데 권한에 따라 왜 열리지 않을까?",
            html=(
                '<section class="access"><div class="file">'
                '<span class="diagram-symbol" data-icon="document"></span>'
                '<p data-entity="original">요청: report.csv 열기</p></div>'
                '<div class="permission"><h3>가상 접근 규칙</h3>'
                "<p>읽기 권한이면 열기 허용. 권한이 없으면 거절.</p>"
                '<p data-entity="condition">{{condition}}</p>'
                '<p class="verdict" data-entity="result">{{result}}</p></div></section>'
            ),
            css=(
                ".scene-content .access {display:grid;grid-template-columns:1fr 1.4fr;gap:20px;padding:16px 0}"
                ".scene-content .file {padding:18px;background:#14171d;align-self:start}"
                ".scene-content .permission {padding:8px 0;min-width:0}"
                ".scene-content .verdict {border-top:2px solid #79b8ff;padding-top:12px;font-weight:700}"
                ".scene-content p {font-size:15px;line-height:1.6}"
                "@media(max-width:500px){.scene-content .access {grid-template-columns:1fr;gap:4px}}"
            ),
            original="요청: report.csv 열기",
            rule="가상 접근 규칙: report.csv 열기 요청은 읽기 권한이 있으면 허용하고, 권한이 없으면 거절한다. 요청 파일과 작업은 두 경우에 동일하다.",
            question="report.csv 열기 요청은 같을 때 무엇이 접근 판정을 바꾸는가?",
            reader_action="읽기 권한으로 열기 또는 권한 없이 열기를 선택한다.",
            takeaway="파일과 작업이 같아도 요청자의 읽기 권한 유무가 허용과 거절을 나눈다.",
            initial={"condition": "권한: 미선택", "result": "접근 판정: 선택 전"},
            outcomes=[
                {
                    "id": "read",
                    "label": "읽기 권한으로 열기",
                    "values": {"condition": "권한: 읽기", "result": "접근 판정: 허용"},
                    "reason": "읽기 권한이 가상 접근 규칙을 충족하므로 report.csv 열기가 허용된다.",
                },
                {
                    "id": "none",
                    "label": "권한 없이 열기",
                    "values": {"condition": "권한: 없음", "result": "접근 판정: 거절"},
                    "reason": "읽기 권한이 없으므로 같은 report.csv 열기 요청이 거절된다.",
                },
            ],
        ),
        _example(
            kind="transform",
            mode="compare",
            title="원본을 남겨 두고 이름 표기 비교하기",
            html=(
                '<article class="record"><h3><span class="diagram-symbol" data-icon="database"></span>'
                "이름 필드의 두 표현</h3><p>가상 규칙: 영문 대문자 또는 소문자 변환을 각각 적용한다. 숫자는 유지한다.</p>"
                '<dl class="ledger"><dt>고정 원본</dt><dd><code data-entity="original">name: Ada_7</code></dd>'
                '<dt>적용 규칙</dt><dd data-entity="condition">{{condition}}</dd>'
                '<dt>변환 결과</dt><dd><code data-entity="result">{{result}}</code></dd></dl></article>'
            ),
            css=(
                ".scene-content .record {padding:16px 0}.scene-content p {font-size:15px;line-height:1.6}"
                ".scene-content h3 {display:flex;align-items:center;gap:8px}"
                ".scene-content .ledger {display:grid;grid-template-columns:90px 1fr;gap:14px 12px;padding:18px 12px;background:#14171d}"
                ".scene-content dt {font-size:14px;color:#8b93a1}.scene-content dd {margin:0;min-width:0;font-size:15px}"
                ".scene-content code {white-space:pre-wrap;font-size:15px;overflow-wrap:anywhere}"
            ),
            original="name: Ada_7",
            rule="가상 표기 규칙: name: Ada_7에 uppercase를 적용하면 name: ADA_7이다. lowercase를 적용하면 name: ada_7이다. 숫자 7과 밑줄은 유지하며, 원본은 수정하지 않는다.",
            question="같은 이름 필드에서 대문자·소문자 변환은 무엇을 바꾸고 무엇을 유지하는가?",
            reader_action="대문자로 변환과 소문자로 변환을 같은 원본에 각각 적용한다.",
            takeaway="영문자 표기만 달라지고 숫자 7과 밑줄은 유지된다. 고정 원본은 수정하지 않는다.",
            initial={"condition": "규칙: 미선택", "result": "name: Ada_7"},
            outcomes=[
                {
                    "id": "upper",
                    "label": "대문자로 변환",
                    "values": {"condition": "규칙: uppercase", "result": "name: ADA_7"},
                    "reason": "uppercase는 da를 DA로 바꾸지만 숫자 7과 밑줄은 유지한다. 고정 원본은 수정하지 않는다.",
                },
                {
                    "id": "lower",
                    "label": "소문자로 변환",
                    "values": {"condition": "규칙: lowercase", "result": "name: ada_7"},
                    "reason": "lowercase는 A를 a로 바꾸지만 숫자 7과 밑줄은 유지한다. 고정 원본은 수정하지 않는다.",
                },
            ],
        ),
        _example(
            kind="reveal",
            mode="explore",
            title="같은 사진의 저장 계층을 펼쳐 읽기",
            html=(
                '<article class="storage"><div class="asset"><span class="diagram-symbol" data-icon="document"></span>'
                '<p data-entity="original">photo.png · 2 MB</p></div>'
                '<div class="shelf"><h3>가상 보관 안내</h3><p>사진은 메모리와 디스크에 함께 있다. 선택은 이동이 아니라 설명 펼치기다.</p>'
                '<p class="detail" data-entity="result">{{result}}</p></div></article>'
            ),
            css=(
                ".scene-content .storage {padding:12px 0}.scene-content .asset {display:flex;align-items:center;gap:12px;padding:8px 16px}"
                ".scene-content .shelf {margin-left:20px;padding:14px 18px;border-left:3px solid #79b8ff;background:#14171d}"
                ".scene-content p {font-size:15px;line-height:1.6}.scene-content .detail {white-space:pre-line}"
            ),
            original="photo.png · 2 MB",
            rule="가상 보관 규칙: photo.png(2 MB)는 메모리와 디스크에 함께 있다. 메모리 사본은 프로그램 종료 시 지워진다. 디스크 사본은 사용자가 삭제할 때까지 남는다. 계층 선택은 규칙 설명만 펼치며 파일을 이동하거나 삭제하지 않는다.",
            question="프로그램이 끝나도 사진이 남는 계층은 어디인가?",
            reader_action="메모리 보관 규칙과 디스크 보관 규칙을 각각 펼친다.",
            takeaway="이 가상 규칙에서 종료 시 메모리 사본은 지워지고 디스크 사본은 남는다. 선택은 파일 조작이 아니다.",
            initial={"result": "보관 규칙: 계층을 선택하세요."},
            outcomes=[
                {
                    "id": "memory",
                    "label": "메모리 보관 규칙",
                    "values": {
                        "result": "메모리 사본\n현재 크기: 2 MB\n보관 종료: 프로그램 종료 시\n종료하면 이 사본만 지워진다."
                    },
                    "reason": "메모리 사본의 종료 조건을 펼쳤다. 디스크 사본과 원본 파일 정보는 바뀌지 않는다.",
                },
                {
                    "id": "disk",
                    "label": "디스크 보관 규칙",
                    "values": {
                        "result": "디스크 사본\n현재 크기: 2 MB\n보관 종료: 사용자가 삭제할 때\n프로그램이 끝나도 이 사본은 남는다."
                    },
                    "reason": "디스크 사본은 사용자 삭제 전까지 남는다는 가상 규칙을 펼쳤다. 파일을 이동한 것이 아니다.",
                },
            ],
        ),
    ]


def numeric_example() -> dict:
    """A fictional numeric composition, not a Prometheus-specific template."""
    example = _example(
        kind="transform",
        mode="compare",
        title="원본과 보정값 비교",
        html=(
            '<section class="readings"><p data-entity="original">원본: 2, 4, 3점</p>'
            '<div data-entity="readings_plot"><p>같은 눈금에서 비교</p></div>'
            '<p data-entity="result">{{result}}</p></section>'
        ),
        css=(
            ".scene-content .readings{padding:4px 0}"
            ".scene-content .readings p{font-size:14px;line-height:1.5;margin:6px 0}"
        ),
        original="원본: 2, 4, 3점",
        rule="가상 측정 규칙: 세 번의 원본 관측값은 순서대로 2, 4, 3점이다. 보정 없음은 그대로 표시하며, +2 보정은 각 관측값에 2점을 더하여 4, 6, 5점으로 표시한다. 선택은 원본을 변경하지 않는다.",
        question="같은 원본에 +2 보정을 적용하면 세 관측값은 어떻게 달라지는가?",
        reader_action="보정 없음과 +2 보정을 선택해 같은 축에서 비교한다.",
        takeaway="+2 보정은 모든 관측값을 2점 높이며 원본과 관측 순서는 유지한다.",
        initial={"result": "비교 대상: 원본과 +2 보정"},
        outcomes=[
            {"id": "raw", "label": "보정 없음", "values": {"result": "표시값: 2, 4, 3점"},
             "reason": "보정 없음은 원본을 그대로 표시하므로 2, 4, 3점이다."},
            {"id": "offset", "label": "+2 보정", "values": {"result": "표시값: 4, 6, 5점"},
             "reason": "각 원본 값에 2점을 더하므로 4, 6, 5점이다."},
        ],
    )
    scene = example["output"]["scenes"][0]
    scene["charts"] = [{
        "entity": "readings_plot", "kind": "line", "label": "원본과 +2 보정", "unit": "점",
        "caption": "설명용 가상 수치 · 실제 측정값이 아니다.",
        "labels": ["첫 관측", "두 번째", "세 번째"],
        "series": [
            {"id": "raw", "label": "원본", "values": [2, 4, 3], "tone": "blue"},
            {"id": "offset", "label": "+2 보정", "values": [4, 6, 5], "tone": "amber"},
        ],
        "views": [
            {"state": "start", "active_series": ["raw", "offset"], "visible_points": 3},
            {"state": "raw", "active_series": ["raw"], "visible_points": 3},
            {"state": "offset", "active_series": ["offset"], "visible_points": 3},
        ],
    }]
    return example


def select_examples(article: str) -> list[dict]:
    """Choose differing compositions, never copy a topic's facts into the input."""
    text = article.lower()
    index = (
        0
        if any(word in text for word in ("policy", "정책", "조건", "admission"))
        else 1
    )
    if any(word in text for word in ("계층", "layer", "hierarchy")):
        index = 2
    bank = examples()
    if any(word in text for word in ("수치", "누적", "측정값", "시계열", "메트릭", "metric", "counter", "gauge")):
        return deepcopy([numeric_example(), bank[1]])
    return deepcopy([bank[index], bank[(index + 1) % len(bank)]])
