"""Validate opt-in, code-owned diagram compositions without changing legacy scenes.

Models supply short labels and stable participants, not the icons, responsive layout
or animation code. Call after the ordinary HTML sanitizer; rendering is separate.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag


DIAGRAM_ICONS = frozenset(
    {
        "producer",
        "consumer",
        "queue",
        "exchange",
        "server",
        "database",
        "cache",
        "document",
    }
)
_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"presentation {label}: 필드 오류")


def _text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"presentation {label}: 1~{limit}자의 짧은 텍스트 필요")


def _children(element, label):
    children = []
    for child in element.contents:
        if isinstance(child, Tag):
            children.append(child)
        elif str(child).strip():
            raise ValueError(f"presentation {label}: 구조 밖의 텍스트 금지")
    return children


def _element(element, name, classes=(), extra=()):
    expected = set(extra) | ({"class"} if classes else set())
    if (
        element.name != name
        or set(element.attrs) != expected
        or element.get("class", []) != list(classes)
    ):
        raise ValueError(f"presentation: {name}.{'.'.join(classes)} 구조 필요")


def _plain(element, name, css_class, limit):
    _element(element, name, (css_class,) if css_class else ())
    if element.find(True):
        raise ValueError("presentation: 이름과 상태에는 중첩 HTML 금지")
    _text(element.get_text(), limit, css_class or name)


def _nodes(fragment):
    if not isinstance(fragment, str):
        raise ValueError("presentation: 상태 HTML 필요")
    roots = _children(BeautifulSoup(fragment, "html.parser"), "장면")
    if not 1 <= len(roots) <= 2:
        raise ValueError("presentation: diagram-board와 선택적 diagram-ledger만 허용")
    _element(roots[0], "div", ("diagram-board",))
    nodes = _children(roots[0], "diagram-board")
    identities = []
    for node in nodes:
        classes = node.get("class", [])
        if (
            "diagram-node" not in classes
            or len(classes) != len(set(classes))
            or set(classes) - {"diagram-node", "is-active", "is-muted"}
            or {"is-active", "is-muted"}.issubset(classes)
        ):
            raise ValueError(
                "presentation: diagram-node와 선택적 상태 클래스 하나만 허용"
            )
        _element(node, "section", classes, ("data-entity",))
        entity = node["data-entity"]
        if not isinstance(entity, str) or not _ID.fullmatch(entity):
            raise ValueError("presentation: 유효한 data-entity 필요")
        parts = _children(node, "diagram-node")
        if len(parts) != 4:
            raise ValueError(
                "presentation: 노드에는 role/symbol/label/detail 네 요소 필요"
            )
        role, symbol, label, detail = parts
        _plain(role, "span", "diagram-role", 24)
        _element(symbol, "span", ("diagram-symbol",), ("data-icon",))
        icon = symbol["data-icon"]
        if (
            not isinstance(icon, str)
            or icon not in DIAGRAM_ICONS
            or symbol.find(True)
            or symbol.get_text(strip=True)
        ):
            raise ValueError("presentation: 허용된 data-icon을 지정한 빈 symbol 필요")
        _plain(label, "strong", "diagram-label", 32)
        _plain(detail, "span", "diagram-detail", 64)
        identities.append((entity, icon))
    if len({entity for entity, _ in identities}) != len(identities):
        raise ValueError("presentation: 노드 data-entity 중복")
    if len(roots) == 2:
        _element(roots[1], "div", ("diagram-ledger",))
        rows = _children(roots[1], "diagram-ledger")
        if not 1 <= len(rows) <= 2:
            raise ValueError("presentation: 결과 요약은 1~2개 항목만 허용")
        for row in rows:
            _element(row, "div")
            cells = _children(row, "결과 요약")
            if len(cells) != 2:
                raise ValueError("presentation: 결과 요약은 span 이름과 strong 값 필요")
            _plain(cells[0], "span", None, 32)
            _plain(cells[1], "strong", None, 64)
    return identities


def validate_presentation(scene: dict) -> None:
    """Reject malformed preset metadata/markup; absent presentation is a no-op.

    ``flow`` has 2–4 participants linked in order. ``branch`` has exactly four:
    source, hub, first outcome, second outcome. Their order and icons must remain
    stable across all states. The trusted renderer owns all preset CSS and SVG.
    """
    if not isinstance(scene, dict):
        raise ValueError("presentation: 장면 객체 필요")
    if "presentation" not in scene:
        return
    presentation = scene["presentation"]
    _object(presentation, {"layout", "eyebrow", "links"}, "설정")
    layout = presentation["layout"]
    if layout not in ("flow", "branch"):
        raise ValueError("presentation.layout: flow 또는 branch 필요")
    _text(presentation["eyebrow"], 48, "eyebrow")
    states = scene.get("states")
    if not isinstance(states, list) or not states:
        raise ValueError("presentation: 상태 목록 필요")
    identities = None
    for state in states:
        if not isinstance(state, dict):
            raise ValueError("presentation: 상태 객체 필요")
        current = _nodes(state.get("html"))
        if (layout == "branch" and len(current) != 4) or not 2 <= len(current) <= 4:
            raise ValueError("presentation: flow는 2~4개, branch는 4개 노드 필요")
        if identities is not None and current != identities:
            raise ValueError(
                "presentation: 모든 상태에서 노드 ID·순서·아이콘 유지 필요"
            )
        identities = current
    entities = [entity for entity, _ in identities]
    expected = (
        {
            (entities[0], entities[1]),
            (entities[1], entities[2]),
            (entities[1], entities[3]),
        }
        if layout == "branch"
        else set(zip(entities, entities[1:]))
    )
    links = presentation["links"]
    if not isinstance(links, list) or len(links) != len(expected):
        raise ValueError("presentation.links: 배치에 맞는 연결 개수 필요")
    actual = set()
    for link in links:
        _object(link, {"source", "target", "label"}, "link")
        for key in ("source", "target"):
            if not isinstance(link[key], str) or link[key] not in entities:
                raise ValueError("presentation.links: 존재하는 노드 ID 필요")
        _text(link["label"], 32, "link.label")
        actual.add((link["source"], link["target"]))
    if actual != expected:
        raise ValueError("presentation.links: 배치 순서와 연결 구조 불일치 또는 중복")
