"""모델이 만든 상태·HTML·CSS를 검증하고 격리 문서로 렌더링한다."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re

from bs4 import BeautifulSoup, Comment
import tinycss2

from generator.design.scene_motion import validate_scene_motion
from generator.design.scene_presentation import DIAGRAM_ICONS, validate_presentation

from generator.paths import GENERATOR_DIR as HERE

TAGS = set(
    "div span p section article strong em b i code pre ul ol li dl dt dd h3 h4 table thead tbody tr th td br small".split()
)
FUNCTIONS = set(
    "var calc min max clamp rgb rgba hsl hsla linear-gradient radial-gradient repeating-linear-gradient repeat minmax fit-content translate translateX translateY rotate scale".lower().split()
)


def section_ends(body: str) -> dict[str, int]:
    """코드 울타리 밖의 ### 섹션 끝 오프셋. 중복 제목은 배치 대상으로 쓰지 않는다."""
    headings = []
    offset = 0
    fence = None
    for line in body.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None and (match := re.match(r"^###\s+(.+?)\s*$", line)):
            headings.append((match.group(1), offset))
        offset += len(line)
    return {
        name: headings[index + 1][1] if index + 1 < len(headings) else len(body)
        for index, (name, _) in enumerate(headings)
        if sum(other == name for other, _ in headings) == 1 and name != "정리"
    }


def _string(obj: dict, key: str, limit: int) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{key}: 비어 있거나 길이 제한 초과")
    return value


def clean_html(fragment: str) -> str:
    """유효한 수동 콘텐츠만 허용. 스크립트/이벤트/URL/폼/SVG는 거부한다."""
    soup = BeautifulSoup(fragment, "html.parser")
    for comment in soup.find_all(string=lambda node: isinstance(node, Comment)):
        comment.extract()
    entities = set()
    for tag in soup.find_all(True):
        if tag.name not in TAGS:
            raise ValueError(f"허용하지 않는 HTML 태그: {tag.name}")
        for key, value in tag.attrs.items():
            if key == "class":
                if not all(
                    re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,60}", name) for name in value
                ):
                    raise ValueError("CSS 클래스 이름 오류")
            elif key == "data-entity":
                if (
                    not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", str(value))
                    or value in entities
                ):
                    raise ValueError("data-entity 이름 오류 또는 상태 내 중복")
                entities.add(value)
                if not tag.get_text(strip=True):
                    raise ValueError("추적 대상에는 읽을 수 있는 이름이 필요함")
            elif key == "data-icon":
                if tag.name != "span" or value not in DIAGRAM_ICONS:
                    raise ValueError("허용하지 않는 아이콘 이름 또는 태그")
            elif key in {"colspan", "rowspan"} and tag.name in {"th", "td"}:
                if not re.fullmatch(r"[1-6]", str(value)):
                    raise ValueError("표 크기 제한 초과")
            else:
                raise ValueError(f"허용하지 않는 HTML 속성: {key}")
    if not soup.get_text(strip=True):
        raise ValueError("읽을 수 있는 HTML 내용이 없음")
    return str(soup)


def clean_css(css: str) -> str:
    """CSS를 파싱해 외부 자원과 실행·루트 스타일 침범을 거부한다."""
    if len(css) > 14000 or "<" in css or "\\" in css:
        raise ValueError("CSS 길이 또는 이스케이프 제한")

    def tokens_safe(tokens):
        for token in tokens:
            if token.type in {"url", "error", "at-keyword"}:
                raise ValueError("CSS 외부 자원 또는 문법 오류")
            if token.type == "function":
                if token.lower_name not in FUNCTIONS:
                    raise ValueError(f"허용하지 않는 CSS 함수: {token.name}")
                tokens_safe(token.arguments)
            if hasattr(token, "content"):
                tokens_safe(token.content)

    def check_rules(rules):
        for rule in rules:
            if (
                rule.type == "at-rule"
                and rule.lower_at_keyword == "media"
                and rule.content is not None
            ):
                tokens_safe(rule.prelude)
                check_rules(
                    tinycss2.parse_rule_list(
                        rule.content, skip_comments=True, skip_whitespace=True
                    )
                )
            elif rule.type == "qualified-rule":
                selector = tinycss2.serialize(rule.prelude).strip()
                # No sibling selectors or selector functions: generated CSS stays in the scene.
                for part in selector.split(","):
                    if (
                        not re.fullmatch(
                            r"\.scene-content(?:[\s.>#a-zA-Z0-9_:\-\[\]=\"']*)",
                            part.strip(),
                        )
                        or ":has" in part
                    ):
                        raise ValueError(
                            "CSS 선택자는 .scene-content 내부로 한정해야 함"
                        )
                declarations = tinycss2.parse_declaration_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
                for declaration in declarations:
                    if declaration.type != "declaration" or declaration.important:
                        raise ValueError("CSS 선언 오류 또는 !important 금지")
                    if declaration.lower_name in {"behavior", "-moz-binding"}:
                        raise ValueError("실행형 CSS 금지")
                    if declaration.lower_name.startswith(("animation", "transition")):
                        raise ValueError(
                            "움직임은 공통 실행기가 담당: 생성 CSS 애니메이션 금지"
                        )
                    tokens_safe(declaration.value)
            else:
                raise ValueError(
                    "@media 이외의 CSS at-rule 또는 중첩 규칙은 지원하지 않음"
                )

    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    check_rules(rules)
    return tinycss2.serialize(rules)


def validate_design(raw: str, body: str) -> dict:
    if len(raw) > 100000:
        raise ValueError("디자인 응답 크기 제한 초과")
    design = json.loads(raw)
    if not isinstance(design, dict) or set(design) != {"summary", "scenes"}:
        raise ValueError("summary와 scenes가 필요함")
    _string(design, "summary", 600)
    scenes = design["scenes"]
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 2:
        raise ValueError("시각화는 1~2개 필요")
    used = set()
    for scene in scenes:
        # Keep previously saved examples readable without requiring regeneration.
        if isinstance(scene, dict) and "playback" not in scene:
            scene["playback"] = {"steps": [], "interval_ms": 3000}
        if not isinstance(scene, dict) or set(scene) - {
            "explanation",
            "transitions",
            "effects",
            "scenarios",
            "presentation",
            "interaction_mode",
            "change_explanations",
            "charts",
        } != {
            "title",
            "after_heading",
            "caption",
            "css",
            "initial",
            "states",
            "playback",
        }:
            raise ValueError("시각화 필드 오류")
        _string(scene, "title", 100)
        _string(scene, "caption", 700)
        anchor = _string(scene, "after_heading", 150)
        if anchor not in section_ends(body) or anchor in used:
            raise ValueError("본문 배치 제목이 없거나 중복됨")
        used.add(anchor)
        scene["css"] = clean_css(_string(scene, "css", 14000))
        states = scene["states"]
        if not isinstance(states, list) or not 1 <= len(states) <= 8:
            raise ValueError("상태 개수는 1~8개")
        ids = set()
        for state in states:
            if not isinstance(state, dict) or set(state) != {
                "id",
                "html",
                "description",
                "actions",
            }:
                raise ValueError("상태 필드 오류")
            sid = _string(state, "id", 32)
            if not re.fullmatch(r"[a-z][a-z0-9_-]*", sid) or sid in ids:
                raise ValueError("상태 ID 오류")
            ids.add(sid)
            state["html"] = clean_html(_string(state, "html", 7000))
            _string(state, "description", 700)
            if not isinstance(state["actions"], list) or len(state["actions"]) > 4:
                raise ValueError("상태별 버튼은 최대 4개")
            labels = set()
            for action in state["actions"]:
                if not isinstance(action, dict) or set(action) != {"label", "target"}:
                    raise ValueError("버튼 필드 오류")
                label = _string(action, "label", 60)
                if label in labels:
                    raise ValueError("상태 안의 버튼 이름 중복")
                labels.add(label)
                _string(action, "target", 32)
        if scene["initial"] not in ids:
            raise ValueError("초기 상태 누락")
        for state in states:
            if any(action["target"] not in ids for action in state["actions"]):
                raise ValueError("존재하지 않는 전이 대상")
        if set(state_paths(scene)) != ids:
            raise ValueError("도달할 수 없는 상태 존재")
        playback = scene["playback"]
        if not isinstance(playback, dict) or set(playback) != {"steps", "interval_ms"}:
            raise ValueError("자동 재생 필드 오류")
        steps, interval = playback["steps"], playback["interval_ms"]
        if type(interval) is not int or not 1500 <= interval <= 6000:
            raise ValueError("자동 재생 간격은 1500~6000ms")
        if not isinstance(steps, list) or not all(
            isinstance(step, str) for step in steps
        ):
            raise ValueError("자동 재생 경로는 상태 ID 목록이어야 함")
        if steps:
            if (
                not 2 <= len(steps) <= 8
                or len(set(steps)) != len(steps)
                or steps[0] != scene["initial"]
            ):
                raise ValueError("자동 재생은 초기 상태에서 시작하는 유한 경로여야 함")
            by_id = {state["id"]: state for state in states}
            if any(step not in by_id for step in steps):
                raise ValueError("자동 재생에 없는 상태 ID 사용")
            for before, after in zip(steps, steps[1:]):
                if after not in {
                    action["target"] for action in by_id[before]["actions"]
                }:
                    raise ValueError("자동 재생 경로가 실제 버튼 전이와 불일치")
        validate_scene_motion(scene)
        validate_presentation(scene)
        from generator.design.scene_charts import validate_scene_charts

        validate_scene_charts(scene)
    from generator.design.scene_clarity import collect_clarity_issues

    clarity_issues = collect_clarity_issues(design)
    if clarity_issues:
        raise ValueError(clarity_issues[0]["message"])
    return design


def state_paths(scene: dict) -> dict[str, list[int]]:
    paths = {scene["initial"]: []}
    states = {state["id"]: state for state in scene["states"]}
    queue = [scene["initial"]]
    for sid in queue:
        for index, action in enumerate(states[sid]["actions"]):
            if action["target"] not in paths:
                paths[action["target"]] = paths[sid] + [index]
                queue.append(action["target"])
    return paths


BASE_CSS = """
:root{color-scheme:dark;font-family:'Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;color:#d6dae0;background:#14171d;font-size:15px;line-height:1.7}
*{box-sizing:border-box}body{margin:0;padding:20px;word-break:keep-all;overflow-wrap:anywhere}h2{font-size:20px;line-height:1.4;margin:0 0 10px}.scene-caption{font-size:12px;color:#8b93a1;margin:0 0 18px}
.scene-content{position:relative;isolation:isolate;overflow:hidden;min-height:40px}.scene-content p{margin:0 0 12px}.scene-content pre{white-space:pre-wrap}.scene-content table{max-width:100%;table-layout:fixed}
#scene-controls{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}button{font:inherit;font-size:13px;min-height:44px;background:#202d3d;color:#d6dae0;border:1px solid #3a414d;border-radius:6px;padding:8px 13px;cursor:pointer}button:hover{border-color:#79b8ff}button:focus-visible,#scene-status:focus-visible{outline:2px solid #79b8ff;outline-offset:3px}
#scene-status{font-size:14px;background:#79b8ff12;border-left:2px solid #79b8ff;padding:14px;margin:18px 0 10px}#scene-reset{font-size:12px;background:none;color:#8b93a1;margin-top:8px}[hidden]{display:none!important}
#scene-playback{display:flex;align-items:center;gap:12px;margin-top:12px}#scene-progress{font:12px ui-monospace,monospace;color:#8b93a1}
#scene-scenarios{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}#scene-scenarios button{background:#0c0e12;color:#8b93a1}#scene-scenarios button[aria-pressed=true]{color:#d6dae0;border-color:#79b8ff;background:#79b8ff18}
#scene-transition-status{font-size:13px;min-height:1.7em;color:#ffb86b;margin:10px 0 0}#scene-previous{font-size:12px;background:none;color:#8b93a1;margin-top:8px;margin-right:8px}button:disabled{opacity:.5;cursor:default}
.scene-change-summary{margin:16px 0 0;border-top:1px solid #3a414d;padding-top:12px;font-size:14px;line-height:1.55}
.scene-change-summary h3{font-size:13px;font-weight:600;color:#8b93a1;margin:0 0 10px}
#scene-change-summary:focus-visible{outline:2px solid #79b8ff;outline-offset:3px}
.scene-change-row{display:grid;grid-template-columns:minmax(0,1fr) 18px minmax(0,1fr);gap:4px 10px;padding:8px 0;border-bottom:1px solid #3a414d70;align-items:start}
.scene-change-label{grid-column:1/-1;font-size:13px;color:#8b93a1}
.scene-change-before,.scene-change-after{min-width:0;overflow-wrap:anywhere;font-family:ui-monospace,monospace}
.scene-change-before{color:#a7adb7}.scene-change-after{color:#79b8ff;font-weight:600}.scene-change-arrow{color:#8b93a1;text-align:center}
@media(max-width:400px){.scene-change-row[data-layout=stacked]{grid-template-columns:18px minmax(0,1fr)}.scene-change-row[data-layout=stacked] .scene-change-label{grid-column:1/-1}.scene-change-row[data-layout=stacked] .scene-change-before{grid-column:2}.scene-change-row[data-layout=stacked] .scene-change-arrow{grid-column:1;transform:rotate(90deg)}.scene-change-row[data-layout=stacked] .scene-change-after{grid-column:2}}
.scene-change-reason{margin:10px 0;color:#d6dae0}.scene-change-invariants{display:flex;flex-wrap:wrap;gap:6px 14px;color:#a7adb7;font-size:13px}
.scene-change-invariant{min-width:0;overflow-wrap:anywhere}.scene-change-invariant-label{color:#8b93a1;margin-right:6px}.scene-change-invariant-value{font-family:ui-monospace,monospace}
.scene-change-details{margin-top:8px}.scene-change-details-toggle{font-size:13px;color:#a7adb7;min-height:44px;padding:10px 0;cursor:pointer}.scene-change-details-toggle:focus-visible{outline:2px solid #79b8ff;outline-offset:3px}.scene-change-details[open]>.scene-change-details-toggle{color:#d6dae0}.scene-change-details>.scene-change-row:last-child{border-bottom:0}
#scene-controls:empty{display:none}
#scene-extra-details{margin-top:12px}#scene-extra-details summary{font-size:13px;color:#8b93a1;cursor:pointer;min-height:44px;padding:10px 0}#scene-extra-details summary:focus-visible{outline:2px solid #79b8ff;outline-offset:3px}#scene-extra-details #scene-status{margin-top:0}
.scene-transfer-layer{position:absolute;inset:0;z-index:10;pointer-events:none;overflow:visible}.scene-transfer-wire{fill:none;stroke:#79b8ff;stroke-width:2;stroke-dasharray:4 5;opacity:.65}
.scene-transfer-token{position:absolute;z-index:11;max-width:min(11rem,70%);padding:5px 10px;border:1px solid #ffb86b;border-radius:5px;background:#0c0e12;color:#ffb86b;font:600 13px/1.5 ui-monospace,monospace;white-space:normal;overflow-wrap:anywhere;text-align:center;translate:-50% -50%;box-shadow:0 3px 16px #0c0e12;pointer-events:none}
body:not(.diagram-scene) span[data-icon]{display:inline-flex;width:28px;height:28px;vertical-align:middle;color:#79b8ff;flex-shrink:0}body:not(.diagram-scene) span[data-icon] svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
@media(max-width:400px){body{padding:14px}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
"""


def render_document(scene: dict) -> str:
    script = (
        (HERE.parent / "assets/js/scene-diagram.js").read_text(encoding="utf-8")
        + "\n"
        + (HERE.parent / "assets/js/scene-charts.js").read_text(encoding="utf-8")
        + "\n"
        + (HERE.parent / "assets/js/scene-runtime.js").read_text(encoding="utf-8")
    )
    presentation = scene.get("presentation")
    if presentation:
        validate_presentation(scene)
        # Presets use audited layout rules. Candidate CSS cannot move icons,
        # hide labels, or turn the article into a different site.
        scene_css = (HERE.parent / "assets/css/scene-diagram.css").read_text(
            encoding="utf-8"
        )
    else:
        scene_css = scene["css"]
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = f"default-src 'none'; script-src 'sha256-{digest}'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; connect-src 'none'"
    data = (
        json.dumps(scene, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    initial = next(
        state for state in scene["states"] if state["id"] == scene["initial"]
    )
    fallback = "".join(
        f"<p>{html.escape(state['description'])}</p>" for state in scene["states"]
    )
    from generator.design.scene_charts import chart_fallback_html

    fallback += chart_fallback_html(scene)
    for edge in scene.get("change_explanations", []):
        origin = next(state for state in scene["states"] if state["id"] == edge["from"])
        action_label = next(
            action["label"]
            for action in origin["actions"]
            if action["target"] == edge["to"]
        )
        changes = "".join(
            f"<li>{html.escape(item['label'])}: {html.escape(item['before'])} → {html.escape(item['after'])}</li>"
            for item in edge["changes"]
        )
        invariants = "".join(
            f"<li>유지 · {html.escape(item['label'])}: {html.escape(item['value'])}</li>"
            for item in edge["invariants"]
        )
        fallback += (
            f"<section><h3>{html.escape(action_label)}</h3>"
            f"<ul>{changes}{invariants}</ul><p>{html.escape(edge['reason'])}</p></section>"
        )
    if presentation:
        markup = (
            f'<span class="diagram-eyebrow">{html.escape(presentation["eyebrow"])}</span>'
            f"<h2>{html.escape(scene['title'])}</h2>"
            '<div id="scene-scenarios" role="group" aria-label="상황 선택" hidden></div>'
            '<div id="scene-interaction" role="group" aria-label="재생 조작" hidden>'
            '<div id="scene-playback" hidden><button id="scene-play" type="button" aria-pressed="false">자동 재생</button></div>'
            '<button id="scene-previous" type="button" hidden>← 이전</button>'
            '<button id="scene-next" type="button">다음 →</button>'
            '<button id="scene-reset" type="button">처음부터</button></div>'
            '<span id="scene-progress" aria-live="off"></span>'
            f'<div class="scene-content" id="scene-content">{initial["html"]}</div>'
            '<p id="scene-transition-status" role="status" aria-live="polite" hidden></p>'
            '<p id="scene-status" role="status" aria-live="polite" tabindex="-1"></p>'
            '<div id="scene-controls" role="group" aria-label="실험 조작"></div>'
            '<p class="diagram-note"><span><i aria-hidden="true"></i>메시지·데이터</span>'
            '<span><i class="signal" aria-hidden="true"></i>요청·응답 신호</span>'
            "<span>설명용 모형 · 실제 연결 없음</span></p>"
        )
        body_attrs = f' class="diagram-scene" data-layout="{presentation["layout"]}"'
    else:
        markup = (
            f'<h2>{html.escape(scene["title"])}</h2><p class="scene-caption">설명용 시각화 · 실제 시스템에 연결하지 않는다.</p>'
            '<div id="scene-scenarios" role="group" aria-label="상황 선택" hidden></div>'
            f'<div class="scene-content" id="scene-content">{initial["html"]}</div>'
            '<p id="scene-transition-status" role="status" aria-live="polite" hidden></p>'
            '<div id="scene-interaction" hidden><div id="scene-controls" role="group" aria-label="실험 조작"></div>'
            '<p id="scene-status" role="status" aria-live="polite" tabindex="-1"></p>'
            '<div id="scene-playback" hidden><button id="scene-play" type="button" aria-pressed="false">자동 재생</button><span id="scene-progress"></span></div>'
            '<button id="scene-previous" type="button" hidden>← 이전</button>'
            '<button id="scene-reset" type="button">처음부터 ↺</button></div>'
        )
        body_attrs = ""
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(csp, quote=True)}">'
        f"<title>{html.escape(scene['title'])}</title><style>{BASE_CSS}\n{scene_css}</style></head><body{body_attrs}>"
        f"{markup}"
        f'<noscript>{fallback}</noscript><script type="application/json" id="scene-data">{data}</script>'
        f"<script>{script}</script></body></html>"
    )
