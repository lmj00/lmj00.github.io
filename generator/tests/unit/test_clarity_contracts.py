"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import unittest

from jsonschema import Draft202012Validator

from generator.design.compact_scenes import (
    build_compact_schema,
    compile_compact_design,
)
from generator.design.scene_clarity import clarity_observations, collect_clarity_issues
from generator.design.scene_document import clean_html
from generator.design.visual_contracts import DESIGN_SCHEMA
from generator.tests.fixtures.design import (
    EXCERPTS,
    HEADINGS,
    clear_compact_design,
    clear_design,
    compact_design,
)


class ExplanationQualityTest(unittest.TestCase):
    def test_entity_attribute_is_not_arbitrary_data_or_code(self):
        for fragment in (
            '<p data-other="x">x</p>',
            '<p data-entity="javascript:x">x</p>',
            '<p data-entity="a">x</p><p data-entity="a">y</p>',
            '<p data-entity="a"></p>',
            '<p data-entity="a" onclick="x()">x</p>',
        ):
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                clean_html(fragment)


class SceneClarityTests(unittest.TestCase):
    def test_schema_is_opt_in_and_static_scene_does_not_need_clarity_fields(self):
        before = copy.deepcopy(DESIGN_SCHEMA)
        schema = build_compact_schema(HEADINGS, EXCERPTS, require_clarity=True)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.assertTrue(validator.is_valid(clear_compact_design()))
        self.assertFalse(validator.is_valid(compact_design()))
        static = compact_design()
        static["scenes"][0]["explanation"]["mode"] = "static"
        self.assertTrue(validator.is_valid(static))
        self.assertTrue(
            Draft202012Validator(build_compact_schema(HEADINGS, EXCERPTS)).is_valid(
                compact_design()
            )
        )
        self.assertEqual(DESIGN_SCHEMA, before)

    def test_compile_preserves_new_fields_without_mutating_or_synthesizing(self):
        compact = clear_compact_design()
        before = copy.deepcopy(compact)
        compiled = compile_compact_design(compact, HEADINGS, EXCERPTS)
        self.assertEqual(compact, before)
        for field in ("interaction_mode", "change_explanations"):
            self.assertEqual(compiled["scenes"][0][field], compact["scenes"][0][field])
        legacy = compile_compact_design(compact_design(), HEADINGS, EXCERPTS)
        self.assertNotIn("interaction_mode", legacy["scenes"][0])
        self.assertNotIn("change_explanations", legacy["scenes"][0])

    def test_valid_actual_changes_and_fixed_context_pass(self):
        design = clear_design()
        before = copy.deepcopy(design)
        self.assertEqual(collect_clarity_issues(design, required=True), [])
        self.assertEqual(design, before)

    def test_legacy_fields_are_optional_but_missing_required_fields_are_issues(self):
        legacy = compile_compact_design(compact_design(), HEADINGS, EXCERPTS)
        self.assertEqual(collect_clarity_issues(legacy), [])
        issues = collect_clarity_issues(legacy, required=True)
        self.assertEqual(len(issues), 2)
        self.assertTrue(
            all(
                item["kind"] == "clarity" and item["scene_index"] == 0
                for item in issues
            )
        )
        legacy["scenes"][0]["explanation"]["mode"] = "static"
        self.assertEqual(collect_clarity_issues(legacy, required=True), [])

    def test_present_partial_fields_cannot_bypass_legacy_validation(self):
        for field in ("interaction_mode", "change_explanations"):
            design = clear_design()
            del design["scenes"][0][field]
            self.assertTrue(collect_clarity_issues(design))

    def test_false_before_after_missing_entities_and_unchanged_claims_are_rejected(
        self,
    ):
        replacements = (
            {"before": "labels: {invented: data}"},
            {"after": "labels: {invented: data}"},
            {"entity": "unknown"},
            {"before": "처리 결과", "after": "처리 결과"},
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                design = clear_design()
                design["scenes"][0]["change_explanations"][0]["changes"][0].update(
                    replacement
                )
                issues = collect_clarity_issues(design)
                self.assertTrue(any("changes[0]" in item["path"] for item in issues))

    def test_both_claimed_values_already_present_in_both_states_are_not_a_change(self):
        design = clear_design()
        for state in design["scenes"][0]["states"]:
            state["html"] = state["html"].replace(
                "<h4>처리 결과</h4>", "<h4>처리 결과: old new</h4>"
            )
        design["scenes"][0]["change_explanations"][0]["changes"][0].update(
            before="old", after="new"
        )
        self.assertTrue(collect_clarity_issues(design))

    def test_substring_overlap_for_real_numeric_changes_is_not_false_rejection(self):
        design = clear_design()
        scene = design["scenes"][0]
        scene["states"][0]["html"] = scene["states"][0]["html"].replace(
            "labels: {}", "1"
        )
        scene["states"][1]["html"] = scene["states"][1]["html"].replace(
            "labels: {team: demo}", "10"
        )
        scene["change_explanations"][0]["changes"][0].update(before="1", after="10")
        self.assertEqual(collect_clarity_issues(design), [])

    def test_whitespace_is_normalized_but_content_is_not_rewritten(self):
        design = clear_design()
        scene = design["scenes"][0]
        scene["change_explanations"][0]["changes"][0]["before"] = "labels:\n  {}"
        self.assertEqual(collect_clarity_issues(design), [])
        scene["change_explanations"][0]["changes"][0]["before"] = "Labels: {}"
        self.assertTrue(collect_clarity_issues(design))

    def test_invariant_must_be_present_in_both_actual_states(self):
        for mutation in ("invented", "app: different"):
            design = clear_design()
            design["scenes"][0]["change_explanations"][0]["invariants"][0]["value"] = (
                mutation
            )
            self.assertTrue(collect_clarity_issues(design))

    def test_changed_entity_must_match_effect_target_but_transfer_has_no_false_lock(
        self,
    ):
        design = clear_design()
        design["scenes"][0]["effects"][0]["entities"] = ["original"]
        self.assertTrue(
            any(
                "effects.entities" in issue["message"]
                for issue in collect_clarity_issues(design)
            )
        )
        del design["scenes"][0]["effects"]
        self.assertEqual(collect_clarity_issues(design), [])

    def test_missing_duplicate_unknown_self_and_non_action_edges_are_rejected(self):
        mutations = (
            lambda items: items.pop(),
            lambda items: items.append(copy.deepcopy(items[0])),
            lambda items: items[0].update(to="missing"),
            lambda items: items[0].update(to="ready"),
            lambda items: items[0].update(**{"from": "allowed", "to": "denied"}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                design = clear_design()
                mutation(design["scenes"][0]["change_explanations"])
                self.assertTrue(collect_clarity_issues(design))

    def test_self_buttons_do_not_need_change_claims(self):
        design = clear_design()
        design["scenes"][0]["states"][0]["actions"].append(
            {"label": "그대로", "target": "ready"}
        )
        self.assertEqual(collect_clarity_issues(design), [])

    def test_duplicate_change_or_invariant_labels_are_rejected(self):
        for field in ("changes", "invariants"):
            design = clear_design()
            items = design["scenes"][0]["change_explanations"][0][field]
            items.append(copy.deepcopy(items[0]))
            self.assertTrue(collect_clarity_issues(design))

    def test_hidden_or_duplicated_entity_text_is_not_verified(self):
        for prefix in (
            '<div hidden data-entity="request">',
            '<div data-entity="request">duplicate</div><div data-entity="request">',
        ):
            design = clear_design()
            scene = design["scenes"][0]
            scene["states"][0]["html"] = scene["states"][0]["html"].replace(
                '<div data-entity="request">', prefix
            )
            self.assertTrue(collect_clarity_issues(design))

    def test_plain_text_limits_and_empty_or_html_reasons_are_enforced(self):
        for field, value in (
            ("reason", "   "),
            ("reason", "<b>Why</b>"),
            ("reason", "x" * 241),
        ):
            design = clear_design()
            design["scenes"][0]["change_explanations"][0][field] = value
            self.assertTrue(collect_clarity_issues(design))
        design = clear_design()
        design["scenes"][0]["change_explanations"][0]["reason"] = (
            "설명용 정책은 값이 < 3이면 허용한다."
        )
        self.assertEqual(collect_clarity_issues(design), [])
        for field in ("before", "after", "label"):
            design = clear_design()
            design["scenes"][0]["change_explanations"][0]["changes"][0][field] = (
                "x" * 121
            )
            self.assertTrue(collect_clarity_issues(design))

    def test_observations_use_actual_text_and_do_not_call_reasons_verified(self):
        design = clear_design()
        observed = clarity_observations(design)[0]
        edge = observed["action_observations"][0]
        self.assertEqual(edge["action_labels"], ["조건 충족"])
        self.assertEqual(
            edge["text_verified_changes"],
            design["scenes"][0]["change_explanations"][0]["changes"],
        )
        self.assertIn("declared_reason", edge)
        self.assertNotIn("verified_reason", edge)
        request = next(
            item for item in edge["entity_dom_text"] if item["entity"] == "request"
        )
        self.assertIn("labels: {}", request["before"])
        self.assertIn("labels: {team: demo}", request["after"])
        edge["text_verified_changes"][0]["after"] = "copy only"
        self.assertNotEqual(
            design["scenes"][0]["change_explanations"][0]["changes"][0]["after"],
            "copy only",
        )

    def test_invalid_claim_is_not_exported_as_text_verified(self):
        design = clear_design()
        design["scenes"][0]["change_explanations"][0]["changes"][0]["after"] = (
            "invented"
        )
        observed = clarity_observations(design)[0]
        self.assertEqual(
            observed["action_observations"][0]["text_verified_changes"], []
        )
        self.assertTrue(observed["issues"])
