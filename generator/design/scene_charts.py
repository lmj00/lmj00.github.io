"""Bounded numeric chart data for the trusted renderer, not generated SVG/code.

The chart is an additional view of declared numbers. It does not replace readable
HTML entities or the existing source, clarity, browser and independent review
gates. In particular, this module cannot establish that a number is factual.
"""

from __future__ import annotations

import math
import re
from html import escape

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator
import tinycss2


def _object(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _text(limit):
    return {"type": "string", "minLength": 1, "maxLength": limit}


_ID = {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,31}$"}
SCENE_CHARTS_SCHEMA = {
    "type": "array",
    "minItems": 0,
    "maxItems": 2,
    "items": _object(
        entity=_ID,
        kind={"type": "string", "enum": ["line", "bar"]},
        label=_text(72),
        caption={**_text(160), "pattern": "설명용"},
        unit={"type": "string", "maxLength": 20},
        labels={"type": "array", "items": _text(48), "minItems": 2, "maxItems": 12},
        series={
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": _object(
                id=_ID,
                label=_text(48),
                values={
                    "type": "array",
                    "items": {"type": "number", "minimum": -1e12, "maximum": 1e12},
                    "minItems": 2,
                    "maxItems": 12,
                },
                tone={"type": "string", "enum": ["blue", "amber", "teal"]},
            ),
        },
        views={
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": _object(
                state={"type": "string", "minLength": 1, "maxLength": 80},
                active_series={
                    "type": "array",
                    "items": _ID,
                    "minItems": 1,
                    "maxItems": 3,
                    "uniqueItems": True,
                },
                visible_points={"type": "integer", "minimum": 1, "maximum": 12},
            ),
        },
    ),
}
# A short alias is convenient when embedding this optional array in contracts.
CHARTS_SCHEMA = SCENE_CHARTS_SCHEMA


def _validate_chart_css(css):
    """Generated styling must not target trusted chart/SVG implementation nodes."""

    def walk(rules):
        for rule in rules:
            if rule.type == "at-rule" and rule.content is not None:
                walk(
                    tinycss2.parse_rule_list(
                        rule.content, skip_comments=True, skip_whitespace=True
                    )
                )
            elif rule.type == "qualified-rule":
                selector = tinycss2.serialize(rule.prelude).lower()
                if re.search(
                    r"scene-chart|data-chart|(?:^|[\s>,])(?:svg|path|polyline|polygon|line|circle|ellipse|rect|g|defs|use)(?=$|[\s.#:\[,>])",
                    selector,
                ):
                    raise ValueError(
                        "charts.css: 공통 차트/SVG 선택자를 수정할 수 없음; 모델 HTML의 클래스만 꾸미세요"
                    )

    walk(tinycss2.parse_stylesheet(css or "", skip_comments=True, skip_whitespace=True))


def validate_scene_charts(scene: dict) -> None:
    """Reject unsafe/inconsistent chart data without changing the candidate.

    Each chart is attached *after* a unique readable block entity. Keeping its
    trusted graphic outside that entity preserves exact-text/effect snapshots.
    All state views are explicit; only process scenes may progressively reveal
    points. The axis uses the whole data set, including zero, in every view.
    """
    if "charts" not in scene:
        return
    charts = scene["charts"]
    errors = list(Draft202012Validator(SCENE_CHARTS_SCHEMA).iter_errors(charts))
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.absolute_path)
        raise ValueError(f"charts{'.' + path if path else ''}: {error.message[:300]}")
    if charts:
        _validate_chart_css(scene.get("css", ""))
    states = scene.get("states", [])
    state_ids = {state.get("id") for state in states}
    if charts and (not state_ids or len(state_ids) != len(states)):
        raise ValueError("charts: 중복 없는 상태 ID가 필요함")
    seen_hosts = set()
    for chart in charts:
        entity = chart["entity"]
        prefix = f"charts[{entity}]"
        if entity in seen_hosts:
            raise ValueError(f"{prefix}: chart host 중복")
        seen_hosts.add(entity)
        text_values = [
            chart["label"],
            chart["caption"],
            chart["unit"],
            *chart["labels"],
            *(series["label"] for series in chart["series"]),
        ]
        for value in text_values:
            if (value and not value.strip()) or re.search(
                r"[<>\x00-\x08\x0b-\x1f]", value
            ):
                raise ValueError(
                    f"{prefix}: 라벨·단위·설명은 읽을 수 있는 일반 텍스트만 허용"
                )
        series_ids = {series["id"] for series in chart["series"]}
        if len(series_ids) != len(chart["series"]):
            raise ValueError(f"{prefix}: series ID 중복")
        for series in chart["series"]:
            if len(series["values"]) != len(chart["labels"]):
                raise ValueError(
                    f"{prefix}: labels와 각 series.values의 개수가 같아야 함"
                )
            if any(
                isinstance(value, bool) or not math.isfinite(value)
                for value in series["values"]
            ):
                raise ValueError(f"{prefix}: 숫자는 유한한 값만 허용")
        views = chart["views"]
        if len({view["state"] for view in views}) != len(views):
            raise ValueError(f"{prefix}: state view 중복")
        if {view["state"] for view in views} != state_ids:
            raise ValueError(
                f"{prefix}: 모든 실제 상태에 view를 정확히 하나씩 지정해야 함"
            )
        for view in views:
            if not set(view["active_series"]) <= series_ids:
                raise ValueError(f"{prefix}: 존재하지 않는 active_series")
            if view["visible_points"] > len(chart["labels"]):
                raise ValueError(f"{prefix}: visible_points가 데이터 길이를 초과함")
            if scene.get("interaction_mode") != "process" and view[
                "visible_points"
            ] != len(chart["labels"]):
                raise ValueError(
                    f"{prefix}: compare/explore는 모든 점을 보여야 함; 순차 공개는 process만 허용"
                )
        for state in states:
            soup = BeautifulSoup(state.get("html", ""), "html.parser")
            hosts = soup.find_all(attrs={"data-entity": entity})
            if len(hosts) != 1:
                raise ValueError(
                    f"{prefix}: {state['id']}에 유일한 chart host가 필요함"
                )
            host = hosts[0]
            if host.name not in {"div", "section", "article"}:
                raise ValueError(
                    f"{prefix}: host는 div, section, article 블록이어야 함"
                )
            if host.find(attrs={"data-entity": True}) or host.find_parent(
                attrs={"data-entity": True}
            ):
                raise ValueError(f"{prefix}: host와 다른 data-entity를 중첩할 수 없음")
            if host.find_parent(
                [
                    "p",
                    "span",
                    "table",
                    "thead",
                    "tbody",
                    "tr",
                    "code",
                    "pre",
                    "ul",
                    "ol",
                ]
            ):
                raise ValueError(
                    f"{prefix}: chart sibling을 담을 수 있는 블록 부모가 필요함"
                )
            readable = BeautifulSoup(str(host), "html.parser")
            for hidden in readable.select(
                'script, style, template, [hidden], [aria-hidden="true"]'
            ):
                hidden.decompose()
            if not readable.get_text(" ", strip=True):
                raise ValueError(
                    f"{prefix}: 그래프 없이도 읽을 수 있는 HTML fallback이 필요함"
                )


def chart_fallback_html(scene: dict) -> str:
    """Complete, escaped static numeric evidence when scripts are unavailable."""
    validate_scene_charts(scene)
    fragments = []
    for chart in scene.get("charts", []):
        heading = escape(chart["label"])
        unit = f" ({escape(chart['unit'])})" if chart["unit"] else ""
        header = "".join(
            f'<th scope="col">{escape(series["label"])}</th>'
            for series in chart["series"]
        )
        rows = []
        for index, label in enumerate(chart["labels"]):
            values = "".join(
                f"<td>{escape(str(series['values'][index]))}</td>"
                for series in chart["series"]
            )
            rows.append(
                f'<tr><th scope="row">{index + 1} · {escape(label)}</th>{values}</tr>'
            )
        fragments.append(
            f'<section class="scene-chart-fallback"><h4>{heading}</h4>'
            f"<p>{escape(chart['caption'])}</p><table><caption>{heading}{unit}</caption>"
            f'<thead><tr><th scope="col">관측 지점</th>{header}</tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )
    return "".join(fragments)


def verify_chart_graphics(root, chart: dict, state_id: str) -> None:
    """Check actual SVG geometry/paint, not just a matching readable data table.

    Called on the settled browser DOM. Native zero-height bars are valid zeros;
    nonzero data must retain visible paint and its expected position/size.
    """
    report = root.evaluate("""root => {
      const svg = root.querySelector('svg.scene-chart-graphic');
      if (!svg) return {error:'missing SVG'};
      const rect = svg.getBoundingClientRect();
      function shown(node) {
        for (let el=node; el; el=el.parentElement) {
          const s=getComputedStyle(el);
          if (s.display==='none' || s.visibility==='hidden' || Number(s.opacity)<=0.05) return false;
        }
        return true;
      }
      function paint(value) {
        return Boolean(value && !['none','transparent'].includes(value) &&
          !/rgba\\([^)]*,\\s*0(?:\\.0+)?\\s*\\)/.test(value) && !/\\/\\s*0(?:\\.0+)?\\s*\\)/.test(value));
      }
      return {width:rect.width,height:rect.height,shown:shown(svg),
        points:[...svg.querySelectorAll('[data-chart-index]')].map(n=>{
          const s=getComputedStyle(n),b=n.getBBox();
          return {series:n.dataset.chartSeries,index:Number(n.dataset.chartIndex),value:Number(n.dataset.chartValue),tag:n.tagName,
            x:b.x,y:b.y,width:b.width,height:b.height,shown:shown(n),fill:paint(s.fill)&&Number(s.fillOpacity)>0.05};
        }),
        lines:[...svg.querySelectorAll('polyline')].map(n=>{
          const s=getComputedStyle(n);
          return {series:n.dataset.chartSeries,points:[...n.points].map(p=>[p.x,p.y]),shown:shown(n),stroke:paint(s.stroke)&&Number(s.strokeOpacity)>0.05&&parseFloat(s.strokeWidth)>=1};
        })};
    }""")
    prefix = f"수치 차트 {chart['entity']}/{state_id}"
    if (
        report.get("error")
        or not report.get("shown")
        or report.get("width", 0) < 80
        or report.get("height", 0) < 80
    ):
        raise ValueError(f"{prefix}: 실제 그래프 영역이 없거나 너무 작음")
    view = next((item for item in chart["views"] if item["state"] == state_id), None)
    if not view:
        raise ValueError(f"{prefix}: 해당 상태 데이터 없음")
    count = view["visible_points"]
    expected = {
        (series["id"], index): value
        for series in chart["series"]
        for index, value in enumerate(series["values"][:count])
    }
    points = {(item["series"], item["index"]): item for item in report["points"]}
    if len(points) != len(report["points"]) or set(points) != set(expected):
        raise ValueError(f"{prefix}: 실제 그래프 점/막대와 데이터 개수가 다름")
    values = [0] + [value for series in chart["series"] for value in series["values"]]
    low, high = min(values), max(values)
    if low == high:
        high = low + 1

    def y(value):
        return 8 + (high - value) / (high - low) * 138

    def near(actual, wanted):
        return (
            isinstance(actual, (int, float))
            and math.isfinite(actual)
            and abs(actual - wanted) < 0.05
        )

    size = len(chart["labels"])
    series_order = {series["id"]: index for index, series in enumerate(chart["series"])}
    for key, value in expected.items():
        point = points[key]
        if point["value"] != value or not point["shown"] or not point["fill"]:
            raise ValueError(f"{prefix}: {key}의 수치 표시가 숨겨지거나 바뀜")
        if chart["kind"] == "line":
            correct = (
                point["tag"] == "circle"
                and near(point["x"] + point["width"] / 2, (key[1] + 0.5) / size * 600)
                and near(point["y"] + point["height"] / 2, y(value))
                and point["width"] >= 4
                and point["height"] >= 4
            )
        else:
            width = min(62, 600 / size * 0.76 / len(chart["series"]))
            x = (
                (key[1] + 0.5) * 600 / size
                - width * len(chart["series"]) / 2
                + width * series_order[key[0]]
            )
            correct = (
                point["tag"] == "rect"
                and near(point["x"], x)
                and near(point["y"], min(y(0), y(value)))
                and near(point["width"], max(1, width - 2))
                and near(point["height"], abs(y(value) - y(0)))
            )
        if not correct:
            raise ValueError(f"{prefix}: {key}의 실제 그래프 위치/크기가 수치와 다름")
    lines = {item["series"]: item for item in report["lines"]}
    if chart["kind"] == "line":
        if len(lines) != len(chart["series"]):
            raise ValueError(f"{prefix}: 실제 수치 연결선이 누락됨")
        for series in chart["series"]:
            line = lines.get(series["id"])
            if (
                not line
                or not line["shown"]
                or not line["stroke"]
                or len(line["points"]) != count
            ):
                raise ValueError(f"{prefix}: 실제 수치 연결선이 보이지 않음")
            if any(
                not near(point[0], (index + 0.5) / size * 600)
                or not near(point[1], y(series["values"][index]))
                for index, point in enumerate(line["points"])
            ):
                raise ValueError(f"{prefix}: 실제 연결선 좌표가 수치와 다름")
