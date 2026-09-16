"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import json
import unittest

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from generator.design.compact_scenes import (
    build_compact_schema,
    compile_compact_design,
)
from generator.design.scene_document import validate_design
from generator.design.visual_contracts import DESIGN_SCHEMA
from generator.tests.fixtures.design import (
    COMPACT_BODY,
    EXCERPTS,
    HEADINGS,
    compact_design,
)


class CompactSceneTests(unittest.TestCase):
    def compile(self, value=None):
        return compile_compact_design(value or compact_design(), HEADINGS, EXCERPTS)

    def test_schema_is_valid_independent_and_uses_caller_owned_enums(self):
        original = copy.deepcopy(DESIGN_SCHEMA)
        schema = build_compact_schema(HEADINGS, EXCERPTS)
        Draft202012Validator.check_schema(schema)
        self.assertTrue(Draft202012Validator(schema).is_valid(compact_design()))
        scene = schema["properties"]["scenes"]["items"]
        self.assertEqual(scene["properties"]["heading_id"]["enum"], list(HEADINGS))
        evidence = scene["properties"]["explanation"]["properties"]["excerpt_ids"]
        self.assertEqual(
            evidence["items"]["enum"], [item["excerpt_id"] for item in EXCERPTS]
        )
        self.assertNotIn("presentation", scene["required"])
        self.assertNotIn("html", scene["properties"]["states"]["items"]["properties"])
        schema["properties"]["summary"]["maxLength"] = 1
        self.assertEqual(DESIGN_SCHEMA, original)

    def test_compiles_template_values_ids_classes_without_mutating_inputs(self):
        value = compact_design()
        before = copy.deepcopy((value, HEADINGS, EXCERPTS))
        actual = self.compile(value)
        self.assertEqual((value, HEADINGS, EXCERPTS), before)
        scene = actual["scenes"][0]
        self.assertEqual(scene["after_heading"], "조건 적용")
        self.assertNotIn("html", scene)
        self.assertNotIn("heading_id", scene)
        self.assertNotIn("presentation", scene)
        self.assertEqual(
            scene["explanation"]["evidence"],
            [{k: EXCERPTS[0][k] for k in ("source_url", "quote")}],
        )
        self.assertNotIn("excerpt_ids", scene["explanation"])
        for state, text, classes in zip(
            scene["states"],
            ("대기", "허용", "거절"),
            ([], ["is-success"], ["is-error"]),
        ):
            self.assertNotIn("values", state)
            self.assertNotIn("entity_classes", state)
            soup = BeautifulSoup(state["html"], "html.parser")
            self.assertEqual(soup.strong.get_text(), text)
            self.assertEqual(soup.section["class"], ["policy-card"] + classes)
            self.assertEqual(soup.section["data-entity"], "request")
        self.assertTrue(Draft202012Validator(DESIGN_SCHEMA).is_valid(actual))
        self.assertEqual(validate_design(json.dumps(actual), COMPACT_BODY), actual)

    def test_json_input_and_repeated_text_slots_are_supported(self):
        value = compact_design()
        value["scenes"][0]["html"] += "<p>다시: {{result}}</p>"
        actual = compile_compact_design(json.dumps(value), HEADINGS, EXCERPTS)
        self.assertEqual(actual["scenes"][0]["states"][1]["html"].count("허용"), 2)

    def test_new_generation_excludes_presentation_but_saved_compact_still_compiles(
        self,
    ):
        value = compact_design()
        presentation = {
            "layout": "flow",
            "eyebrow": "기존 저장 프리셋",
            "links": [{"source": "request", "target": "result", "label": "확인"}],
        }
        value["scenes"][0]["presentation"] = presentation
        self.assertFalse(
            Draft202012Validator(build_compact_schema(HEADINGS, EXCERPTS)).is_valid(
                value
            )
        )
        compatible = build_compact_schema(HEADINGS, EXCERPTS, allow_presentation=True)
        self.assertTrue(Draft202012Validator(compatible).is_valid(value))
        self.assertEqual(self.compile(value)["scenes"][0]["presentation"], presentation)
        # Compilation compatibility does not waive the preset's HTML/topology check.
        with self.assertRaises(ValueError):
            validate_design(json.dumps(self.compile(value)), COMPACT_BODY)

    def test_values_are_plain_text_not_html_attributes_or_entities(self):
        value = compact_design()
        text = '<script>alert("x")</script><img src=x onerror=alert(1)> &lt;b&gt; & "'
        value["scenes"][0]["states"][0]["values"][0]["value"] = text
        fragment = self.compile(value)["scenes"][0]["states"][0]["html"]
        soup = BeautifulSoup(fragment, "html.parser")
        self.assertIsNone(soup.script)
        self.assertIsNone(soup.img)
        self.assertEqual(soup.p.get_text(), text)
        self.assertNotIn("<script>", fragment)
        self.assertIn("&amp;lt;b&amp;gt;", fragment)

    def test_missing_unknown_and_duplicate_values_are_rejected_with_state_path(self):
        mutations = [
            lambda values: values.pop(),
            lambda values: values.append({"binding": "unknown", "value": "x"}),
            lambda values: values.append(copy.deepcopy(values[0])),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                value = compact_design()
                mutate(value["scenes"][0]["states"][0]["values"])
                with self.assertRaisesRegex(
                    ValueError, "compact/scenes/0/states/0/values"
                ):
                    self.compile(value)

    def test_empty_text_value_is_allowed_if_entity_still_has_readable_label(self):
        value = compact_design()
        value["scenes"][0]["states"][0]["values"][0]["value"] = ""
        self.compile(value)

    def test_values_cannot_hide_unresolved_bindings(self):
        for text in ("{{missing}}", "{{", "}}"):
            with self.subTest(text=text):
                value = compact_design()
                value["scenes"][0]["states"][0]["values"][0]["value"] = text
                with self.assertRaisesRegex(ValueError, "values/condition"):
                    self.compile(value)

    def test_attribute_comment_and_css_bindings_are_forbidden(self):
        fragments = (
            '<p class="{{condition}}">{{result}}</p>',
            '<p data-entity="{{condition}}">{{result}}</p>',
            '<p title="&#123;&#123;condition&#125;&#125;">{{result}}</p>',
            '<p {{condition}}="x">{{result}}</p>',
            "<!-- {{condition}} --><p>{{result}}</p>",
        )
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                value = compact_design()
                value["scenes"][0]["html"] = fragment
                with self.assertRaisesRegex(ValueError, "compact/scenes/0/html"):
                    self.compile(value)
        value = compact_design()
        value["scenes"][0]["css"] = ".scene-content {color:{{condition}}}"
        with self.assertRaisesRegex(ValueError, "compact/scenes/0/css"):
            self.compile(value)

    def test_malformed_template_bindings_are_rejected(self):
        for text in (
            "{{ condition }}",
            "{{Condition}}",
            "{{result",
            "result}}",
            "{{a.b}}",
        ):
            with self.subTest(text=text):
                value = compact_design()
                value["scenes"][0]["html"] += f"<p>{text}</p>"
                with self.assertRaisesRegex(ValueError, "malformed text binding"):
                    self.compile(value)

    def test_no_binding_static_template_is_supported(self):
        value = compact_design()
        scene = value["scenes"][0]
        scene["html"] = '<p data-entity="request">요청</p>'
        for state in scene["states"]:
            state["values"] = []
        self.compile(value)

    def test_untrusted_template_and_css_are_rejected(self):
        for fragment in (
            "<script>alert(1)</script>",
            '<p onclick="x()">요청</p>',
            '<iframe src="https://example.test"></iframe>',
        ):
            with self.subTest(fragment=fragment):
                value = compact_design()
                value["scenes"][0]["html"] += fragment
                with self.assertRaisesRegex(ValueError, "compact/scenes/0/html"):
                    self.compile(value)
        value = compact_design()
        value["scenes"][0]["css"] = (
            '.scene-content {background:url("https://example.test")} '
        )
        with self.assertRaisesRegex(ValueError, "compact/scenes/0/css"):
            self.compile(value)

    def test_duplicate_entities_and_empty_rendered_entity_are_rejected(self):
        value = compact_design()
        value["scenes"][0]["html"] += '<p data-entity="request">중복</p>'
        with self.assertRaisesRegex(ValueError, "compact/scenes/0/html"):
            self.compile(value)
        value = compact_design()
        value["scenes"][0]["html"] = (
            '<p data-entity="request">{{condition}}{{result}}</p>'
        )
        for item in value["scenes"][0]["states"][0]["values"]:
            item["value"] = ""
        with self.assertRaisesRegex(ValueError, "compact/scenes/0/states/0/html"):
            self.compile(value)

    def test_state_class_patches_reject_unknown_duplicate_and_conflicting_entities(
        self,
    ):
        patches = (
            [{"entity": "missing", "classes": ["is-active"]}],
            [{"entity": "request", "classes": []}] * 2,
            [{"entity": "request", "classes": ["is-active", "is-muted"]}],
            [{"entity": "request", "classes": ["is-success", "is-error"]}],
            [{"entity": "request", "classes": ["is-expanded", "is-collapsed"]}],
            [{"entity": "request", "classes": ["custom-injected"]}],
            [{"entity": "request", "classes": ["is-active", "is-active"]}],
        )
        for patch in patches:
            with self.subTest(patch=patch):
                value = compact_design()
                value["scenes"][0]["states"][0]["entity_classes"] = patch
                with self.assertRaisesRegex(ValueError, "entity_classes"):
                    self.compile(value)

    def test_template_cannot_define_state_classes_that_leak_between_states(self):
        value = compact_design()
        value["scenes"][0]["html"] = value["scenes"][0]["html"].replace(
            "policy-card", "policy-card is-active"
        )
        with self.assertRaisesRegex(ValueError, "put state classes"):
            self.compile(value)

    def test_unknown_heading_or_evidence_and_duplicate_evidence_ids_are_rejected(self):
        value = compact_design()
        value["scenes"][0]["heading_id"] = "does-not-exist"
        with self.assertRaisesRegex(ValueError, "heading_id"):
            self.compile(value)
        for identifiers in (["does-not-exist"], ["source-1-excerpt-1"] * 2):
            value = compact_design()
            value["scenes"][0]["explanation"]["excerpt_ids"] = identifiers
            with self.assertRaisesRegex(ValueError, "excerpt_ids"):
                self.compile(value)

    def test_two_scenes_cannot_select_the_same_heading(self):
        value = compact_design()
        value["scenes"].append(copy.deepcopy(value["scenes"][0]))
        with self.assertRaisesRegex(ValueError, "compact/scenes/1/heading_id"):
            self.compile(value)
        value["scenes"][1]["heading_id"] = "section_2"
        self.assertEqual(
            self.compile(value)["scenes"][1]["after_heading"], "데이터 변환"
        )

    def test_invalid_caller_indexes_fail_before_generation(self):
        for headings in (
            {},
            {"bad/id": "제목"},
            {"h1": ""},
            {"h1": "같음", "h2": "같음"},
        ):
            with (
                self.subTest(headings=headings),
                self.assertRaisesRegex(ValueError, "headings"),
            ):
                build_compact_schema(headings, EXCERPTS)
        for excerpts in (
            [],
            EXCERPTS + [EXCERPTS[0]],
            [{**EXCERPTS[0], "quote": ""}],
            [{**EXCERPTS[0], "quote": "x" * 501}],
            [{**EXCERPTS[0], "source_url": "javascript:alert(1)"}],
        ):
            with (
                self.subTest(excerpts=excerpts),
                self.assertRaisesRegex(ValueError, "excerpts"),
            ):
                build_compact_schema(HEADINGS, excerpts)

    def test_rejects_legacy_state_html_and_extra_fields_in_compact_response(self):
        value = compact_design()
        value["scenes"][0]["states"][0]["html"] = "<p>duplicated template</p>"
        with self.assertRaisesRegex(ValueError, "Additional properties"):
            self.compile(value)

    def test_rejects_oversized_expanded_state(self):
        value = compact_design()
        value["scenes"][0]["html"] += "<p>" + ("{{result}}" * 100) + "</p>"
        value["scenes"][0]["states"][0]["values"][1]["value"] = "x" * 100
        with self.assertRaisesRegex(ValueError, "compiled/scenes/0/states/0/html"):
            self.compile(value)

    def test_invalid_json_and_oversized_raw_response_report_clear_error(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            compile_compact_design("{", HEADINGS, EXCERPTS)
        with self.assertRaisesRegex(ValueError, "exceeds 100000"):
            compile_compact_design(" " * 100001, HEADINGS, EXCERPTS)

    def test_compiling_does_not_bypass_authoritative_graph_validation(self):
        value = compact_design()
        value["scenes"][0]["states"][0]["actions"][0]["target"] = "missing"
        compiled = self.compile(value)
        with self.assertRaises(ValueError):
            validate_design(json.dumps(compiled), COMPACT_BODY)

    def test_optional_effects_compile_and_survive_existing_motion_validation(self):
        value = compact_design()
        value["scenes"][0]["effects"] = [
            {
                "from": "ready",
                "to": target,
                "kind": "compare",
                "entities": ["request"],
                "duration_ms": 1000,
            }
            for target in ("allowed", "denied")
        ]
        compiled = self.compile(value)
        self.assertEqual(
            compiled["scenes"][0]["effects"], value["scenes"][0]["effects"]
        )
        self.assertEqual(validate_design(json.dumps(compiled), COMPACT_BODY), compiled)

    def test_class_only_change_does_not_bypass_effect_text_change_requirement(self):
        value = compact_design()
        scene = value["scenes"][0]
        scene["states"][1]["values"] = copy.deepcopy(scene["states"][0]["values"])
        scene["effects"] = [
            {
                "from": "ready",
                "to": "allowed",
                "kind": "compare",
                "entities": ["request"],
                "duration_ms": 1000,
            }
        ]
        compiled = self.compile(value)
        with self.assertRaises(ValueError):
            validate_design(json.dumps(compiled), COMPACT_BODY)
