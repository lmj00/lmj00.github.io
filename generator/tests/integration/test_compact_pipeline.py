"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from generator.contracts import Article, GeneratedText, ModelGatewayError
from generator.design.compact_scenes import compile_compact_design
from generator.design.design_pipeline import ArticleDesignPipeline
from generator.design.design_resume import load_saved_design
from generator.design.prompt_examples import examples
from generator.design.scene_document import validate_design
from generator.design.scene_motion import interaction_issues
from generator.main import load_prompt
from generator.tests.fixtures.design import (
    COMPACT_BODY,
    COMPACT_SOURCES,
    EXCERPTS,
    compact_candidate,
)
from generator.tests.fixtures.runs import (
    PASS,
    compile_resume_candidate,
    resume_article,
    resume_config,
    write_saved_snapshot,
)


class CompactPipelineTest(unittest.TestCase):
    def cfg(self):
        return dict(
            design_enabled=True,
            design_required=True,
            design_interaction_required=True,
            design_generation_format="compact",
            design_model_fallback=["writer"],
            design_review_model_fallback=["reviewer"],
            design_max_revisions=1,
        )

    def test_compact_generation_and_indexed_review_use_same_normal_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            verifier.check.return_value = {"passed": True}
            models.complete_json.side_effect = [
                GeneratedText(json.dumps(compact_candidate()), "writer"),
                GeneratedText(
                    '{"verdict":"pass","issues":[],"previous_issues":[]}', "reviewer"
                ),
            ]
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            article = Article(
                "정책", COMPACT_BODY, "original", (), (EXCERPTS[0]["source_url"],)
            )
            result = app.enhance(article, COMPACT_SOURCES, self.cfg())
            self.assertEqual(result.body, COMPACT_BODY)
            self.assertIsNotNone(result.presentation)
            first = json.loads(models.complete_json.call_args_list[0].args[1])
            self.assertNotIn("sources", first)
            self.assertNotIn("current_official_sections", first)
            self.assertEqual(first["headings"]["section_1"], "조건 적용")
            reviewed = json.loads(models.complete_json.call_args_list[1].args[1])
            self.assertIn("review_targets", reviewed)
            self.assertNotIn("sources", reviewed)
            self.assertNotIn("current_official_sections", reviewed)
            run = next((Path(directory) / ".design-runs").iterdir())
            self.assertTrue((run / "1-compact.json").exists())
            self.assertTrue((run / "1-candidate.json").exists())
            self.assertTrue((run / "provenance.json").exists())
            verifier.check.assert_called_once()

    def test_review_failure_repairs_only_compact_scene_then_rechecks(self):
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            verifier.check.return_value = {"passed": True}
            calls = []

            def reply(prompt, raw, models_used, **kwargs):
                inputs = json.loads(raw)
                calls.append(inputs)
                if len(calls) == 1:
                    value = compact_candidate()
                elif len(calls) == 2:
                    target = next(
                        item
                        for item in inputs["review_targets"]
                        if item["path"] == "/candidate/scenes/0/caption"
                    )
                    value = {
                        "verdict": "revise",
                        "previous_issues": [],
                        "issues": [
                            {
                                "id": "I1",
                                "target_ref": target["target_ref"],
                                "evidence_ref": None,
                                "kind": "readability",
                                "problem": "가정을 더 분명히 표시",
                                "suggestion": "가상 예시임을 명시",
                            }
                        ],
                    }
                elif len(calls) == 3:
                    scene = copy.deepcopy(inputs["repair_scenes"][0]["scene"])
                    scene["caption"] = (
                        "가상 정책 예시이며 실제 시스템과 연결하지 않는다."
                    )
                    value = {"patches": [{"scene_index": 0, "scene": scene}]}
                else:
                    value = {
                        "verdict": "pass",
                        "issues": [],
                        "previous_issues": [
                            {
                                "id": "I1",
                                "status": "resolved",
                                "reason": "가정 명시 확인",
                            }
                        ],
                    }
                return GeneratedText(
                    json.dumps(value), "reviewer" if len(calls) in (2, 4) else "writer"
                )

            models.complete_json.side_effect = reply
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            article = Article("정책", COMPACT_BODY, "original", (), ())
            result = app.enhance(article, COMPACT_SOURCES, self.cfg())
            self.assertIsNotNone(result.presentation)
            self.assertEqual(len(calls), 4)
            self.assertIn("html", calls[2]["repair_scenes"][0]["scene"])
            self.assertNotIn("html", calls[2]["repair_scenes"][0]["scene"]["states"][0])
            self.assertEqual(verifier.check.call_count, 2)

    def test_all_three_format_examples_compile_and_have_meaningful_choices(self):
        for example in examples():
            with self.subTest(summary=example["output"]["summary"]):
                inputs = example["input"]
                value = compile_compact_design(
                    example["output"], inputs["headings"], inputs["source_excerpts"]
                )
                validate_design(json.dumps(value), "### 가상 조건\n\n설명")
                self.assertEqual(interaction_issues(value), [])

    def test_mobile_media_closing_braces_are_not_template_bindings(self):
        value = compact_candidate()
        value["scenes"][0]["css"] += (
            "@media(max-width:400px){.scene-content .policy-card {gap:8px}}"
        )
        compiled = compile_compact_design(value, {"section_1": "조건 적용"}, EXCERPTS)
        self.assertIn("@media", compiled["scenes"][0]["css"])

    def test_invalid_generation_format_fails_before_paid_call(self):
        models = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            app = ArticleDesignPipeline(
                models, load_prompt, mock.Mock(), base_dir=Path(directory)
            )
            with self.assertRaises(ModelGatewayError):
                app.enhance(
                    Article("정책", COMPACT_BODY, "writer", (), ()),
                    COMPACT_SOURCES,
                    {**self.cfg(), "design_generation_format": "bad"},
                )
            models.complete_json.assert_not_called()

    def test_bad_css_repairs_only_css_then_runs_independent_review(self):
        original = compact_candidate()
        broken = copy.deepcopy(original)
        broken["scenes"][0]["css"] += (
            "@meddia(max-width:400px){.scene-content {gap:8px}}"
        )
        preserved = copy.deepcopy(broken)
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            verifier.check.return_value = {"passed": True}
            models.complete_json.side_effect = [
                GeneratedText(json.dumps(broken), "writer"),
                GeneratedText(
                    json.dumps(
                        {
                            "scene_index": 0,
                            "changes": {"css": original["scenes"][0]["css"]},
                        }
                    ),
                    "writer",
                ),
                GeneratedText(
                    '{"verdict":"pass","issues":[],"previous_issues":[]}', "reviewer"
                ),
            ]
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            result = app.enhance(
                Article("정책", COMPACT_BODY, "original", (), ()),
                COMPACT_SOURCES,
                self.cfg(),
            )
            self.assertEqual(result.body, COMPACT_BODY)
            self.assertIsNotNone(result.presentation)
            self.assertEqual(models.complete_json.call_count, 3)
            self.assertEqual(
                [call.args[2] for call in models.complete_json.call_args_list],
                [["writer"], ["writer"], ["reviewer"]],
            )
            repair = models.complete_json.call_args_list[1]
            self.assertEqual(repair.kwargs["purpose"], "디자인 필드 부분 수정")
            change_schema = repair.kwargs["response_schema"]["properties"]["changes"]
            self.assertEqual(set(change_schema["properties"]), {"css"})
            self.assertFalse(change_schema["additionalProperties"])
            run = next((Path(directory) / ".design-runs").iterdir())
            repaired = json.loads((run / "2-compact.json").read_text())
            self.assertEqual(repaired, original)
            self.assertEqual(
                repaired["scenes"][0]["html"], preserved["scenes"][0]["html"]
            )
            self.assertEqual(
                repaired["scenes"][0]["states"], preserved["scenes"][0]["states"]
            )
            self.assertTrue((run / "1-field-repair-plan.json").exists())
            verifier.check.assert_called_once()
        self.assertEqual(broken, preserved)

    def test_css_field_repair_cannot_smuggle_an_html_replacement(self):
        original = compact_candidate()
        broken = copy.deepcopy(original)
        broken["scenes"][0]["css"] += (
            "@meddia(max-width:400px){.scene-content {gap:8px}}"
        )
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            models.complete_json.side_effect = [
                GeneratedText(json.dumps(broken), "writer"),
                GeneratedText(
                    json.dumps(
                        {
                            "scene_index": 0,
                            "changes": {
                                "css": original["scenes"][0]["css"],
                                "html": "<p>범위 밖 변경</p>",
                            },
                        }
                    ),
                    "writer",
                ),
            ]
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            with self.assertRaises(ModelGatewayError):
                app.enhance(
                    Article("정책", COMPACT_BODY, "original", (), ()),
                    COMPACT_SOURCES,
                    self.cfg(),
                )
            self.assertEqual(models.complete_json.call_count, 2)
            self.assertEqual(
                [call.args[2] for call in models.complete_json.call_args_list],
                [["writer"], ["writer"]],
            )
            verifier.check.assert_not_called()
            run = next((Path(directory) / ".design-runs").iterdir())
            self.assertEqual(
                json.loads((run / "result.json").read_text())["status"], "held"
            )
            self.assertFalse((run / "2-candidate.json").exists())
            self.assertFalse(any(run.glob("*-review.json")))

    def test_unknown_binding_repairs_template_and_values_without_other_changes(self):
        original = compact_candidate()
        broken = copy.deepcopy(original)
        broken["scenes"][0]["html"] += "<p>{{unknown_slot}}</p>"
        preserved = copy.deepcopy(broken)
        changes = {
            field: copy.deepcopy(original["scenes"][0][field])
            for field in ("html", "states")
        }
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            verifier.check.return_value = {"passed": True}
            models.complete_json.side_effect = [
                GeneratedText(json.dumps(broken), "writer"),
                GeneratedText(
                    json.dumps({"scene_index": 0, "changes": changes}), "writer"
                ),
                GeneratedText(
                    '{"verdict":"pass","issues":[],"previous_issues":[]}', "reviewer"
                ),
            ]
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            result = app.enhance(
                Article("정책", COMPACT_BODY, "original", (), ()),
                COMPACT_SOURCES,
                self.cfg(),
            )
            self.assertEqual(result.body, COMPACT_BODY)
            self.assertEqual(models.complete_json.call_count, 3)
            repair = models.complete_json.call_args_list[1]
            self.assertEqual(repair.kwargs["purpose"], "디자인 필드 부분 수정")
            change_schema = repair.kwargs["response_schema"]["properties"]["changes"]
            self.assertEqual(set(change_schema["properties"]), {"html", "states"})
            run = next((Path(directory) / ".design-runs").iterdir())
            repaired = json.loads((run / "2-compact.json").read_text())
            self.assertEqual(repaired, original)
            for field in set(original["scenes"][0]) - {"html", "states"}:
                self.assertEqual(
                    repaired["scenes"][0][field], preserved["scenes"][0][field]
                )
            verifier.check.assert_called_once()
        self.assertEqual(broken, preserved)

    def test_repaired_fields_are_recompiled_and_failed_compile_does_not_extend_budget(
        self,
    ):
        broken = compact_candidate()
        broken["scenes"][0]["css"] += (
            "@meddia(max-width:400px){.scene-content {gap:8px}}"
        )
        with tempfile.TemporaryDirectory() as directory:
            models, verifier = mock.Mock(), mock.Mock()
            models.complete_json.side_effect = [
                GeneratedText(json.dumps(broken), "writer"),
                GeneratedText(
                    json.dumps(
                        {
                            "scene_index": 0,
                            "changes": {"css": broken["scenes"][0]["css"]},
                        }
                    ),
                    "writer",
                ),
            ]
            app = ArticleDesignPipeline(
                models, load_prompt, verifier, base_dir=Path(directory)
            )
            with self.assertRaises(ModelGatewayError):
                app.enhance(
                    Article("정책", COMPACT_BODY, "original", (), ()),
                    COMPACT_SOURCES,
                    self.cfg(),
                )
            self.assertEqual(models.complete_json.call_count, 2)
            verifier.check.assert_not_called()
            run = next((Path(directory) / ".design-runs").iterdir())
            state = json.loads((run / "result.json").read_text())
            self.assertEqual(state["status"], "held")
            self.assertEqual(state["stage"], "compile")
            self.assertEqual(state["attempts"], 2)


class CompactResumeTest(unittest.TestCase):
    def app(self, root, models=None, verifier=None):
        models = models if models is not None else mock.Mock()
        verifier = verifier if verifier is not None else mock.Mock()
        verifier.check.return_value = {"passed": True}
        return (
            ArticleDesignPipeline(models, load_prompt, verifier, base_dir=root),
            models,
            verifier,
        )

    def test_generated_compact_snapshot_loads_roundtrip_without_file_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, models, _ = self.app(root)
            models.complete_json.side_effect = [
                GeneratedText(json.dumps(compact_candidate()), "writer"),
                GeneratedText(json.dumps(PASS), "reviewer"),
            ]
            generated = app.enhance(resume_article(), COMPACT_SOURCES, resume_config())
            run = next((root / ".design-runs").iterdir())
            before = {
                path.name: path.read_bytes() for path in run.iterdir() if path.is_file()
            }
            saved = load_saved_design(run)
            after = {
                path.name: path.read_bytes() for path in run.iterdir() if path.is_file()
            }
        self.assertIsNotNone(generated.presentation)
        self.assertEqual(saved.compact_candidate, compact_candidate())
        self.assertEqual(
            json.loads(saved.candidate.content),
            compile_resume_candidate(saved.compact_candidate),
        )
        self.assertEqual(saved.article.body, COMPACT_BODY)
        self.assertEqual(saved.sources, COMPACT_SOURCES)
        self.assertEqual(saved.author_models, ("writer",))
        self.assertEqual(before, after)

    def test_tampered_saved_compact_is_rejected_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "saved"
            value = write_saved_snapshot(run)
            value["scenes"][0]["caption"] = "변경된 설명"
            (run / "1-compact.json").write_text(json.dumps(value), encoding="utf-8")
            with (
                mock.patch("generator.providers.openrouter.requests.post") as post,
                self.assertRaises(ModelGatewayError),
            ):
                load_saved_design(run)
            post.assert_not_called()

    def test_direct_inconsistent_compact_seed_is_rejected_before_api(self):
        value = compact_candidate()
        expanded = compile_resume_candidate(value)
        bad = copy.deepcopy(value)
        bad["scenes"][0]["caption"] = "초기 후보와 불일치"
        before = copy.deepcopy(bad)
        with tempfile.TemporaryDirectory() as directory:
            app, models, _ = self.app(Path(directory))
            with self.assertRaises(ModelGatewayError):
                app.enhance(
                    resume_article(),
                    COMPACT_SOURCES,
                    resume_config(),
                    initial_candidate=GeneratedText(json.dumps(expanded), "writer"),
                    initial_author_models=("writer",),
                    initial_compact_candidate=bad,
                )
            models.complete_json.assert_not_called()
        self.assertEqual(bad, before)

    def test_legacy_saved_candidate_still_resumes_without_compact_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_saved_snapshot(root / "saved", compact=False)
            saved = load_saved_design(root / "saved")
            self.assertIsNone(saved.compact_candidate)
            app, models, _ = self.app(root / "resumed")
            models.complete_json.return_value = GeneratedText(
                json.dumps(PASS), "reviewer"
            )
            result = app.enhance(
                saved.article,
                saved.sources,
                resume_config(design_generation_format="legacy"),
                initial_candidate=saved.candidate,
                initial_author_models=saved.author_models,
            )
            self.assertEqual(result.body, COMPACT_BODY)
            self.assertIsNotNone(result.presentation)
            models.complete_json.assert_called_once()
            self.assertEqual(models.complete_json.call_args.args[2], ["reviewer"])

    def test_saved_compact_browser_failure_only_calls_compact_repair_then_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_saved_snapshot(root / "saved")
            saved = load_saved_design(root / "saved")
            original_compact = copy.deepcopy(saved.compact_candidate)
            original_expanded = saved.candidate.content
            saved_bytes = {
                path.name: path.read_bytes() for path in (root / "saved").iterdir()
            }
            app, models, verifier = self.app(root / "resumed")
            verifier.check.side_effect = [
                ValueError("mobile layout overflow"),
                {"passed": True},
            ]
            repaired_scene = copy.deepcopy(saved.compact_candidate["scenes"][0])
            repaired_scene["caption"] = (
                "같은 정책을 두 조건으로 비교하는 가상 실험이다."
            )
            models.complete_json.side_effect = [
                GeneratedText(
                    json.dumps(
                        {"patches": [{"scene_index": 0, "scene": repaired_scene}]}
                    ),
                    "writer",
                ),
                GeneratedText(json.dumps(PASS), "reviewer"),
            ]
            result = app.enhance(
                saved.article,
                saved.sources,
                resume_config(design_generation_format="legacy"),
                initial_candidate=saved.candidate,
                initial_author_models=saved.author_models,
                initial_review_context=saved.review_context,
                initial_compact_candidate=saved.compact_candidate,
            )
            self.assertIsNotNone(result.presentation)
            self.assertEqual(models.complete_json.call_count, 2)
            repair, review = models.complete_json.call_args_list
            self.assertEqual(repair.args[2], ["writer"])
            self.assertEqual(review.args[2], ["reviewer"])
            repair_request = json.loads(repair.args[1])
            scene = repair_request["repair_scenes"][0]["scene"]
            self.assertIn("html", scene)
            self.assertNotIn("html", scene["states"][0])
            self.assertEqual(scene, original_compact["scenes"][0])
            self.assertEqual(verifier.check.call_count, 2)
            self.assertEqual(saved.compact_candidate, original_compact)
            self.assertEqual(saved.candidate.content, original_expanded)
            self.assertEqual(
                saved_bytes,
                {path.name: path.read_bytes() for path in (root / "saved").iterdir()},
            )
            resumed_run = next((root / "resumed" / ".design-runs").iterdir())
            provenance = json.loads((resumed_run / "provenance.json").read_text())
            self.assertEqual(provenance["generation_format"], "compact")
            reloaded = load_saved_design(resumed_run)
            self.assertEqual(
                reloaded.compact_candidate["scenes"][0]["caption"],
                repaired_scene["caption"],
            )

    def test_invalid_review_reference_retries_same_reviewer_not_designer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, models, _ = self.app(root)
            roles = []

            def reply(prompt, raw, candidates, **kwargs):
                roles.append(list(candidates))
                if len(roles) == 1:
                    return GeneratedText(json.dumps(compact_candidate()), "writer")
                inputs = json.loads(raw)
                target = next(
                    item
                    for item in inputs["review_targets"]
                    if item["path"] == "/candidate/scenes/0/caption"
                )
                evidence = (
                    None
                    if len(roles) == 2
                    else inputs["source_excerpts"][0]["excerpt_id"]
                )
                review = {
                    "verdict": "revise",
                    "previous_issues": [],
                    "issues": [
                        {
                            "id": "I1",
                            "target_ref": target["target_ref"],
                            "evidence_ref": evidence,
                            "kind": "factual",
                            "problem": "조건 설명의 근거를 확인해야 한다.",
                            "suggestion": "공식 원문에 맞게 조건을 설명한다.",
                        }
                    ],
                }
                return GeneratedText(json.dumps(review), "reviewer")

            models.complete_json.side_effect = reply
            with self.assertRaises(ModelGatewayError):
                app.enhance(
                    resume_article(),
                    COMPACT_SOURCES,
                    resume_config(design_max_revisions=0),
                )
            self.assertEqual(roles, [["writer"], ["reviewer"], ["reviewer"]])
            repair_call = models.complete_json.call_args_list[-1]
            self.assertEqual(repair_call.kwargs["format_retries"], 0)
            self.assertIn("report_format_error", json.loads(repair_call.args[1]))
            run = next((root / ".design-runs").iterdir())
            canonical = json.loads((run / "1-review.json").read_text())
            self.assertEqual(canonical["verdict"], "revise")
            self.assertEqual(
                canonical["issues"][0]["path"], "/candidate/scenes/0/caption"
            )
            self.assertTrue(canonical["issues"][0]["source_quote"])
