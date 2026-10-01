"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from generator.contracts import ModelGatewayError
from generator.design.design_checks import inspect_design, inspect_scene_browsers
from generator.design.design_quality import EvidenceMismatch, validate_explanations
from generator.design.evidence_repair import apply_evidence_repair, build_repair_request
from generator.design.scene_document import validate_design
from generator.design.scene_repair import apply_scene_repair, build_scene_repair_request
from generator.design.visual_contracts import source_sections
from generator.tests.fixtures.design import (
    DESIGN_BODY,
    DESIGN_SOURCES,
    design_candidate,
    scene_patch,
)
from generator.tests.fixtures.runs import (
    break_entities,
    broken_candidate,
    repair_response,
    scene_repair_inputs,
    two_scenes,
)


class EvidenceRepairTest(unittest.TestCase):
    def setUp(self):
        self.design = broken_candidate()
        self.sections = source_sections(DESIGN_SOURCES)
        with self.assertRaises(EvidenceMismatch) as error:
            validate_explanations(self.design, self.sections)
        self.issues = error.exception.issues
        self.request = build_repair_request(self.design, self.sections, self.issues)

    def test_precise_feedback_and_small_request_without_html_css(self):
        self.assertEqual(self.issues[0]["path"], "scenes[0].explanation.evidence[0]")
        serialized = json.dumps(self.request)
        for forbidden in (
            "<div",
            '"css"',
            '"states"',
            '"article"',
            '"previous_candidate"',
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("caption", self.request["scenes"][0])
        self.assertIn("takeaway", self.request["scenes"][0]["explanation"])

    def test_only_failed_quote_changes_and_original_is_immutable(self):
        before = copy.deepcopy(self.design)
        result = apply_evidence_repair(self.design, self.request, repair_response())
        self.assertEqual(self.design, before)
        self.assertEqual(result, design_candidate())
        self.assertTrue(
            validate_explanations(result, self.sections)["semantic_review_required"]
        )

    def test_invalid_missing_duplicate_unrelated_patches_are_rejected(self):
        base = json.loads(repair_response())
        cases = [
            repair_response(None),
            repair_response("invented-id"),
            '{"patches":[]}',
        ]
        for mutation in (
            "extra",
            "duplicate",
            "wrong-target",
            "float-index",
            "bool-index",
        ):
            value = copy.deepcopy(base)
            if mutation == "extra":
                value["css"] = "change design"
            elif mutation == "duplicate":
                value["patches"] *= 2
            elif mutation == "wrong-target":
                value["patches"][0]["scene_index"] = 1
            elif mutation == "float-index":
                value["patches"][0]["scene_index"] = 0.5
            else:
                value["patches"][0]["scene_index"] = True
            cases.append(json.dumps(value))
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(ModelGatewayError):
                apply_evidence_repair(self.design, self.request, raw)

    def test_all_quote_errors_collected_but_structural_errors_take_precedence(self):
        value = broken_candidate()
        value["scenes"][0]["explanation"]["evidence"] *= 3
        with self.assertRaises(EvidenceMismatch) as error:
            validate_explanations(value, self.sections)
        self.assertEqual(len(error.exception.issues), 3)
        value["scenes"][0]["explanation"]["key_entities"] = ["missing"]
        with self.assertRaises(ValueError) as error:
            validate_explanations(value, self.sections)
        self.assertNotIsInstance(error.exception, EvidenceMismatch)

    def test_long_source_excerpts_stay_exact_and_within_contract(self):
        content = "One sentence.\n" + "word " * 600 + "끝" * 600
        request = build_repair_request(
            self.design,
            [{"url": "https://example.com", "content": content}],
            self.issues,
        )
        normalized = " ".join(content.split())
        for excerpt in request["source_excerpts"]:
            self.assertIn(excerpt["quote"], normalized)
            self.assertLessEqual(len(excerpt["quote"]), 500)


class CollectedValidationTest(unittest.TestCase):
    def test_browser_checks_safe_scenes_even_with_placement_and_quote_errors(self):
        value = two_scenes()
        value["scenes"][1]["after_heading"] = value["scenes"][0]["after_heading"]
        value["scenes"][1]["explanation"]["evidence"][0]["quote"] = "없는 인용"
        before = copy.deepcopy(value)
        verifier = mock.Mock()
        verifier.check.side_effect = [
            ValueError("mobile height exceeded"),
            {"ok": True},
        ]
        documents, reports, issues = inspect_scene_browsers(
            value, DESIGN_BODY, verifier
        )
        self.assertEqual(value, before)
        self.assertEqual(verifier.check.call_count, 2)
        self.assertTrue(all(documents))
        self.assertEqual(reports[0]["status"], "failed")
        self.assertEqual(issues[0]["scene_index"], 0)

    def test_unsafe_or_invalid_scenes_never_execute_while_safe_scene_is_checked(self):
        for invalid in ("html", "css", "graph", "schema"):
            with self.subTest(invalid=invalid):
                value = two_scenes()
                if invalid == "html":
                    value["scenes"][0]["states"][0]["html"] = (
                        "<script>alert(1)</script>"
                    )
                elif invalid == "css":
                    value["scenes"][0]["css"] = (
                        ".scene-content {background:url(https://example.com)}"
                    )
                elif invalid == "graph":
                    value["scenes"][0]["states"][0]["actions"][0]["target"] = "missing"
                else:
                    value["scenes"][0] = None
                verifier = mock.Mock()
                documents, reports, issues = inspect_scene_browsers(
                    value, DESIGN_BODY, verifier
                )
                verifier.check.assert_called_once()
                self.assertEqual(verifier.check.call_args.args[0], value["scenes"][1])
                self.assertIsNone(documents[0])
                self.assertEqual(reports[0]["status"], "skipped")
                self.assertEqual(issues, [])

    def test_duplicate_heading_does_not_hide_other_scenes_entity_and_evidence_errors(
        self,
    ):
        value = two_scenes()
        value["scenes"][1]["after_heading"] = value["scenes"][0]["after_heading"]
        break_entities(value, 0)
        break_entities(value, 1)
        value["scenes"][1]["explanation"]["evidence"][0]["quote"] = "만들어낸 인용"
        before = copy.deepcopy(value)
        checked, issues = inspect_design(
            json.dumps(value), DESIGN_BODY, source_sections(DESIGN_SOURCES)
        )
        self.assertEqual(value, before)
        self.assertEqual(checked, before)
        self.assertEqual(sum(item["kind"] == "missing_entities" for item in issues), 4)
        self.assertEqual({item["scene_index"] for item in issues}, {0, 1})
        self.assertIn("placement", {item["kind"] for item in issues})
        self.assertIn("evidence", {item["kind"] for item in issues})

    def test_unsafe_html_css_and_graph_faults_remain_blocking(self):
        value = two_scenes()
        value["scenes"][0]["css"] = (
            ".scene-content {background:url(https://example.com)}"
        )
        value["scenes"][0]["states"][0]["html"] = "<script>alert(1)</script>"
        value["scenes"][1]["states"][0]["actions"][0]["target"] = "missing"
        _, issues = inspect_design(
            json.dumps(value), DESIGN_BODY, source_sections(DESIGN_SOURCES)
        )
        self.assertTrue(
            {"css", "html", "structure"} <= {item["kind"] for item in issues}
        )

    def test_schema_faults_are_collected_without_crashing_other_checks(self):
        for invalid in (None, {}, {"states": None}, {"states": [{"html": 4}]}):
            value = two_scenes()
            value["scenes"][0] = invalid
            break_entities(value, 1)
            with self.subTest(invalid=invalid):
                _, issues = inspect_design(
                    json.dumps(value), DESIGN_BODY, source_sections(DESIGN_SOURCES)
                )
                self.assertTrue(any(item["scene_index"] == 0 for item in issues))
                self.assertTrue(any(item["scene_index"] == 1 for item in issues))


class ScopedPatchTest(unittest.TestCase):
    def setUp(self):
        self.value = two_scenes()
        break_entities(self.value)
        _, self.issues = inspect_design(
            json.dumps(self.value), DESIGN_BODY, source_sections(DESIGN_SOURCES)
        )
        self.request = build_scene_repair_request(
            self.value, self.issues, scene_repair_inputs()
        )

    def test_only_affected_scene_is_sent_and_changed(self):
        self.assertEqual(
            [item["scene_index"] for item in self.request["repair_scenes"]], [0]
        )
        self.assertNotIn("states", self.request["locked_scenes"][0])
        self.assertNotIn("개요", self.request["available_headings"])
        before = copy.deepcopy(self.value)
        repaired = apply_scene_repair(
            self.value, self.request, scene_patch(two_scenes(), [0])
        )
        self.assertEqual(repaired, two_scenes())
        self.assertEqual(repaired["scenes"][1], self.value["scenes"][1])
        self.assertEqual(self.value, before)
        validate_design(json.dumps(repaired), DESIGN_BODY)

    def test_omitted_extra_duplicate_reordered_or_id_deleting_repairs_are_rejected(
        self,
    ):
        patch = json.loads(scene_patch(two_scenes(), [0]))
        cases = [
            {"patches": []},
            json.loads(scene_patch(two_scenes())),
            {"patches": patch["patches"] * 2},
            {**patch, "article": "rewrite"},
            {"patches": [{"scene_index": 0, "scene": None}]},
        ]
        for index in (1, -1, 0.0, True):
            invalid = copy.deepcopy(patch)
            invalid["patches"][0]["scene_index"] = index
            cases.append(invalid)
        invalid = copy.deepcopy(patch)
        invalid["patches"][0]["scene"]["explanation"]["key_entities"] = [
            "different-object"
        ]
        cases.append(invalid)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ModelGatewayError):
                apply_scene_repair(self.value, self.request, json.dumps(case))

    def test_only_official_excerpt_ids_are_accepted(self):
        patch = json.loads(scene_patch(two_scenes(), [0]))
        unknown = copy.deepcopy(patch)
        unknown["patches"][0]["scene"]["explanation"]["evidence"] = [
            {"excerpt_id": "invented"}
        ]
        copied_quote = copy.deepcopy(patch)
        copied_quote["patches"][0]["scene"]["explanation"]["evidence"] = [
            {"source_url": "https://example.com", "quote": "reworded"}
        ]
        for case in (unknown, copied_quote):
            with self.subTest(case=case), self.assertRaises(ModelGatewayError):
                apply_scene_repair(self.value, self.request, json.dumps(case))
