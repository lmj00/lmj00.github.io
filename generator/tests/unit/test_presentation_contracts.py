"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import json
import unittest
from copy import deepcopy

from jsonschema import Draft202012Validator

from generator.design.scene_charts import chart_fallback_html, validate_scene_charts
from generator.design.scene_document import clean_html, render_document, validate_design
from generator.design.scene_motion import validate_scene_motion
from generator.design.scene_presentation import DIAGRAM_ICONS, validate_presentation
from generator.design.visual_contracts import (
    DESIGN_SCHEMA,
    SCENE_PRESENTATION_SCHEMA,
    SCENE_TRANSITIONS_SCHEMA,
)
from generator.tests.fixtures.design import DESIGN_BODY
from generator.tests.fixtures.scenes import (
    diagram_candidate,
    diagram_node,
    numeric_scene,
    presentation_scene,
)


class DiagramIntegrationTest(unittest.TestCase):
    def test_validates_and_embeds_only_trusted_css_and_icons(self):
        value = diagram_candidate()
        value["scenes"][0]["css"] = ".scene-content .board {color:magenta}"
        scene = validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]
        document = render_document(scene)
        self.assertIn('class="diagram-scene"', document)
        self.assertNotIn("color:magenta", document.split("</style>")[0])
        self.assertIn("window.ArticleDiagram", document)
        self.assertIn("script-src 'sha256-", document.replace("&#x27;", "'"))
        self.assertNotIn("<svg", scene["states"][0]["html"])

    def test_arbitrary_svg_and_icon_names_remain_rejected(self):
        for fragment in (
            '<span data-icon="https://example.test/icon.svg">icon</span>',
            '<span data-icon="server"><svg></svg></span>',
        ):
            with self.assertRaises(ValueError):
                clean_html(fragment)

    def test_signal_kind_validator_rejects_malformed_values(self):
        scene = diagram_candidate()["scenes"][0]
        validate_scene_motion(scene)
        for kind in ("javascript", [], {}, None, 2):
            value = copy.deepcopy(scene)
            value["transitions"][0]["steps"][0]["kind"] = kind
            with self.assertRaises(ValueError):
                validate_scene_motion(value)


class SceneChartsContractTest(unittest.TestCase):
    def test_chart_owned_svg_selectors_rejected_only_when_charts_exist(self):
        for css in (
            ".scene-content svg {stroke:none;fill:none}",
            ".scene-content .scene-chart-graphic {height:1px}",
            ".scene-content polyline {stroke:transparent}",
            '.scene-content [data-chart-for="measure"] {width:1px}',
            "@media(max-width:400px){.scene-content circle {r:0}}",
        ):
            with self.subTest(css=css):
                scene = numeric_scene()
                scene["css"] = css
                with self.assertRaisesRegex(ValueError, "공통 차트/SVG"):
                    validate_scene_charts(scene)
                scene.pop("charts")
                validate_scene_charts(scene)

    def test_no_javascript_fallback_contains_all_series_values_and_labels(self):
        scene = numeric_scene()
        fallback = chart_fallback_html(scene)
        self.assertIn("설명용 가상 수치", fallback)
        self.assertIn("누적 완료 요청", fallback)
        self.assertIn("현재 진행 중인 요청", fallback)
        self.assertIn("3 · 두 번째 요청 완료", fallback)
        self.assertEqual(fallback.count("<td>"), 6)
        self.assertEqual(chart_fallback_html({}), "")

    def test_legacy_and_empty_are_unchanged(self):
        for scene in ({}, {"charts": []}, numeric_scene(), numeric_scene("bar")):
            before = deepcopy(scene)
            validate_scene_charts(scene)
            self.assertEqual(scene, before)

    def test_nonfinite_bool_large_and_wrong_count_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "1", 1e13):
            with self.subTest(value=value), self.assertRaises(ValueError):
                scene = numeric_scene()
                scene["charts"][0]["series"][0]["values"][1] = value
                validate_scene_charts(scene)
        scene = numeric_scene()
        scene["charts"][0]["series"][0]["values"].append(1)
        with self.assertRaisesRegex(ValueError, "개수가 같아야"):
            validate_scene_charts(scene)

    def test_view_coverage_ids_and_count(self):
        mutations = [
            lambda c: c["views"].pop(),
            lambda c: c["views"].append(deepcopy(c["views"][0])),
            lambda c: c["views"][0].update(state="nonexistent"),
            lambda c: c["views"][0].update(active_series=["unknown"]),
            lambda c: c["views"][0].update(active_series=["count", "count"]),
            lambda c: c["views"][0].update(visible_points=4),
            lambda c: c["series"][1].update(id="count"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                scene = numeric_scene()
                mutate(scene["charts"][0])
                validate_scene_charts(scene)

    def test_partial_reveal_only_process(self):
        for mode in ("compare", "explore", None):
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(ValueError, "process만"),
            ):
                scene = numeric_scene(mode=mode)
                scene["charts"][0]["views"][0]["visible_points"] = 1
                validate_scene_charts(scene)
        scene = numeric_scene(mode="process")
        scene["charts"][0]["views"][0]["visible_points"] = 1
        validate_scene_charts(scene)

    def test_readable_unique_block_host_in_every_state(self):
        fragments = [
            '<div data-entity="other">누적 완료</div>',
            '<div data-entity="measure">A</div><div data-entity="measure">B</div>',
            '<span data-entity="measure">설명</span>',
            '<div data-entity="measure"><span hidden>설명</span></div>',
            '<div data-entity="measure"><span data-entity="nested">설명</span></div>',
            '<div data-entity="outer"><div data-entity="measure">설명</div></div>',
            '<table><tr><td><div data-entity="measure">설명</div></td></tr></table>',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                scene = numeric_scene()
                scene["states"][1]["html"] = fragment
                validate_scene_charts(scene)

    def test_caption_and_text_do_not_accept_markup_or_hidden_text(self):
        for field, value in (
            ("caption", "실제 운영 측정 결과"),
            ("label", "<img src=x>"),
            ("unit", "\x01"),
            ("label", "   "),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                scene = numeric_scene()
                scene["charts"][0][field] = value
                validate_scene_charts(scene)

    def test_numeric_edge_cases_keep_signed_zero_and_decimal_values(self):
        for values in (
            [0, 0, 0],
            [-5, -5, -5],
            [-4, 0, 9],
            [0.1, 0.2, 0.3],
            [1e-20, 0, 1e12],
        ):
            scene = numeric_scene("bar")
            scene["charts"][0]["series"][0]["values"] = values
            validate_scene_charts(scene)

    def test_fallback_escapes_plain_punctuation(self):
        scene = numeric_scene()
        scene["charts"][0]["label"] = 'A & B "비교"'
        self.assertIn("A &amp; B &quot;비교&quot;", chart_fallback_html(scene))

    def test_no_unbounded_or_executable_chart_options(self):
        for field, value in (
            ("onclick", "fetch('/secret')"),
            ("url", "https://example.org/data"),
            ("kind", "svg"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                scene = numeric_scene()
                scene["charts"][0][field] = value
                validate_scene_charts(scene)
        scene = numeric_scene()
        scene["charts"].append(deepcopy(scene["charts"][0]))
        with self.assertRaisesRegex(ValueError, "host 중복"):
            validate_scene_charts(scene)


class ScenePresentationTest(unittest.TestCase):
    def test_legacy_scenes_are_a_no_op(self):
        for legacy in ({}, {"states": [{"html": "<p>기존 장면</p>"}]}):
            validate_presentation(legacy)
        self.assertNotIn(
            "presentation", DESIGN_SCHEMA["properties"]["scenes"]["items"]["required"]
        )

    def test_flow_two_to_four_and_four_node_branch_are_valid_without_mutation(self):
        for layout, count in (("flow", 2), ("flow", 3), ("flow", 4), ("branch", 4)):
            with self.subTest(layout=layout, count=count):
                value = presentation_scene(layout, count)
                original = copy.deepcopy(value)
                validate_presentation(value)
                self.assertEqual(value, original)
                Draft202012Validator(SCENE_PRESENTATION_SCHEMA).validate(
                    value["presentation"]
                )

    def test_plain_labels_status_modifiers_and_short_ledger_are_allowed(self):
        value = presentation_scene()
        value["states"][0]["html"] = value["states"][0]["html"].replace(
            'class="diagram-node"', 'class="diagram-node is-active"', 1
        )
        value["states"][1]["html"] = value["states"][1]["html"].replace(
            'class="diagram-node"', 'class="diagram-node is-muted"', 1
        )
        ledger = (
            '<div class="diagram-ledger"><div><span>요청 상태</span>'
            "<strong>처리 완료</strong></div><div><span>다음 대상</span>"
            "<strong>응답 서버</strong></div></div>"
        )
        for state in value["states"]:
            state["html"] += ledger
        validate_presentation(value)

    def test_all_icons_are_allowed_but_must_remain_stable(self):
        for icon in DIAGRAM_ICONS:
            value = presentation_scene()
            for state in value["states"]:
                state["html"] = state["html"].replace(
                    'data-icon="server"', f'data-icon="{icon}"'
                )
            validate_presentation(value)
        value["states"][1]["html"] = value["states"][1]["html"].replace(
            f'data-icon="{icon}"',
            'data-icon="producer"' if icon != "producer" else 'data-icon="consumer"',
            1,
        )
        with self.assertRaisesRegex(ValueError, "아이콘 유지"):
            validate_presentation(value)

    def test_node_order_and_identity_must_be_stable(self):
        for replacement in (
            diagram_node("hub") + diagram_node("sender") + diagram_node("primary"),
            diagram_node("sender") + diagram_node("hub") + diagram_node("other"),
        ):
            value = presentation_scene()
            value["states"][1]["html"] = (
                f'<div class="diagram-board">{replacement}</div>'
            )
            with self.assertRaisesRegex(ValueError, "노드 ID·순서"):
                validate_presentation(value)

    def test_metadata_fields_are_strict_and_bounded(self):
        changes = (
            lambda p: p.update(extra=True),
            lambda p: p.pop("links"),
            lambda p: p.update(layout="cards"),
            lambda p: p.update(layout=[]),
            lambda p: p.update(eyebrow=" "),
            lambda p: p.update(eyebrow="x" * 49),
            lambda p: p.update(links={}),
            lambda p: p["links"][0].update(label=""),
            lambda p: p["links"][0].update(label="x" * 33),
            lambda p: p["links"][0].update(source=[]),
            lambda p: p["links"][0].update(target="unknown"),
            lambda p: p["links"][0].update(url="https://example.test"),
        )
        for change in changes:
            value = presentation_scene()
            change(value["presentation"])
            with (
                self.subTest(presentation=value["presentation"]),
                self.assertRaises(ValueError),
            ):
                validate_presentation(value)

    def test_links_match_layout_topology_and_are_not_duplicates(self):
        for layout, count in (("flow", 3), ("branch", 4)):
            for source, target in (
                ("sender", "primary"),
                ("hub", "sender"),
                ("sender", "sender"),
            ):
                value = presentation_scene(layout, count)
                value["presentation"]["links"][0].update(source=source, target=target)
                with (
                    self.subTest(layout=layout, edge=(source, target)),
                    self.assertRaises(ValueError),
                ):
                    validate_presentation(value)
            value = presentation_scene(layout, count)
            value["presentation"]["links"][1] = copy.deepcopy(
                value["presentation"]["links"][0]
            )
            with self.assertRaises(ValueError):
                validate_presentation(value)

    def test_branch_requires_exactly_four_nodes(self):
        value = presentation_scene()
        value["presentation"]["layout"] = "branch"
        with self.assertRaisesRegex(ValueError, "4개 노드"):
            validate_presentation(value)

    def test_markup_rejects_extra_structure_attributes_nested_labels_and_long_copy(
        self,
    ):
        replacements = (
            ('class="diagram-board"', 'class="diagram-board cards"'),
            ('class="diagram-node"', 'class="diagram-node extra"'),
            ('class="diagram-node"', 'class="diagram-node is-muted is-active"'),
            ('data-entity="hub"', 'data-entity="sender"'),
            ('data-icon="server"', 'data-icon="rabbitmq"'),
            ('data-icon="server"', 'data-icon="server" style="color:red"'),
            ('data-icon="server"></span>', 'data-icon="server">★</span>'),
            ('data-icon="server"></span>', 'data-icon="server"><svg></svg></span>'),
            ('class="diagram-role">처리 주체', 'class="diagram-role">' + "긴" * 25),
            ('class="diagram-label">sender', 'class="diagram-label">' + "긴" * 33),
            ('class="diagram-detail">대기', 'class="diagram-detail">' + "긴" * 65),
            ('class="diagram-label">sender', 'class="diagram-label"><em>sender</em>'),
            ('class="diagram-label">sender', 'class="diagram-label">'),
            ("</section>", "<p>추가 문단</p></section>"),
        )
        for old, new in replacements:
            value = presentation_scene()
            value["states"][0]["html"] = value["states"][0]["html"].replace(old, new, 1)
            with self.subTest(replacement=new), self.assertRaises(ValueError):
                validate_presentation(value)
        for extra in ("설명", "<p>추가 문단</p>", '<div class="diagram-ledger"></div>'):
            value = presentation_scene()
            value["states"][0]["html"] += extra
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_presentation(value)

    def test_signal_kind_schema_is_optional_and_bounded(self):
        transition = {
            "from": "ready",
            "to": "done",
            "steps": [
                {
                    "source": "sender",
                    "target": "hub",
                    "label": "확인",
                    "duration_ms": 1200,
                }
            ],
        }
        validator = Draft202012Validator(SCENE_TRANSITIONS_SCHEMA)
        validator.validate([transition])
        for kind in ("signal", "message"):
            transition["steps"][0]["kind"] = kind
            validator.validate([transition])
        transition["steps"][0]["kind"] = "executable"
        self.assertFalse(validator.is_valid([transition]))
