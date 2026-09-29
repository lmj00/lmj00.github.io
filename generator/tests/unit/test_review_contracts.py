"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from jsonschema import Draft202012Validator, ValidationError

from generator.contracts import GeneratedText, ModelGatewayError
from generator.design.design_inputs import (
    compact_input,
    reference_review_schema,
    resolve_review,
    review_choices,
)
from generator.design.design_review import complete_validated_review
from generator.design.reader_review import (
    build_reader_evidence,
    reader_review_schema,
    validate_reader_checks,
)
from generator.design.visual_contracts import (
    REVIEW_SCHEMA,
    ReviewContractError,
    validate_review,
)
from generator.tests.fixtures.content import design_review_report, reader_report
from generator.tests.fixtures.design import clear_design


class DesignInputTest(unittest.TestCase):
    def test_sources_are_not_duplicated_in_wire_context(self):
        request = dict(
            article_title="글",
            article="본문",
            tags=[],
            headings=["핵심"],
            sources="XML",
            current_official_sections=[
                {"url": "https://example.com", "content": "Exact source."}
            ],
            recent_designs=[],
            interaction_required=True,
        )
        wire = compact_input(request)
        self.assertNotIn("sources", wire)
        self.assertNotIn("current_official_sections", wire)
        self.assertEqual(wire["headings"], {"section_1": "핵심"})
        self.assertEqual(wire["source_excerpts"][0]["quote"], "Exact source.")
        self.assertEqual(request["sources"], "XML")

    def test_review_paths_and_quotes_are_resolved_not_generated(self):
        candidate = {"scenes": [{"caption": "설명"}]}
        choices = review_choices(
            candidate, [{"url": "https://example.com", "content": "Exact source."}]
        )
        target = next(
            item for item in choices["review_targets"] if item["target"] == "content"
        )
        report = {
            "verdict": "revise",
            "previous_issues": [],
            "issues": [
                {
                    "id": "I1",
                    "target_ref": target["target_ref"],
                    "evidence_ref": "source-1-excerpt-1",
                    "kind": "factual",
                    "problem": "문제",
                    "suggestion": "수정",
                }
            ],
        }
        actual = resolve_review(json.dumps(report), choices)
        self.assertEqual(actual["issues"][0]["path"], "/candidate/scenes/0/caption")
        self.assertEqual(actual["issues"][0]["source_quote"], "Exact source.")
        self.assertEqual(candidate["scenes"][0]["caption"], "설명")
        report["issues"][0]["kind"] = "visual"
        with self.assertRaises(ValueError):
            resolve_review(json.dumps(report), choices)

    def test_target_ids_are_stable_across_text_changes(self):
        before = review_choices({"caption": "전"}, [])
        after = review_choices({"caption": "후"}, [])
        self.assertEqual(before["review_targets"], after["review_targets"])


class ValidatedReviewTest(unittest.TestCase):
    def setUp(self):
        self.models = mock.Mock()
        self.request = {
            "candidate": {"scenes": [{"caption": "설명"}]},
            "article": "검수된 본문은 그대로 유지한다.",
            "current_official_sections": [
                {"url": "https://example.test", "content": "Source evidence."}
            ],
        }
        self.before = copy.deepcopy(self.request)

    def validate(self, raw):
        return validate_review(
            raw, candidate=self.request["candidate"], inputs=self.request
        )

    def call(self, **kwargs):
        return complete_validated_review(
            self.models,
            "original review prompt",
            self.request,
            ["review-primary", "review-fallback"],
            schema=kwargs.pop("schema", REVIEW_SCHEMA),
            validate=kwargs.pop("validate", self.validate),
            **kwargs,
        )

    def test_invalid_path_is_repaired_once_on_actual_same_reviewer(self):
        invalid = json.dumps(design_review_report(path="/candidate/scenes/0/missing"))
        valid = json.dumps(design_review_report())
        self.models.complete_json.side_effect = [
            GeneratedText(invalid, "review-fallback"),
            GeneratedText(valid, "review-fallback"),
        ]
        responses = []
        generated, actual = self.call(
            on_response=lambda value, index: responses.append((value.content, index))
        )
        self.assertEqual(generated.model, "review-fallback")
        self.assertEqual(actual["verdict"], "revise")
        self.assertEqual(responses, [(invalid, 1), (valid, 2)])
        first, repair = self.models.complete_json.call_args_list
        self.assertEqual(first.args[2], ["review-primary", "review-fallback"])
        self.assertEqual(repair.args[2], ["review-fallback"])
        self.assertEqual(first.kwargs["format_retries"], 1)
        self.assertEqual(repair.kwargs["format_retries"], 0)
        self.assertEqual(
            first.kwargs["response_schema"], repair.kwargs["response_schema"]
        )
        self.assertIn("UNTRUSTED DATA", repair.args[0])
        repair_request = json.loads(repair.args[1])
        self.assertEqual(repair_request["candidate"], self.request["candidate"])
        self.assertEqual(repair_request["article"], self.request["article"])
        self.assertEqual(
            repair_request["report_format_error"]["invalid_report"], invalid
        )
        self.assertIn(
            "missing field", repair_request["report_format_error"]["diagnostic"]
        )
        self.assertEqual(self.request, self.before)

    def test_missing_factual_reference_repairs_report_not_candidate(self):
        choices = review_choices(
            self.request["candidate"], self.request["current_official_sections"]
        )
        target = next(
            item for item in choices["review_targets"] if item["target"] == "content"
        )
        invalid = {
            "verdict": "revise",
            "previous_issues": [],
            "issues": [
                {
                    "id": "I1",
                    "target_ref": target["target_ref"],
                    "evidence_ref": None,
                    "kind": "factual",
                    "problem": "사실 오류",
                    "suggestion": "근거에 따라 수정",
                }
            ],
        }
        valid = copy.deepcopy(invalid)
        valid["issues"][0]["evidence_ref"] = choices["source_excerpts"][0]["excerpt_id"]
        self.models.complete_json.side_effect = [
            GeneratedText(json.dumps(invalid), "review-primary"),
            GeneratedText(json.dumps(valid), "review-primary"),
        ]

        def canonical(raw):
            return self.validate(json.dumps(resolve_review(raw, choices)))

        _, actual = self.call(
            schema=reference_review_schema(choices), validate=canonical
        )
        self.assertEqual(actual["issues"][0]["source_quote"], "Source evidence.")
        self.assertEqual(self.models.complete_json.call_count, 2)
        self.assertEqual(self.request, self.before)

    def test_valid_semantic_revise_is_returned_without_format_retry(self):
        self.models.complete_json.return_value = GeneratedText(
            json.dumps(design_review_report()), "review-primary"
        )
        _, actual = self.call()
        self.assertEqual(actual["verdict"], "revise")
        self.models.complete_json.assert_called_once()

    def test_native_format_retry_and_reference_retry_share_one_budget(self):
        attempts = []

        def native(*args, **kwargs):
            kwargs["on_attempt"]({"format_retry": False, "status": "format_error"})
            kwargs["on_attempt"]({"format_retry": True, "status": "valid"})
            return GeneratedText(
                json.dumps(design_review_report(path="/candidate/missing")),
                "review-primary",
            )

        self.models.complete_json.side_effect = native
        with self.assertRaisesRegex(ReviewContractError, "한도 소진"):
            self.call(on_attempt=attempts.append)
        self.models.complete_json.assert_called_once()
        self.assertEqual(len(attempts), 2)

    def test_second_invalid_report_stops_without_any_designer_or_third_review_call(
        self,
    ):
        invalid = GeneratedText(
            json.dumps(design_review_report(path="/candidate/missing")),
            "review-primary",
        )
        self.models.complete_json.side_effect = [invalid, invalid]
        with self.assertRaises(ReviewContractError):
            self.call()
        self.assertEqual(self.models.complete_json.call_count, 2)
        for call in self.models.complete_json.call_args_list:
            self.assertEqual(call.kwargs["purpose"], "디자인 근거 검수")

    def test_transport_failure_propagates_without_contract_retry(self):
        self.models.complete_json.side_effect = ModelGatewayError(
            "provider unavailable"
        )
        with self.assertRaisesRegex(ModelGatewayError, "provider unavailable"):
            self.call()
        self.models.complete_json.assert_called_once()

    def test_unexpected_validator_bug_is_not_retried(self):
        self.models.complete_json.return_value = GeneratedText("{}", "review-primary")
        with self.assertRaises(KeyError):
            self.call(validate=mock.Mock(side_effect=KeyError("implementation bug")))
        self.models.complete_json.assert_called_once()

    def test_diagnostic_and_invalid_report_are_bounded(self):
        self.models.complete_json.side_effect = [
            GeneratedText("x" * 30000, "review-primary"),
            GeneratedText("{}", "review-primary"),
        ]
        validator = mock.Mock(
            side_effect=[ValidationError("error" * 1000), {"verdict": "pass"}]
        )
        _, actual = self.call(validate=validator)
        self.assertEqual(actual["verdict"], "pass")
        data = json.loads(self.models.complete_json.call_args_list[1].args[1])[
            "report_format_error"
        ]
        self.assertEqual(len(data["invalid_report"]), 24000)
        self.assertEqual(data["invalid_report_chars"], 30000)
        self.assertTrue(data["invalid_report_truncated"])
        self.assertLessEqual(len(data["diagnostic"]), 2000)

    def test_progress_and_response_callbacks_are_forwarded(self):
        progress = mock.Mock()
        response = mock.Mock()
        self.models.complete_json.return_value = GeneratedText(
            json.dumps(design_review_report(verdict="pass")), "review-primary"
        )
        self.call(on_progress=progress, on_response=response)
        self.assertIs(
            self.models.complete_json.call_args.kwargs["on_progress"], progress
        )
        response.assert_called_once_with(self.models.complete_json.return_value, 1)


class ReaderReviewTests(unittest.TestCase):
    def setUp(self):
        self.design = clear_design()
        self.evidence = build_reader_evidence(self.design)

    def test_evidence_indexes_actual_actions_text_and_declared_ledger_reason(self):
        self.assertEqual(len(self.evidence), 2)
        edge = self.evidence[0]
        self.assertEqual((edge["from"], edge["to"]), ("ready", "allowed"))
        self.assertEqual(edge["action_labels"], ["조건 충족"])
        self.assertEqual(
            {item["category"] for item in edge["visible_values"]},
            {"before", "after", "invariant", "reason"},
        )
        for item in edge["visible_values"]:
            if item["category"] == "reason":
                self.assertEqual(item["origin"], "trusted_change_ledger")
                self.assertIsNone(item["entity"])
            else:
                self.assertEqual(item["origin"], "entity_dom_text")
                self.assertIn(item["entity"], ("request", "original"))
        self.assertIn("not factual evidence", edge["scope"])

    def test_references_are_stable_and_change_when_value_changes(self):
        before = copy.deepcopy(self.design)
        self.assertEqual(build_reader_evidence(self.design), self.evidence)
        self.assertEqual(self.design, before)
        scene = self.design["scenes"][0]
        scene["change_explanations"][0]["changes"][0]["after"] = "labels: {team: prod}"
        scene["states"][1]["html"] = scene["states"][1]["html"].replace(
            "labels: {team: demo}", "labels: {team: prod}"
        )
        changed = build_reader_evidence(self.design)[0]
        self.assertEqual(changed["edge_ref"], self.evidence[0]["edge_ref"])
        old_after = next(
            item
            for item in self.evidence[0]["visible_values"]
            if item["category"] == "after"
        )
        new_after = next(
            item for item in changed["visible_values"] if item["category"] == "after"
        )
        self.assertNotEqual(old_after["visible_ref"], new_after["visible_ref"])

    def test_unverified_claims_do_not_become_actual_visible_evidence(self):
        scene = self.design["scenes"][0]
        scene["change_explanations"][0]["changes"][0]["after"] = "INVENTED VALUE"
        scene["change_explanations"][0]["invariants"][0]["value"] = "INVENTED INVARIANT"
        edge = build_reader_evidence(self.design)[0]
        self.assertEqual(
            [item["category"] for item in edge["visible_values"]], ["reason"]
        )
        self.assertNotIn("INVENTED", json.dumps(edge))

    def test_schema_is_strict_valid_and_does_not_mutate_legacy_base_or_evidence(self):
        before = copy.deepcopy((REVIEW_SCHEMA, self.evidence))
        schema = reader_review_schema(REVIEW_SCHEMA, self.evidence)
        Draft202012Validator.check_schema(schema)
        self.assertTrue(
            Draft202012Validator(schema).is_valid(reader_report(self.evidence))
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(
            schema["properties"]["reader_checks"]["items"]["additionalProperties"]
        )
        self.assertIn("reader_checks", schema["required"])
        self.assertEqual((REVIEW_SCHEMA, self.evidence), before)
        schema["properties"]["issues"]["maxItems"] = 999
        self.assertNotEqual(REVIEW_SCHEMA["properties"]["issues"]["maxItems"], 999)

    def test_reference_based_review_schema_remains_reference_based(self):
        choices = review_choices(
            self.design,
            [{"url": "https://example.test", "content": "An official source."}],
        )
        base = reference_review_schema(choices)
        schema = reader_review_schema(base, self.evidence)
        issue_fields = schema["properties"]["issues"]["items"]["properties"]
        self.assertIn("target_ref", issue_fields)
        self.assertNotIn("target", issue_fields)
        self.assertNotIn("reader_checks", base["properties"])
        Draft202012Validator.check_schema(schema)

    def test_valid_pass_strips_only_reader_checks_and_preserves_inputs(self):
        report = reader_report(self.evidence)
        before = copy.deepcopy((report, self.evidence))
        canonical, checks = validate_reader_checks(report, self.evidence)
        self.assertEqual(
            canonical,
            {key: value for key, value in report.items() if key != "reader_checks"},
        )
        self.assertEqual(checks, report["reader_checks"])
        self.assertEqual((report, self.evidence), before)
        checks[0]["change_answer"] = "returned copy"
        self.assertNotEqual(
            report["reader_checks"][0]["change_answer"], "returned copy"
        )

    def test_raw_json_is_supported(self):
        canonical, checks = validate_reader_checks(
            json.dumps(reader_report(self.evidence)), self.evidence
        )
        self.assertEqual(canonical["verdict"], "pass")
        self.assertEqual(len(checks), 2)

    def test_pass_missing_edge_or_required_category_is_rejected(self):
        for mutation in ("edge", "before", "after", "invariant", "reason"):
            with self.subTest(mutation=mutation):
                report = reader_report(self.evidence)
                if mutation == "edge":
                    report["reader_checks"].pop()
                else:
                    excluded = {
                        item["visible_ref"]
                        for item in self.evidence[0]["visible_values"]
                        if item["category"] == mutation
                    }
                    refs = report["reader_checks"][0]["visible_refs"]
                    report["reader_checks"][0]["visible_refs"] = [
                        ref for ref in refs if ref not in excluded
                    ]
                with self.assertRaises(ValueError):
                    validate_reader_checks(report, self.evidence)

    def test_unknown_or_other_edge_reference_is_never_accepted(self):
        for verdict in ("pass", "revise"):
            for ref in (
                "visible_unknown",
                self.evidence[1]["visible_values"][0]["visible_ref"],
            ):
                with self.subTest(verdict=verdict, ref=ref):
                    report = reader_report(self.evidence, verdict)
                    report["issues"] = [
                        {
                            "problem": "Existing canonical validator checks issue details."
                        }
                    ]
                    report["reader_checks"][0]["visible_refs"][0] = ref
                    with self.assertRaises((ValueError, ValidationError)):
                        validate_reader_checks(report, self.evidence)

    def test_duplicate_or_unknown_edges_are_rejected_even_for_revise(self):
        for verdict in ("pass", "revise"):
            for replacement in (self.evidence[0]["edge_ref"], "edge_unknown"):
                report = reader_report(self.evidence, verdict)
                report["issues"] = [{"problem": "Unclear."}]
                report["reader_checks"][1]["edge_ref"] = replacement
                with self.assertRaises((ValueError, ValidationError)):
                    validate_reader_checks(report, self.evidence)

    def test_revise_may_omit_unanswerable_edges_or_references_with_actual_issue(self):
        for checks in ([], reader_report(self.evidence)["reader_checks"][:1]):
            report = reader_report(self.evidence, "revise")
            report["issues"] = [{"problem": "Cannot see which value changed."}]
            report["reader_checks"] = checks
            for check in checks:
                check.update(
                    change_answer="화면에서 변경 값을 확인할 수 없다.", visible_refs=[]
                )
            canonical, actual = validate_reader_checks(report, self.evidence)
            self.assertEqual(canonical["verdict"], "revise")
            self.assertEqual(actual, checks)

    def test_revise_without_issue_and_pass_without_checks_are_rejected(self):
        report = reader_report(self.evidence, "revise")
        with self.assertRaises(ValueError):
            validate_reader_checks(report, self.evidence)
        del report["reader_checks"]
        with self.assertRaises(ValueError):
            validate_reader_checks(report, self.evidence)

    def test_answers_are_nonempty_bounded_but_summary_wording_is_not_exact_copy_checked(
        self,
    ):
        for value in ("", "   \n", "x" * 501):
            report = reader_report(self.evidence)
            report["reader_checks"][0]["reason_answer"] = value
            with self.assertRaises(ValidationError):
                validate_reader_checks(report, self.evidence)
        report = reader_report(self.evidence)
        report["reader_checks"][0]["reason_answer"] = (
            "요청에 적용된 예시 규칙 때문이다."
        )
        validate_reader_checks(report, self.evidence)

    def test_duplicate_refs_or_additional_answer_fields_are_rejected(self):
        for mutation in ("duplicate", "extra"):
            report = reader_report(self.evidence)
            check = report["reader_checks"][0]
            if mutation == "duplicate":
                check["visible_refs"].append(check["visible_refs"][0])
            else:
                check["claimed_quality_score"] = 100
            with self.assertRaises(ValidationError):
                validate_reader_checks(report, self.evidence)

    def test_empty_evidence_schema_is_valid_and_requires_an_empty_answer_list(self):
        schema = reader_review_schema(REVIEW_SCHEMA, [])
        Draft202012Validator.check_schema(schema)
        report = reader_report([])
        self.assertTrue(Draft202012Validator(schema).is_valid(report))
        self.assertEqual(validate_reader_checks(report, [])[1], [])

    def test_legacy_missing_claims_cannot_earn_pass_by_inventing_visible_refs(self):
        for scene in self.design["scenes"]:
            del scene["change_explanations"], scene["interaction_mode"]
        evidence = build_reader_evidence(self.design)
        self.assertTrue(evidence)
        self.assertTrue(all(not edge["visible_values"] for edge in evidence))
        with self.assertRaises(ValueError):
            validate_reader_checks(reader_report(evidence), evidence)
