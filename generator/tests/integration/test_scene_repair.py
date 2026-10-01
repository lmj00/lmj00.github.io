"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import generator.main as main
from generator.contracts import GeneratedText, ModelGatewayError
from generator.design.design_pipeline import ArticleDesignPipeline
from generator.design.design_resume import load_saved_design
from generator.tests.fixtures.design import (
    DESIGN_BODY,
    DESIGN_SOURCES,
    DesignHarness,
    design_article,
    design_candidate,
    design_review,
    scene_patch,
)
from generator.tests.fixtures.runs import (
    break_entities,
    broken_candidate,
    repair_response,
    scene_repair_inputs,
    two_scenes,
)


class EvidenceRepairFlowTest(unittest.TestCase):
    def harness(self):
        harness = DesignHarness()
        harness.setUp()
        harness.cfg["design_required"] = True
        return harness

    def test_repair_reuses_candidate_and_still_requires_browser_and_independent_review(
        self,
    ):
        harness = self.harness()
        harness.cfg["design_review_model_fallback"] = ["repairer", "reviewer"]
        harness.models.complete_json.side_effect = [
            GeneratedText(json.dumps(broken_candidate()), "designer"),
            GeneratedText(repair_response(), "repairer"),
            GeneratedText(design_review(), "reviewer"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = harness.run_design(directory)
            self.assertEqual(result.body, DESIGN_BODY)
            self.assertEqual(result.presentation.model, "designer")
            saved = next(Path(directory).glob(".design-runs/*/2-candidate.json"))
            self.assertEqual(json.loads(saved.read_text()), design_candidate())
            self.assertTrue(saved.with_name("1-evidence-issues.json").exists())
        calls = harness.models.complete_json.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[1].kwargs["purpose"], "디자인 인용 부분 수정")
        self.assertNotIn("previous_candidate", json.loads(calls[1].args[1]))
        self.assertIsNone(calls[1].kwargs["max_tokens"])
        self.assertEqual(calls[2].args[2], ["reviewer"])
        self.assertEqual(json.loads(calls[2].args[1])["candidate"], design_candidate())
        self.assertEqual(harness.verifier.check.call_count, 2)

    def test_failed_partial_repair_holds_without_full_regeneration_or_review(self):
        harness = self.harness()
        harness.models.complete_json.side_effect = [
            GeneratedText(json.dumps(broken_candidate()), "designer"),
            GeneratedText(repair_response(None), "designer"),
        ]
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaises(ModelGatewayError),
        ):
            harness.run_design(directory)
        self.assertEqual(harness.models.complete_json.call_count, 2)
        harness.verifier.check.assert_called_once()

    def test_zero_revision_budget_does_not_add_paid_repair(self):
        harness = self.harness()
        harness.cfg["design_max_revisions"] = 0
        harness.models.complete_json.return_value = GeneratedText(
            json.dumps(broken_candidate()), "designer"
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaises(ModelGatewayError),
        ):
            harness.run_design(directory)
        harness.models.complete_json.assert_called_once()

    def test_live_progress_is_persisted_before_gateway_returns(self):
        harness = self.harness()
        with tempfile.TemporaryDirectory() as directory:

            def complete(system, user, models, **kwargs):
                kwargs["on_progress"](
                    {
                        "event": "headers_received",
                        "response_id": "gen-live",
                        "received_bytes": 0,
                        "content_chars": 0,
                    }
                )
                state = json.loads(
                    next(Path(directory).glob(".design-runs/*/result.json")).read_text()
                )
                self.assertEqual(state["status"], "running")
                self.assertEqual(state["live_request"]["response_id"], "gen-live")
                self.assertTrue(
                    list(Path(directory).glob(".design-runs/*/*-progress.jsonl"))
                )
                return GeneratedText(
                    json.dumps(design_candidate())
                    if models == ["designer"]
                    else design_review(),
                    models[0],
                )

            harness.models.complete_json.side_effect = complete
            result = harness.run_design(directory)
            self.assertIsNotNone(result.presentation)

    def test_structural_fault_is_not_hidden_by_exact_quote_repair(self):
        harness = self.harness()
        value = broken_candidate()
        value["scenes"][0]["explanation"]["key_entities"] = ["missing-packet"]
        harness.models.complete_json.return_value = GeneratedText(
            json.dumps(value), "designer"
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaises(ModelGatewayError),
        ):
            harness.run_design(directory)
        calls = harness.models.complete_json.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1].kwargs["purpose"], "디자인 장면 부분 수정")
        self.assertIn(
            "missing-packet", str(json.loads(calls[1].args[1])["repair_feedback"])
        )
        harness.verifier.check.assert_called_once()


class SceneRepairFlowTest(unittest.TestCase):
    def harness(self, directory):
        harness = DesignHarness()
        harness.setUp()
        harness.cfg["design_required"] = True
        pipeline = ArticleDesignPipeline(
            harness.models,
            lambda _: "prompt",
            harness.verifier,
            base_dir=Path(directory),
        )
        return harness, pipeline

    def test_saved_candidate_needs_only_patch_and_review_and_preserves_body(self):
        value = two_scenes()
        break_entities(value)
        with tempfile.TemporaryDirectory() as directory:
            harness, pipeline = self.harness(directory)
            harness.cfg["design_review_model_fallback"] = [
                "original-designer",
                "repairer",
                "reviewer",
            ]
            harness.models.complete_json.side_effect = [
                GeneratedText(scene_patch(two_scenes(), [0]), "repairer"),
                GeneratedText(design_review(), "reviewer"),
            ]
            result = pipeline.enhance(
                design_article(),
                DESIGN_SOURCES,
                harness.cfg,
                initial_candidate=GeneratedText(
                    json.dumps(value), "original-designer", {"cost": 100}
                ),
                initial_author_models=("original-designer",),
            )
            self.assertEqual(result.body, DESIGN_BODY)
            self.assertIsNotNone(result.presentation)
            calls = harness.models.complete_json.call_args_list
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].kwargs["purpose"], "디자인 장면 부분 수정")
            self.assertEqual(calls[1].args[2], ["reviewer"])
            saved = next(Path(directory).glob(".design-runs/*/2-candidate.json"))
            self.assertEqual(
                json.loads(saved.read_text())["scenes"][1], value["scenes"][1]
            )
            self.assertEqual(harness.verifier.check.call_count, 4)
            seed = json.loads(saved.with_name("1-saved-response.json").read_text())
            self.assertNotIn("cost", seed.get("usage", {}))
            self.assertTrue(saved.with_name("1-validation-issues.json").exists())

    def test_semantic_rejection_after_patch_still_holds(self):
        value = design_candidate()
        break_entities(value)
        with tempfile.TemporaryDirectory() as directory:
            harness, pipeline = self.harness(directory)
            harness.models.complete_json.side_effect = [
                GeneratedText(scene_patch(), "designer"),
                GeneratedText(design_review(issue=True), "reviewer"),
            ]
            with self.assertRaises(ModelGatewayError):
                pipeline.enhance(
                    design_article(),
                    DESIGN_SOURCES,
                    harness.cfg,
                    initial_candidate=GeneratedText(json.dumps(value), "designer"),
                )
            self.assertEqual(harness.models.complete_json.call_count, 2)

    def test_all_browser_failures_are_collected_and_no_unsafe_review_occurs(self):
        with tempfile.TemporaryDirectory() as directory:
            harness, pipeline = self.harness(directory)
            harness.cfg["design_max_revisions"] = 0
            harness.verifier.check.side_effect = [
                ValueError("scene A overflow"),
                ValueError("scene B tiny text"),
            ]
            with self.assertRaises(ModelGatewayError):
                pipeline.enhance(
                    design_article(),
                    DESIGN_SOURCES,
                    harness.cfg,
                    initial_candidate=GeneratedText(
                        json.dumps(two_scenes()), "designer"
                    ),
                )
            issues = json.loads(
                next(
                    Path(directory).glob(".design-runs/*/1-repair-issues.json")
                ).read_text()
            )
            self.assertEqual(len(issues), 2)
            harness.models.complete_json.assert_not_called()

    def test_quote_and_browser_errors_are_in_one_scene_repair_request(self):
        value = two_scenes()
        value["scenes"][1]["explanation"]["evidence"][0]["quote"] = "없는 인용"
        with tempfile.TemporaryDirectory() as directory:
            harness, pipeline = self.harness(directory)
            harness.verifier.check.side_effect = [
                ValueError("mobile height exceeded"),
                {},
                {},
                {},
            ]
            harness.models.complete_json.side_effect = [
                GeneratedText(scene_patch(two_scenes()), "designer"),
                GeneratedText(design_review(), "reviewer"),
            ]
            result = pipeline.enhance(
                design_article(),
                DESIGN_SOURCES,
                harness.cfg,
                initial_candidate=GeneratedText(json.dumps(value), "designer"),
            )
            self.assertIsNotNone(result.presentation)
            calls = harness.models.complete_json.call_args_list
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].kwargs["purpose"], "디자인 장면 부분 수정")
            request = json.loads(calls[0].args[1])
            self.assertEqual(
                {item["kind"] for item in request["repair_feedback"]["issues"]},
                {"evidence", "browser"},
            )
            self.assertEqual(
                [item["scene_index"] for item in request["repair_scenes"]], [0, 1]
            )
            self.assertEqual(harness.verifier.check.call_count, 4)


class ResumeTest(unittest.TestCase):
    def save_run(self, root):
        (root / "input.json").write_text(json.dumps(scene_repair_inputs()))
        (root / "2-candidate.json").write_text(json.dumps(design_candidate()))
        (root / "1-designer-response.json").write_text(
            json.dumps({"model": "z-original"})
        )
        (root / "2-scene-repair-response.json").write_text(
            json.dumps({"model": "a-repairer"})
        )

    def test_loader_preserves_sources_body_and_all_authors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.save_run(root)
            saved = load_saved_design(root)
            self.assertEqual(saved.article.body, DESIGN_BODY)
            self.assertEqual(saved.candidate.model, "z-original")
            self.assertEqual(saved.author_models, ("a-repairer", "z-original"))
            value = scene_repair_inputs()
            value["current_official_sections"][0]["content"] = "mismatch"
            (root / "input.json").write_text(json.dumps(value))
            with self.assertRaises(ModelGatewayError):
                load_saved_design(root)

    def test_cli_requires_unique_local_preview_and_skips_topic_and_draft_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.save_run(root)
            with (
                mock.patch.object(main, "load_dotenv"),
                mock.patch.object(
                    main,
                    "load_config",
                    return_value={
                        "review_enabled": True,
                        "design_enabled": True,
                        "design_required": True,
                    },
                ),
                mock.patch.object(main, "JekyllPreviewPublisher") as publisher,
                mock.patch.object(main, "ArticleDesignPipeline") as design,
                mock.patch.object(main, "GeneratorPipeline") as full,
            ):
                self.assertEqual(
                    main.main(
                        [
                            "--local-preview",
                            "resume-test",
                            "--resume-design-run",
                            str(root),
                        ]
                    ),
                    0,
                )
                full.assert_not_called()
                self.assertIn(
                    "initial_candidate", design.return_value.enhance.call_args.kwargs
                )
                publisher.return_value.publish.assert_called_once()
            with self.assertRaises(SystemExit):
                main.main(["--resume-design-run", str(root)])

    def test_missing_or_invalid_saved_run_makes_no_api_call(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaises(ModelGatewayError),
        ):
            load_saved_design(Path(directory))

    def test_review_history_survives_resumes_and_runtime_issues_are_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.save_run(root)
            report = json.loads(design_review(issue=True))
            (root / "saved-review-context.json").write_text(
                json.dumps(
                    {
                        "report": report,
                        "candidate": design_candidate(),
                        "previous_review": None,
                    }
                )
            )
            saved = load_saved_design(root)
            self.assertEqual(saved.review_context["report"], report)
            report["issues"][0].update(
                target="renderer", path="/renderer/controls", kind="visual"
            )
            (root / "saved-review-context.json").write_text(
                json.dumps(
                    {
                        "report": report,
                        "candidate": design_candidate(),
                        "previous_review": None,
                    }
                )
            )
            with self.assertRaises(ModelGatewayError):
                load_saved_design(root)

    def test_empty_revision_budget_preserves_seed_without_extra_api_call(self):
        value = design_candidate()
        break_entities(value)
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            pipeline = ArticleDesignPipeline(
                models, lambda _: "prompt", verifier, base_dir=Path(directory)
            )
            with self.assertRaises(ModelGatewayError):
                pipeline.enhance(
                    design_article(),
                    DESIGN_SOURCES,
                    {
                        "design_enabled": True,
                        "design_required": True,
                        "design_max_revisions": 0,
                    },
                    initial_candidate=GeneratedText(json.dumps(value), "designer"),
                )
            models.complete_json.assert_not_called()
