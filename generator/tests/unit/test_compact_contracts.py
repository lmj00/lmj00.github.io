"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import json
import unittest

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from generator.design.compact_repair import (
    apply_compact_field_repair,
    plan_compact_field_repair,
)
from generator.design.compact_scenes import (
    apply_compact_repair,
    build_compact_repair_schema,
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


class CompactFieldRepairTests(unittest.TestCase):
    def plan(self, candidate, path="css"):
        return plan_compact_field_repair(
            candidate,
            ValueError(f"compact/scenes/0/{path}: test error"),
            HEADINGS,
            EXCERPTS,
        )

    def test_css_repair_changes_only_css_preserving_both_scenes_and_summary(self):
        candidate = compact_design()
        candidate["scenes"].append(copy.deepcopy(candidate["scenes"][0]))
        candidate["scenes"][1]["heading_id"] = "section_2"
        before = copy.deepcopy(candidate)
        plan = self.plan(candidate)
        self.assertEqual(plan["targets"], {"scene_index": 0, "fields": ["css"]})
        self.assertNotIn("css", plan["request"]["scene_context"])
        self.assertEqual(set(plan["request"]["current_fields"]), {"css"})
        Draft202012Validator.check_schema(plan["schema"])
        patch = {
            "scene_index": 0,
            "changes": {"css": ".scene-content .policy-card {display:block}"},
        }
        fixed = apply_compact_field_repair(candidate, json.dumps(patch), plan)
        expected = copy.deepcopy(before)
        expected["scenes"][0]["css"] = patch["changes"]["css"]
        self.assertEqual(fixed, expected)
        self.assertEqual(candidate, before)
        self.assertEqual(fixed["scenes"][1], before["scenes"][1])
        compile_compact_design(fixed, HEADINGS, EXCERPTS)

    def test_html_and_binding_failures_repair_template_and_states_together_only(self):
        candidate = compact_design()
        for path in (
            "html",
            "states/0/values",
            "states/1/entity_classes/0",
            "states/0/html",
        ):
            with self.subTest(path=path):
                plan = self.plan(candidate, path)
                self.assertEqual(plan["targets"]["fields"], ["html", "states"])
                self.assertEqual(
                    set(plan["schema"]["properties"]["changes"]["properties"]),
                    {"html", "states"},
                )
                self.assertNotIn("css", plan["request"]["current_fields"])

    def test_actual_compiler_error_is_repaired_with_no_rewrite_of_unaffected_fields(
        self,
    ):
        candidate = compact_design()
        candidate["scenes"][0]["states"][0]["values"].pop()
        try:
            compile_compact_design(candidate, HEADINGS, EXCERPTS)
        except ValueError as error:
            plan = plan_compact_field_repair(candidate, error, HEADINGS, EXCERPTS)
        else:
            self.fail("Expected a compiler error")
        replacement = compact_design()["scenes"][0]
        patch = {
            "scene_index": 0,
            "changes": {"html": replacement["html"], "states": replacement["states"]},
        }
        fixed = apply_compact_field_repair(candidate, patch, plan)
        compile_compact_design(fixed, HEADINGS, EXCERPTS)
        for field in set(candidate["scenes"][0]) - {"html", "states"}:
            self.assertEqual(fixed["scenes"][0][field], candidate["scenes"][0][field])

    def test_state_graph_repair_includes_existing_dependencies_not_new_optional_fields(
        self,
    ):
        candidate = compact_design()
        for field in (
            "states/0/actions/0/target",
            "initial",
            "playback/steps",
            "scenarios/0/steps",
        ):
            with self.subTest(field=field):
                plan = self.plan(candidate, field)
                self.assertEqual(
                    plan["targets"]["fields"],
                    ["states", "initial", "playback", "scenarios"],
                )
                self.assertNotIn("html", plan["targets"]["fields"])
                self.assertNotIn("effects", plan["targets"]["fields"])
                self.assertNotIn("transitions", plan["targets"]["fields"])
        candidate["scenes"][0]["effects"] = []
        candidate["scenes"][0]["transitions"] = []
        self.assertEqual(
            self.plan(candidate, "effects")["targets"]["fields"],
            ["states", "initial", "playback", "effects", "transitions", "scenarios"],
        )

    def test_simple_known_fields_have_exact_single_field_scope(self):
        for field in ("explanation/excerpt_ids", "heading_id", "caption", "title"):
            with self.subTest(field=field):
                plan = self.plan(compact_design(), field)
                self.assertEqual(plan["targets"]["fields"], [field.split("/")[0]])

    def test_unknown_global_or_out_of_range_errors_have_no_repair_plan(self):
        errors = (
            "invalid JSON",
            "compact/: extra fields",
            "compact/scenes/0: missing html",
            "compact/scenes/9/html: invalid",
            "compact/scenes/0/presentation: invalid",
            "compact/scenes/0/unknown: invalid",
            "compiled/scenes/0/states/0/html: too long",
            "some text compact/scenes/0/css: invalid",
        )
        for error in errors:
            with self.subTest(error=error):
                self.assertIsNone(
                    plan_compact_field_repair(
                        compact_design(), error, HEADINGS, EXCERPTS
                    )
                )
        for candidate in (
            None,
            {},
            {"summary": "x", "scenes": []},
            {"summary": "x", "scenes": [None]},
        ):
            with self.subTest(candidate=candidate):
                self.assertIsNone(self.plan(candidate))

    def test_extra_missing_changed_scene_or_additional_top_fields_are_rejected(self):
        candidate = compact_design()
        plan = self.plan(candidate)
        css = candidate["scenes"][0]["css"]
        patches = (
            {"scene_index": 0, "changes": {}},
            {"scene_index": 0, "changes": {"css": css, "html": "<p>Unrelated</p>"}},
            {"scene_index": 1, "changes": {"css": css}},
            {"scene_index": False, "changes": {"css": css}},
            {"scene_index": 0, "changes": {"css": css}, "summary": "unrelated"},
            {"patches": [{"scene_index": 0, "changes": {"css": css}}]},
            {"scene_index": 0, "changes": None},
        )
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                apply_compact_field_repair(candidate, patch, plan)

    def test_html_repair_cannot_omit_states_or_change_css(self):
        candidate = compact_design()
        plan = self.plan(candidate, "html")
        for changes in (
            {"html": "<p>Only HTML</p>"},
            {
                "html": candidate["scenes"][0]["html"],
                "states": candidate["scenes"][0]["states"],
                "css": ".scene-content {display:block}",
            },
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apply_compact_field_repair(
                    candidate, {"scene_index": 0, "changes": changes}, plan
                )

    def test_explanation_repair_cannot_remove_or_replace_locked_core_entities(self):
        candidate = compact_design()
        plan = self.plan(candidate, "explanation/excerpt_ids")
        self.assertEqual(plan["request"]["locked_entities"], ["request"])
        for entities in (["different"], ["request", "another"]):
            explanation = copy.deepcopy(candidate["scenes"][0]["explanation"])
            explanation["key_entities"] = entities
            with (
                self.subTest(entities=entities),
                self.assertRaisesRegex(ValueError, "key_entities are locked"),
            ):
                apply_compact_field_repair(
                    candidate,
                    {"scene_index": 0, "changes": {"explanation": explanation}},
                    plan,
                )
        explanation = copy.deepcopy(candidate["scenes"][0]["explanation"])
        explanation["excerpt_ids"] = ["source-1-excerpt-2"]
        fixed = apply_compact_field_repair(
            candidate, {"scene_index": 0, "changes": {"explanation": explanation}}, plan
        )
        self.assertEqual(fixed["scenes"][0]["explanation"]["key_entities"], ["request"])

    def test_dynamic_schema_rejects_unknown_heading_and_excerpt_ids(self):
        candidate = compact_design()
        plan = self.plan(candidate, "heading_id")
        with self.assertRaises(ValueError):
            apply_compact_field_repair(
                candidate,
                {"scene_index": 0, "changes": {"heading_id": "unknown"}},
                plan,
            )
        plan = self.plan(candidate, "explanation")
        explanation = copy.deepcopy(candidate["scenes"][0]["explanation"])
        explanation["excerpt_ids"] = ["unknown"]
        with self.assertRaises(ValueError):
            apply_compact_field_repair(
                candidate,
                {"scene_index": 0, "changes": {"explanation": explanation}},
                plan,
            )

    def test_duplicate_json_fields_and_oversized_invalid_patch_are_rejected(self):
        candidate = compact_design()
        plan = self.plan(candidate)
        for raw in (
            '{"scene_index":0,"changes":{"css":"x","css":"y"}}',
            "{",
            " " * 100001,
        ):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                apply_compact_field_repair(candidate, raw, plan)

    def test_plans_and_applied_results_do_not_alias_candidate_or_patch(self):
        candidate = compact_design()
        before = copy.deepcopy(candidate)
        plan = self.plan(candidate)
        plan["request"]["scene_context"]["explanation"]["takeaway"] = (
            "Request copy only"
        )
        self.assertEqual(candidate, before)
        patch = {"scene_index": 0, "changes": {"css": candidate["scenes"][0]["css"]}}
        patch_before = copy.deepcopy(patch)
        fixed = apply_compact_field_repair(candidate, patch, plan)
        fixed["scenes"][0]["explanation"]["takeaway"] = "Returned copy only"
        self.assertEqual(candidate, before)
        self.assertEqual(patch, patch_before)


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


class CompactRepairTests(unittest.TestCase):
    def test_patch_schema_reuses_compact_scene_with_resolved_id_enums(self):
        schema = build_compact_repair_schema(HEADINGS, EXCERPTS)
        Draft202012Validator.check_schema(schema)
        patch = {
            "patches": [{"scene_index": 0, "scene": compact_design()["scenes"][0]}]
        }
        self.assertTrue(Draft202012Validator(schema).is_valid(patch))

    def test_saved_presentation_requires_explicit_repair_schema_compatibility(self):
        value = compact_design()["scenes"][0]
        value["presentation"] = {
            "layout": "flow",
            "eyebrow": "기존",
            "links": [{"source": "request", "target": "result", "label": "결과"}],
        }
        patch = {"patches": [{"scene_index": 0, "scene": value}]}
        self.assertFalse(
            Draft202012Validator(
                build_compact_repair_schema(HEADINGS, EXCERPTS)
            ).is_valid(patch)
        )
        schema = build_compact_repair_schema(
            HEADINGS, EXCERPTS, allow_presentation=True
        )
        self.assertTrue(Draft202012Validator(schema).is_valid(patch))
        patch["patches"][0]["scene"] = None
        self.assertTrue(Draft202012Validator(schema).is_valid(patch))

    def test_scoped_patch_preserves_summary_order_and_untouched_scenes(self):
        original = compact_design()
        original["scenes"].append(copy.deepcopy(original["scenes"][0]))
        original["scenes"][1]["heading_id"] = "section_2"
        patch_scene = copy.deepcopy(original["scenes"][0])
        patch_scene["caption"] = "수정한 설명"
        patch = {"patches": [{"scene_index": 0, "scene": patch_scene}]}
        before = copy.deepcopy((original, patch))
        repaired = apply_compact_repair(original, json.dumps(patch), {0})
        self.assertEqual((original, patch), before)
        self.assertEqual(repaired["summary"], original["summary"])
        self.assertEqual(repaired["scenes"][1], original["scenes"][1])
        self.assertEqual(repaired["scenes"][0]["caption"], "수정한 설명")
        compile_compact_design(repaired, HEADINGS, EXCERPTS)
        repaired["scenes"][1]["title"] = "only the returned copy changes"
        self.assertEqual(original, before[0])

    def test_missing_extra_duplicate_null_and_out_of_scope_patches_are_rejected(self):
        scene = compact_design()["scenes"][0]
        patches = (
            {"patches": []},
            {"patches": [{"scene_index": 1, "scene": scene}]},
            {"patches": [{"scene_index": True, "scene": scene}]},
            {"patches": [{"scene_index": 0, "scene": None}]},
            {"patches": [{"scene_index": 0, "scene": scene, "extra": True}]},
            {"patches": [{"scene_index": 0, "scene": scene}] * 2},
            {
                "patches": [{"scene_index": 0, "scene": scene}],
                "summary": "do not change",
            },
        )
        for patch in patches:
            with (
                self.subTest(patch=patch),
                self.assertRaisesRegex(ValueError, "compact_repair"),
            ):
                apply_compact_repair(compact_design(), patch, {0})
        for indices in ([], [0, 0], [True], [1], None):
            with (
                self.subTest(indices=indices),
                self.assertRaisesRegex(ValueError, "compact_repair"),
            ):
                apply_compact_repair(compact_design(), {"patches": []}, indices)

    def test_core_entity_ids_cannot_be_deleted_or_changed_to_escape_checks(self):
        original = compact_design()
        scene = copy.deepcopy(original["scenes"][0])
        scene["explanation"]["key_entities"] = ["different"]
        with self.assertRaisesRegex(ValueError, "key_entities are locked"):
            apply_compact_repair(
                original, {"patches": [{"scene_index": 0, "scene": scene}]}, {0}
            )

    def test_schema_and_compiler_still_reject_invalid_replacement_details(self):
        original = compact_design()
        scene = copy.deepcopy(original["scenes"][0])
        scene["heading_id"] = "unknown-heading"
        patch = {"patches": [{"scene_index": 0, "scene": scene}]}
        self.assertFalse(
            Draft202012Validator(
                build_compact_repair_schema(HEADINGS, EXCERPTS)
            ).is_valid(patch)
        )
        repaired = apply_compact_repair(original, patch, {0})
        with self.assertRaisesRegex(ValueError, "heading_id"):
            compile_compact_design(repaired, HEADINGS, EXCERPTS)
