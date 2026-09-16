"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import html as html_module
import json
import unittest

from jsonschema import Draft202012Validator

from generator.design.scene_document import (
    clean_css,
    clean_html,
    render_document,
    section_ends,
    validate_design,
)
from generator.design.scene_motion import interaction_issues, validate_scene_motion
from generator.design.visual_contracts import DESIGN_SCHEMA
from generator.tests.fixtures.design import DESIGN_BODY, design_candidate
from generator.tests.fixtures.scenes import (
    MOTION_BODY,
    effect_scene,
    motion_design,
    motion_scene,
)


class SceneValidationTest(unittest.TestCase):
    def test_playback_requires_a_finite_existing_transition_path(self):
        value = design_candidate()
        value["scenes"][0]["playback"]["steps"] = ["start", "confirmed"]
        self.assertEqual(
            validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]["playback"][
                "steps"
            ],
            ["start", "confirmed"],
        )
        for steps in [
            ["confirmed", "start"],
            ["start", "missing"],
            ["start", "confirmed", "start"],
            ["start"],
        ]:
            invalid = copy.deepcopy(value)
            invalid["scenes"][0]["playback"]["steps"] = steps
            with self.assertRaises(ValueError):
                validate_design(json.dumps(invalid), DESIGN_BODY)
        value["scenes"][0]["playback"]["interval_ms"] = 10
        with self.assertRaises(ValueError):
            validate_design(json.dumps(value), DESIGN_BODY)

    def test_legacy_scene_without_playback_remains_readable(self):
        value = design_candidate()
        del value["scenes"][0]["playback"]
        self.assertEqual(
            validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]["playback"][
                "steps"
            ],
            [],
        )

    def test_valid_design_and_document_security(self):
        scene = validate_design(json.dumps(design_candidate()), DESIGN_BODY)["scenes"][
            0
        ]
        document = render_document(scene)
        self.assertIn("default-src &#x27;none&#x27;", document)
        self.assertIn("sha256-", document)
        self.assertIn("<noscript>", document)
        self.assertNotIn('src="http', document)

    def test_script_url_event_and_form_rejected(self):
        for text in [
            "<script>alert(1)</script>",
            '<p onclick="x()">text</p>',
            '<img src="https://example.com">',
            '<a href="javascript:alert(1)">x</a>',
            '<svg onload="x()"></svg>',
            '<div style="color:red">x</div>',
            "<form>x</form>",
        ]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                clean_html(text)

    def test_css_network_execution_and_scope_rejected(self):
        for css in [
            '@import "https://example.com";',
            ".scene-content {background:url(https://example.com)}",
            '.scene-content {background:image-set("https://example.com")}',
            "body {color:red}",
            ".scene-content + #scene-controls {display:none}",
            ".scene-content {color:red!important}",
            ".scene-content {width:expression(alert(1))}",
            ".scene-content .board {animation:pulse 1s infinite}",
            ".scene-content .board {transition:all 2s}",
            ".scene-content {color:red}</style><script>x()</script>",
        ]:
            with self.subTest(css=css), self.assertRaises(ValueError):
                clean_css(css)

    def test_mobile_css_is_accepted(self):
        self.assertIn(
            "@media",
            clean_css(
                "@media(max-width:400px){.scene-content .board {grid-template-columns:1fr}}"
            ),
        )

    def test_invalid_target_initial_unreachable_and_extra_js_rejected(self):
        for kind in ("target", "initial", "unreachable", "javascript"):
            value = design_candidate()
            scene = value["scenes"][0]
            if kind == "target":
                scene["states"][0]["actions"][0]["target"] = "missing"
            if kind == "initial":
                scene["initial"] = "missing"
            if kind == "unreachable":
                scene["states"][0]["actions"] = []
            if kind == "javascript":
                scene["js"] = "alert(1)"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_design(json.dumps(value), DESIGN_BODY)

    def test_missing_or_duplicate_heading_rejected(self):
        with self.assertRaises(ValueError):
            validate_design(json.dumps(design_candidate()), "### 다른 제목\n본문")
        with self.assertRaises(ValueError):
            validate_design(
                json.dumps(design_candidate()),
                DESIGN_BODY + "\n### 두 확인의 차이\n본문",
            )

    def test_code_fence_headings_are_not_anchors(self):
        body = "### 개요\n```md\n### 가짜\n```\n설명\n### 정리\n끝"
        self.assertEqual(list(section_ends(body)), ["개요"])
        self.assertEqual(body[section_ends(body)["개요"] :], "### 정리\n끝")

    def test_html_is_normalized_and_liquid_remains_inert_in_json_script(self):
        value = design_candidate()
        value["scenes"][0]["states"][0]["description"] = (
            "</script><script>alert(1)</script>"
        )
        scene = validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]
        doc = render_document(scene)
        self.assertIn("\\u003c/script", doc)
        self.assertNotIn("<script>alert(1)</script>", doc)


class SceneEffectsValidationTest(unittest.TestCase):
    def test_effects_are_optional_and_survive_all_validators(self):
        scene = effect_scene()
        value = {"summary": "가상 정책 비교", "scenes": [scene]}
        self.assertTrue(Draft202012Validator(DESIGN_SCHEMA).is_valid(value))
        actual = validate_design(json.dumps(value), MOTION_BODY)
        self.assertEqual(actual["scenes"][0]["effects"], scene["effects"])
        self.assertEqual(interaction_issues(actual), [])

    def test_rejects_bad_edges_fields_durations_and_unchanged_text(self):
        mutations = [
            lambda s: s["effects"][0].update({"from": "missing"}),
            lambda s: s["effects"][0].update({"to": "ready"}),
            lambda s: s["effects"].append(copy.deepcopy(s["effects"][0])),
            lambda s: s["effects"][0].update({"kind": "javascript"}),
            lambda s: s["effects"][0].update({"duration_ms": True}),
            lambda s: s["effects"][0].update({"duration_ms": 599}),
            lambda s: s["effects"][0].update({"duration_ms": 2401}),
            lambda s: s["effects"][0].update({"entities": ["policy"]}),
            lambda s: s["effects"][0].update({"entities": ["result", "result"]}),
            lambda s: s["effects"][0].update({"entities": []}),
            lambda s: s["effects"][0].update({"entities": ["absent"]}),
            lambda s: s["effects"][0].update({"js": "alert(1)"}),
            lambda s: s["states"][1].update({"html": s["states"][0]["html"]}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                scene = effect_scene()
                mutate(scene)
                with self.assertRaises(ValueError):
                    validate_scene_motion(scene)

    def test_transfer_and_effect_cannot_compete_for_same_edge(self):
        scene = motion_scene()
        scene["effects"] = [
            {
                "from": "ready",
                "to": "accepted",
                "kind": "compare",
                "entities": ["result"],
                "duration_ms": 1200,
            }
        ]
        with self.assertRaisesRegex(ValueError, "중복"):
            validate_scene_motion(scene)

    def test_interaction_requires_all_buttons_to_have_effect_or_transfer(self):
        scene = effect_scene()
        scene["effects"].pop()
        self.assertTrue(interaction_issues({"scenes": [scene]}))

    def test_icons_are_allowlisted_not_arbitrary_svg_or_javascript(self):
        self.assertIn(
            'data-icon="document"',
            clean_html('<p>규칙<span data-icon="document"></span></p>'),
        )
        for fragment in (
            '<p><span data-icon="unknown"></span>규칙</p>',
            "<svg></svg>",
            '<p onclick="alert(1)">규칙</p>',
        ):
            with self.assertRaises(ValueError):
                clean_html(fragment)
        scene = effect_scene()
        document = render_document(scene)
        self.assertIn("function icons(content)", document)
        self.assertIn("connect-src 'none'", html_module.unescape(document))


class SceneMotionValidationTest(unittest.TestCase):
    def test_optional_contract_accepts_legacy_scenes(self):
        scene = motion_scene()
        del scene["transitions"]
        del scene["scenarios"]
        validate_scene_motion(scene)
        self.assertTrue(
            Draft202012Validator(DESIGN_SCHEMA).is_valid(motion_design(scene))
        )
        self.assertNotIn(
            "transitions", DESIGN_SCHEMA["properties"]["scenes"]["items"]["required"]
        )
        validated = validate_design(json.dumps(motion_design(scene)), MOTION_BODY)
        self.assertNotIn("transitions", validated["scenes"][0])

    def test_valid_new_fields_survive_full_design_validation(self):
        value = motion_design()
        validate_scene_motion(value["scenes"][0])
        self.assertTrue(Draft202012Validator(DESIGN_SCHEMA).is_valid(value))
        actual = validate_design(json.dumps(value), MOTION_BODY)
        self.assertEqual(
            actual["scenes"][0]["transitions"], value["scenes"][0]["transitions"]
        )
        self.assertEqual(
            actual["scenes"][0]["scenarios"], value["scenes"][0]["scenarios"]
        )

    def test_transition_must_be_unique_non_self_actual_action_edge(self):
        mutations = [
            lambda s: s["transitions"].append(copy.deepcopy(s["transitions"][0])),
            lambda s: s["transitions"][0].update({"from": "missing"}),
            lambda s: s["transitions"][0].update({"to": "missing"}),
            lambda s: s["transitions"][0].update({"to": "ready"}),
            lambda s: s["transitions"][0].update(
                {"from": "accepted", "to": "rejected"}
            ),
            lambda s: s["transitions"][0].update({"from": []}),
            lambda s: s["transitions"][0].update({"extra": "unsupported"}),
        ]
        for change in mutations:
            with self.subTest(change=change):
                scene = motion_scene()
                change(scene)
                with self.assertRaises(ValueError):
                    validate_scene_motion(scene)

    def test_both_distinct_anchors_are_required_in_every_state(self):
        for endpoint in ("missing", "source", [], None, "Not_valid"):
            with self.subTest(endpoint=endpoint):
                scene = motion_scene()
                scene["transitions"][0]["steps"][0]["target"] = endpoint
                with self.assertRaises(ValueError):
                    validate_scene_motion(scene)
        for html in (
            '<p data-entity="source">보내는 쪽</p>',
            '<p data-entity="source">보내는 쪽</p><p data-entity="destination"></p>',
        ):
            scene = motion_scene()
            scene["states"][-1]["html"] = html
            with self.assertRaisesRegex(ValueError, "모든 상태"):
                validate_scene_motion(scene)

    def test_transition_duration_and_step_budgets(self):
        for duration in (True, False, 600.0, "1200", None, 599, 2401, -1):
            with self.subTest(duration=duration):
                scene = motion_scene()
                scene["transitions"][0]["steps"][0]["duration_ms"] = duration
                with self.assertRaises(ValueError):
                    validate_scene_motion(scene)
        for count, duration, valid in (
            (1, 600, True),
            (4, 2000, True),
            (4, 2100, False),
            (0, 1200, False),
            (5, 600, False),
        ):
            with self.subTest(count=count, duration=duration):
                scene = motion_scene()
                step = scene["transitions"][0]["steps"][0]
                step["duration_ms"] = duration
                scene["transitions"][0]["steps"] = [
                    copy.deepcopy(step) for _ in range(count)
                ]
                if valid:
                    validate_scene_motion(scene)
                else:
                    with self.assertRaises(ValueError):
                        validate_scene_motion(scene)
        scene = motion_scene()
        scene["transitions"] *= 17
        with self.assertRaisesRegex(ValueError, "최대 32"):
            validate_scene_motion(scene)

    def test_invalid_nested_types_and_blank_labels_rejected(self):
        for field in ("transitions", "scenarios"):
            for value in (None, True, "", {}, 1):
                with self.subTest(field=field, value=value):
                    scene = motion_scene()
                    scene[field] = value
                    with self.assertRaises(ValueError):
                        validate_scene_motion(scene)
        for label in (None, [], "", "  \n", "a" * 41):
            scene = motion_scene()
            scene["transitions"][0]["steps"][0]["label"] = label
            with self.assertRaises(ValueError):
                validate_scene_motion(scene)
        for steps in (None, {}, [None], [[]], [{"source": "source"}]):
            scene = motion_scene()
            scene["transitions"][0]["steps"] = steps
            with self.assertRaises(ValueError):
                validate_scene_motion(scene)

    def test_scenario_ids_labels_routes_and_edges_are_checked(self):
        mutations = [
            lambda s: s["scenarios"][1].update({"id": "accept"}),
            lambda s: s["scenarios"][1].update({"label": " 조건 충족 "}),
            lambda s: s["scenarios"][1].update({"steps": ["ready", "accepted"]}),
            lambda s: s["scenarios"][1].update({"steps": ["rejected", "ready"]}),
            lambda s: s["scenarios"][1].update({"steps": ["ready", "unknown"]}),
            lambda s: s["scenarios"][1].update(
                {"steps": ["ready", "accepted", "rejected"]}
            ),
            lambda s: s["scenarios"][1].update(
                {"steps": ["ready", "accepted", "ready"]}
            ),
            lambda s: s["scenarios"][1].update({"steps": ["ready"]}),
            lambda s: s["scenarios"][1].update({"steps": ["ready", {}]}),
            lambda s: s["scenarios"][1].update({"steps": None}),
            lambda s: s["scenarios"][1].update({"id": "BAD ID"}),
            lambda s: s["scenarios"][1].update({"label": " "}),
            lambda s: s["scenarios"].pop(),
            lambda s: s["scenarios"].extend(copy.deepcopy(s["scenarios"])),
        ]
        for change in mutations:
            with self.subTest(change=change):
                scene = motion_scene()
                change(scene)
                with self.assertRaises(ValueError):
                    validate_scene_motion(scene)

    def test_full_validation_rejects_unreachable_state_and_unsafe_anchor_html(self):
        scene = motion_scene()
        scene["states"][0]["actions"].pop()
        with self.assertRaisesRegex(ValueError, "도달할 수 없는 상태"):
            validate_design(json.dumps(motion_design(scene)), MOTION_BODY)
        scene = motion_scene()
        scene["states"][0]["html"] += '<p data-entity="source">중복</p>'
        with self.assertRaisesRegex(ValueError, "중복"):
            validate_design(json.dumps(motion_design(scene)), MOTION_BODY)


class InteractionPolicyTest(unittest.TestCase):
    def test_supported_scenarios_and_branch_only_both_pass(self):
        value = motion_design()
        self.assertEqual(interaction_issues(value), [])
        del value["scenes"][0]["scenarios"]
        self.assertEqual(interaction_issues(value), [])

    def test_border_only_branch_and_linear_transfer_are_not_sufficient(self):
        value = motion_design()
        del value["scenes"][0]["transitions"]
        issues = interaction_issues(value)
        self.assertEqual(issues[0]["scene_index"], 0)
        self.assertIn("transitions", issues[0]["path"])
        scene = motion_scene()
        scene["states"].pop()
        scene["states"][0]["actions"].pop()
        scene["transitions"].pop()
        del scene["scenarios"]
        self.assertIn("scenarios", interaction_issues(motion_design(scene))[0]["path"])

    def test_every_selected_scenario_and_branch_edge_needs_transfer(self):
        for keep_scenarios in (True, False):
            value = motion_design()
            value["scenes"][0]["transitions"].pop()
            if not keep_scenarios:
                del value["scenes"][0]["scenarios"]
            issues = interaction_issues(value)
            self.assertIn("ready → rejected", issues[0]["message"])

    def test_off_scenario_linear_button_also_requires_transfer(self):
        scene = motion_scene()
        followup = copy.deepcopy(scene["states"][1])
        followup["id"] = "followup"
        scene["states"].append(followup)
        scene["states"][1]["actions"] = [{"label": "후속 단계", "target": "followup"}]
        issues = interaction_issues(motion_design(scene))
        self.assertIn("accepted → followup", issues[0]["message"])

    def test_default_playback_route_is_required_and_matches_a_scenario(self):
        for steps in ([], None, ["ready"], ["accepted", "rejected"], ["ready", {}]):
            with self.subTest(steps=steps):
                scene = motion_scene()
                scene["playback"]["steps"] = steps
                self.assertTrue(
                    any(
                        "playback.steps" in item["path"]
                        for item in interaction_issues(motion_design(scene))
                    )
                )
        scene = motion_scene()
        scene["states"][1]["actions"] = [{"label": "다른 결과", "target": "rejected"}]
        transition = copy.deepcopy(scene["transitions"][1])
        transition["from"] = "accepted"
        scene["transitions"].append(transition)
        scene["playback"]["steps"] = ["ready", "accepted", "rejected"]
        issues = interaction_issues(motion_design(scene))
        self.assertIn("시나리오 중 하나", issues[0]["message"])
        scene["playback"]["steps"] = ["ready", "rejected"]
        self.assertEqual(interaction_issues(motion_design(scene)), [])

    def test_independent_missing_interaction_requirements_are_collected(self):
        scene = motion_scene()
        del scene["transitions"]
        scene["playback"]["steps"] = []
        paths = {item["path"] for item in interaction_issues(motion_design(scene))}
        self.assertEqual(paths, {"scenes[0].transitions", "scenes[0].playback.steps"})

    def test_one_supported_scene_allows_static_secondary_diagram(self):
        value = motion_design()
        other = motion_scene()
        other["states"] = [other["states"][0]]
        other["states"][0]["actions"] = []
        for field in ("transitions", "scenarios"):
            del other[field]
        other["playback"]["steps"] = []
        value["scenes"].append(other)
        self.assertEqual(interaction_issues(value), [])
        value["scenes"].pop(0)
        issues = interaction_issues(value)
        self.assertIsNone(issues[0]["scene_index"])
        self.assertEqual(issues[0]["path"], "scenes")

    def test_malformed_declared_motion_cannot_satisfy_policy(self):
        value = motion_design()
        value["scenes"][0]["transitions"][0]["steps"][0]["target"] = "source"
        self.assertTrue(interaction_issues(value))
