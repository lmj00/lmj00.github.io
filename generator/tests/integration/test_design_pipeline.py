"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import copy
import html
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from generator.contracts import Article, GeneratedText, ModelGatewayError
from generator.design.design_browser import BrowserSceneVerifier, BrowserUnavailable
from generator.design.design_pipeline import ArticleDesignPipeline
from generator.design.design_resume import load_saved_design
from generator.design.prompt_examples import examples
from generator.main import load_prompt
from generator.tests.fixtures.design import (
    DESIGN_BODY,
    DesignHarness,
    design_article,
    design_candidate,
    design_review,
    scene_patch,
)
from generator.tests.fixtures.runs import interactive_candidate


class ClarityPipelineTest(unittest.TestCase):
    def setUp(self):
        example = examples()[0]
        self.candidate = copy.deepcopy(example["output"])
        self.candidate["scenes"][0]["heading_id"] = "section_1"
        self.candidate["scenes"][0]["explanation"]["excerpt_ids"] = [
            "source-1-excerpt-1"
        ]
        excerpt = example["input"]["source_excerpts"][0]
        self.sources = (
            f"<document><source_url>{excerpt['source_url']}</source_url>"
            f"<document_content>{html.escape(excerpt['quote'])}</document_content></document>"
        )
        self.article = Article(
            "독자 검수 예시", "### 가상 조건\n\n설명", "writer", (), ()
        )
        self.cfg = dict(
            design_enabled=True,
            design_required=True,
            design_interaction_required=True,
            design_clarity_required=True,
            design_generation_format="compact",
            design_model_fallback=["writer"],
            design_review_model_fallback=["reviewer"],
            design_max_revisions=0,
        )

    @staticmethod
    def report(request):
        return {
            "verdict": "pass",
            "issues": [],
            "previous_issues": [],
            "reader_checks": [
                {
                    "edge_ref": edge["edge_ref"],
                    "change_answer": "선택한 권한과 결과가 바뀐다.",
                    "reason_answer": "표시된 가상 접근 규칙이 적용된다.",
                    "invariant_answer": "같은 파일 열기 요청은 유지된다.",
                    "visible_refs": [
                        item["visible_ref"] for item in edge["visible_values"]
                    ],
                }
                for edge in request["reader_evidence"]
            ],
        }

    def test_proof_saved_and_resume_checks_candidate_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            verifier.check.return_value = {"passed": True}

            def reply(prompt, raw, candidates, **kwargs):
                request = json.loads(raw)
                if "reader_evidence" in request:
                    return GeneratedText(json.dumps(self.report(request)), "reviewer")
                return GeneratedText(json.dumps(self.candidate), "writer")

            models.complete_json.side_effect = reply
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            result = app.enhance(self.article, self.sources, self.cfg)
            self.assertIsNotNone(result.presentation)
            self.assertEqual(models.complete_json.call_count, 2)
            run = next((Path(directory) / ".design-runs").iterdir())
            self.assertTrue((run / "1-clarity.json").exists())
            self.assertTrue((run / "1-reader-checks.json").exists())
            canonical = json.loads((run / "1-review.json").read_text())
            self.assertNotIn("reader_checks", canonical)
            self.assertEqual(load_saved_design(run).article.body, self.article.body)
            checks = run / "1-reader-checks.json"
            checks.write_text("[]")
            with self.assertRaisesRegex(ModelGatewayError, "독자|reader|edge|경로"):
                load_saved_design(run)

    def test_empty_pass_repairs_report_not_design_then_holds(self):
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            verifier.check.return_value = {"passed": True}
            empty = GeneratedText(
                '{"verdict":"pass","issues":[],"previous_issues":[]}', "reviewer"
            )
            models.complete_json.side_effect = [
                GeneratedText(json.dumps(self.candidate), "writer"),
                empty,
                empty,
            ]
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            with self.assertRaises(ModelGatewayError):
                app.enhance(self.article, self.sources, self.cfg)
            calls = models.complete_json.call_args_list
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[1].args[2], ["reviewer"])
            self.assertEqual(calls[2].args[2], ["reviewer"])
            self.assertIn(
                "reader_checks", calls[1].kwargs["response_schema"]["required"]
            )


class DesignFlowTest(DesignHarness, unittest.TestCase):
    def test_success_preserves_exact_article(self):
        self.cfg["design_reasoning_efforts"] = {"designer": "low"}
        self.models.complete_json.side_effect = [
            GeneratedText(json.dumps(design_candidate()), "designer", {"cost": 0.01}),
            GeneratedText(design_review(), "reviewer"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_design(directory)
            self.assertEqual(result.body, DESIGN_BODY)
            self.assertEqual(result.source_urls, design_article().source_urls)
            self.assertIsNotNone(result.presentation)
            quality = json.loads(
                next(Path(directory).glob(".design-runs/*/1-quality.json")).read_text()
            )
            self.assertTrue(quality["semantic_review_required"])
            reviewer_input = json.loads(self.models.complete_json.call_args.args[1])
            self.assertEqual(reviewer_input["explanation_checks"], quality)
            self.assertIn("explanation", reviewer_input["candidate"]["scenes"][0])
            calls = self.models.complete_json.call_args_list
            self.assertIsNone(calls[0].kwargs["max_tokens"])
            self.assertEqual(calls[1].kwargs["max_tokens"], 5000)
            self.assertEqual(calls[0].kwargs["reasoning_efforts"], {"designer": "low"})
            self.assertNotIn("reasoning_efforts", calls[1].kwargs)
            self.assertEqual(
                len(list(Path(directory).glob(".design-runs/*/usage.json"))), 1
            )

    def test_height_warning_does_not_trigger_repair_or_skip_independent_review(self):
        self.cfg["design_required"] = True
        warning = BrowserSceneVerifier._check_height(972, 320, "start")
        self.verifier.check.return_value = {"warnings": [warning]}
        self.models.complete_json.side_effect = [
            GeneratedText(json.dumps(design_candidate()), "designer"),
            GeneratedText(design_review(), "reviewer"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_design(directory)
            self.assertIsNotNone(result.presentation)
            self.assertEqual(self.models.complete_json.call_count, 2)
            self.assertEqual(
                self.models.complete_json.call_args_list[1].kwargs["purpose"],
                "디자인 근거 검수",
            )
            report = json.loads(
                next(Path(directory).glob(".design-runs/*/1-browser.json")).read_text()
            )
            self.assertEqual(report[0]["warnings"], [warning])

    def test_one_repair_after_reviewer_rejection(self):
        self.models.complete_json.side_effect = [
            GeneratedText(json.dumps(design_candidate()), "designer"),
            GeneratedText(design_review(issue=True), "reviewer"),
            GeneratedText(scene_patch(), "designer"),
            GeneratedText(design_review(previous_status="resolved"), "reviewer"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNotNone(self.run_design(directory).presentation)
        repair_prompt = json.loads(self.models.complete_json.call_args_list[2].args[1])
        self.assertEqual(
            repair_prompt["repair_feedback"]["issues"][0]["problem"], "근거 보완"
        )
        review_prompt = json.loads(self.models.complete_json.call_args_list[3].args[1])
        self.assertIn("previous_review", review_prompt)
        self.assertIn("previous_candidate", review_prompt)
        self.assertEqual(self.models.complete_json.call_count, 4)

    def test_null_or_explicit_design_limit_is_forwarded_without_changing_review(self):
        for limit in (None, 64000):
            self.cfg["design_max_tokens"] = limit
            self.models.reset_mock()
            self.models.complete_json.side_effect = [
                GeneratedText(json.dumps(design_candidate()), "designer"),
                GeneratedText(design_review(), "reviewer"),
            ]
            with tempfile.TemporaryDirectory() as directory:
                self.assertIsNotNone(self.run_design(directory).presentation)
            calls = self.models.complete_json.call_args_list
            self.assertEqual(calls[0].kwargs["max_tokens"], limit)
            self.assertEqual(calls[1].kwargs["max_tokens"], 5000)

    def test_browser_failure_falls_back_and_never_calls_reviewer(self):
        self.models.complete_json.return_value = GeneratedText(
            json.dumps(design_candidate()), "designer"
        )
        self.verifier.check.side_effect = ValueError("mobile overflow")
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_design(directory), design_article())
        self.assertEqual(self.models.complete_json.call_count, 2)

    def test_model_failure_and_disabled_feature_preserve_article(self):
        self.models.complete_json.side_effect = ModelGatewayError("offline")
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_design(directory), design_article())
        self.assertEqual(self.models.complete_json.call_count, 1)
        self.cfg["design_enabled"] = False
        self.models.reset_mock()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_design(directory), design_article())
        self.models.complete_json.assert_not_called()

    def test_browser_missing_skips_paid_calls(self):
        self.verifier.preflight.side_effect = BrowserUnavailable("no browser")
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_design(directory), design_article())
        self.models.complete_json.assert_not_called()

    def test_required_design_failure_holds_instead_of_plain_article(self):
        self.cfg["design_required"] = True
        self.models.complete_json.side_effect = ModelGatewayError("offline")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ModelGatewayError):
                self.run_design(directory)
            state = json.loads(
                next(Path(directory).glob(".design-runs/*/result.json")).read_text()
            )
            self.assertEqual(state["status"], "held")

    def test_generated_css_issue_is_repairable_but_runtime_issue_is_not(self):
        for target, path, expected_calls in [
            ("content", "/candidate/scenes/0/css", 4),
            ("renderer", "/renderer/controls", 2),
        ]:
            report = json.loads(design_review(issue=True))
            report["issues"][0].update(target=target, path=path, kind="visual")
            final = json.loads(design_review(previous_status="resolved"))
            self.models.reset_mock()
            self.models.complete_json.side_effect = [
                GeneratedText(json.dumps(design_candidate()), "designer"),
                GeneratedText(json.dumps(report), "reviewer"),
                GeneratedText(scene_patch(), "designer"),
                GeneratedText(json.dumps(final), "reviewer"),
            ]
            with tempfile.TemporaryDirectory() as directory:
                result = self.run_design(directory)
            self.assertEqual(self.models.complete_json.call_count, expected_calls)
            self.assertEqual(result.presentation is not None, target == "content")


class ExplanationFlowTest(unittest.TestCase):
    def test_bad_quality_exhausts_one_repair_then_holds_before_browser_review(self):
        harness = DesignHarness()
        harness.setUp()
        harness.cfg["design_required"] = True
        value = design_candidate()
        del value["scenes"][0]["explanation"]
        harness.models.complete_json.return_value = GeneratedText(
            json.dumps(value), "designer"
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ModelGatewayError):
                harness.run_design(directory)
            state = json.loads(
                next(Path(directory).glob(".design-runs/*/result.json")).read_text()
            )
            self.assertEqual(state["status"], "held")
        harness.verifier.check.assert_not_called()
        self.assertEqual(harness.models.complete_json.call_count, 2)
        repaired = json.loads(harness.models.complete_json.call_args.args[1])
        self.assertIn("explanation", str(repaired["repair_feedback"]))


class InteractionPolicyTest(unittest.TestCase):
    def harness(self):
        harness = DesignHarness()
        harness.setUp()
        harness.cfg.update(
            design_required=True,
            design_interaction_required=True,
            design_max_revisions=0,
        )
        return harness

    def test_required_interaction_cannot_silently_fallback_to_plain_article(self):
        for key in ("design_enabled", "design_required"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                harness = self.harness()
                harness.cfg[key] = False
                with self.assertRaises(ModelGatewayError):
                    harness.run_design(directory)
                harness.models.complete_json.assert_not_called()

    def test_text_swap_is_held_without_semantic_review_when_policy_enabled(self):
        harness = self.harness()
        harness.models.complete_json.return_value = GeneratedText(
            json.dumps(design_candidate()), "designer"
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ModelGatewayError):
                harness.run_design(directory)
            issues = json.loads(
                next(
                    Path(directory).glob(".design-runs/*/1-validation-issues.json")
                ).read_text()
            )
            self.assertTrue(any(item["kind"] == "interaction" for item in issues))
        self.assertEqual(harness.models.complete_json.call_count, 1)
        self.assertTrue(
            json.loads(harness.models.complete_json.call_args.args[1])[
                "interaction_required"
            ]
        )

    def test_source_supported_transfer_still_requires_independent_review(self):
        harness = self.harness()
        harness.models.complete_json.side_effect = [
            GeneratedText(json.dumps(interactive_candidate()), "designer"),
            GeneratedText(design_review(), "reviewer"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = harness.run_design(directory)
        self.assertEqual(result.body, DESIGN_BODY)
        self.assertIsNotNone(result.presentation)
        self.assertEqual(harness.models.complete_json.call_count, 2)
        self.assertEqual(harness.models.complete_json.call_args.args[2], ["reviewer"])

    def test_mechanical_motion_pass_does_not_bypass_semantic_rejection(self):
        harness = self.harness()
        harness.models.complete_json.side_effect = [
            GeneratedText(json.dumps(interactive_candidate()), "designer"),
            GeneratedText(design_review(issue=True), "reviewer"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ModelGatewayError):
                harness.run_design(directory)
