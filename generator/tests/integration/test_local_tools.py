"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import generator.main as main_main
import generator.tools.local_preview as local_preview
import generator.tools.preview_design as preview_design
from generator.tests.fixtures.design import (
    COMPACT_BODY,
    COMPACT_SOURCES,
    DESIGN_BODY,
    DESIGN_SOURCES,
    design_candidate,
)
from generator.tests.fixtures.runs import (
    preview_server,
    run_fixture,
    saved_run,
    write_run_file,
)
from generator.tools.design_eval import _digest, compare_runs, main, summarize_run
from generator.tools.local_profile import local_settings


class DesignEvalTest(unittest.TestCase):
    def test_offline_report_keeps_held_status_and_does_not_double_count_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_fixture(Path(directory), "run")
            with mock.patch(
                "socket.socket", side_effect=AssertionError("network forbidden")
            ):
                report = compare_runs([run])
            result = report["runs"][0]
        self.assertTrue(report["offline"])
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["failure_stage"], "design_validation")
        self.assertEqual(len(result["api_calls"]), 1)
        self.assertEqual(result["usage"]["input_tokens"]["reported"], 100)
        self.assertEqual(result["usage"]["output_tokens"]["reported"], 30)
        self.assertEqual(result["usage"]["reasoning_tokens"]["reported"], 10)
        self.assertEqual(result["usage"]["cached_input_tokens"]["reported"], 20)
        self.assertEqual(result["usage"]["reported_cost_usd"]["reported"], 0.01)
        self.assertEqual(result["browser"][0]["reports"][0]["moving_steps_checked"], 4)
        self.assertEqual(result["validation"][0]["counts"], {"evidence": 2})
        self.assertIsNone(result["timing"]["run_elapsed_seconds"])
        self.assertEqual(result["timing"]["api_seconds_reported"], 4.5)

    def test_missing_failure_usage_is_unknown_not_zero_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_fixture(Path(directory), "run")
            write_run_file(
                run / "2-scene-repair-http-2.json",
                {
                    "model": "same-model",
                    "status": "request_error",
                    "usage": {},
                    "elapsed_seconds": 2,
                },
            )
            result = summarize_run(run)
        total = result["usage"]["reported_cost_usd"]
        self.assertEqual(total["reported"], 0.01)
        self.assertEqual(total["unknown_calls"], 1)
        self.assertFalse(total["complete"])
        self.assertEqual(len(result["failures_with_unreported_cost"]), 1)
        self.assertEqual(result["timing"]["api_seconds_reported"], 6.5)

    def test_missing_http_uses_index_without_inventing_latency_or_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_fixture(Path(directory), "run")
            write_run_file(
                run / "usage.json",
                [
                    {"artifact": "1-designer-http-1.json"},
                    {
                        "artifact": "2-reviewer-http-2.json",
                        "purpose": "reviewer",
                        "model": "review-model",
                        "status": "valid",
                        "usage": {"cost": 0.02},
                    },
                ],
            )
            result = summarize_run(run)
        self.assertEqual(len(result["api_calls"]), 2)
        self.assertAlmostEqual(result["usage"]["reported_cost_usd"]["reported"], 0.03)
        self.assertFalse(result["timing"]["api_seconds_complete"])
        self.assertIsNone(result["api_calls"][-1]["provider"])
        self.assertIn(
            "missing_http_artifact",
            {item["error"] for item in result["artifact_problems"]},
        )

    def test_canonical_compact_expanded_counts_and_recorded_elapsed(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_fixture(Path(directory), "run", status="pass")
            compact = {"summary": "검사 대상", "scenes": []}
            (run / "1-compact.json").write_text(
                json.dumps(compact, ensure_ascii=False, indent=4), encoding="utf-8"
            )
            state = json.loads((run / "result.json").read_text())
            write_run_file(run / "result.json", {**state, "elapsed_seconds": 8.2})
            result = summarize_run(run)
        sizes = result["candidate_sizes"][0]
        self.assertEqual(
            sizes["compact_json_chars"],
            len(json.dumps(compact, ensure_ascii=False, separators=(",", ":"))),
        )
        self.assertGreater(sizes["expanded_json_chars"], sizes["compact_json_chars"])
        self.assertEqual(result["timing"]["run_elapsed_seconds"], 8.2)
        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["failure_stage"])

    def test_only_matching_sources_article_and_generation_model_form_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = run_fixture(root, "a")
            second = run_fixture(root, "b", provider="provider-b", effort="high")
            third = run_fixture(root, "c", article="다른 본문")
            fourth = run_fixture(root, "d", model="other-model")
            fifth = run_fixture(root, "e")
            inputs = json.loads((fifth / "input.json").read_text())
            inputs["current_official_sections"][0]["content"] = "다른 원문"
            write_run_file(fifth / "input.json", inputs)
            report = compare_runs([first, second, third, fourth, fifth])
        self.assertEqual(len(report["comparisons"]), 1)
        comparison = report["comparisons"][0]
        self.assertEqual(comparison["runs"], ["R01", "R02"])
        self.assertIn("Provider choices differ or are unknown.", comparison["caveats"])
        self.assertIn(
            "Reasoning effort/budget differs or is unknown.", comparison["caveats"]
        )
        self.assertEqual(report["unmatched_or_incomplete_runs"], ["R03", "R04", "R05"])

    def test_provenance_fingerprints_match_and_tampered_sources_are_not_grouped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = run_fixture(root, "a")
            second = run_fixture(root, "b")
            inputs = json.loads((first / "input.json").read_text())
            write_run_file(
                first / "provenance.json",
                {
                    "generation_format": "compact",
                    "source_digest": _digest(inputs["current_official_sections"]),
                    "article_digest": _digest(inputs["article"]),
                    "prompt_digest": _digest(
                        {"designer": "designer", "reviewer": "reviewer"}
                    ),
                },
            )
            result = summarize_run(first)
            self.assertEqual(result["provenance_mismatches"], [])
            self.assertEqual(result["generation_format"], "compact")
            write_run_file(second / "provenance.json", {"source_digest": "wrong"})
            report = compare_runs([first, second])
        self.assertEqual(report["comparisons"], [])
        self.assertEqual(report["runs"][1]["provenance_mismatches"], ["sources"])

    def test_latest_saved_candidate_is_not_misrepresented_as_last_failed_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_fixture(Path(directory), "run")
            write_run_file(
                run / "result.json",
                {"status": "held", "stage": "scene_repair", "attempts": 2},
            )
            result = summarize_run(run)
        self.assertFalse(result["human_review"]["candidate_is_last_attempt"])
        self.assertEqual(result["human_review"]["candidate_attempt"], 1)
        self.assertEqual(result["failure_stage"], "scene_repair")

    def test_malformed_artifact_is_reported_not_silently_treated_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_fixture(Path(directory), "run")
            (run / "2-reviewer-http-2.json").write_text("{", encoding="utf-8")
            write_run_file(run / "result.json", {"status": [], "design_model": {}})
            result = summarize_run(run)
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(result["usage"]["reported_cost_usd"]["complete"])
        self.assertTrue(result["artifact_problems"])

    def test_cli_prints_json_without_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_fixture(Path(directory), "run")
            before = sorted(path.name for path in run.iterdir())
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([str(run)]), 0)
            self.assertTrue(json.loads(output.getvalue())["offline"])
            self.assertEqual(before, sorted(path.name for path in run.iterdir()))


class LocalPreviewTest(unittest.TestCase):
    def test_cli_does_not_load_env_config_or_any_pipeline(self):
        with (
            mock.patch.object(local_preview, "serve_saved_design") as serve,
            mock.patch.object(main_main, "load_dotenv") as env,
            mock.patch.object(main_main, "load_config") as config,
            mock.patch.object(main_main, "OpenRouterGateway") as models,
            mock.patch.object(main_main, "GeneratorPipeline") as pipeline,
            mock.patch.object(main_main, "JekyllPreviewPublisher") as publish,
        ):
            self.assertEqual(
                main_main.main(
                    ["--render-design-run", "/tmp/run", "--local-preview", "test"]
                ),
                0,
            )
            serve.assert_called_once_with(Path("/tmp/run").resolve(), "test", 4011)
            for dependency in (env, config, models, pipeline, publish):
                dependency.assert_not_called()

    def test_readonly_reload_uses_latest_candidate_and_current_renderer(self):
        with saved_run() as root, preview_server(root) as address:
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            with urlopen(address + "/test/?width=320") as response:
                page = response.read().decode()
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIn("noindex", response.headers["X-Robots-Tag"])
            self.assertIn("API 호출 없음", page)
            self.assertIn("검수 전", page)
            self.assertIn("width:320px", page)
            self.assertIn("확인 &lt;설명&gt;", page)
            digest = hashlib.sha256(before["2-candidate.json"]).hexdigest()
            route = address + f"/test/scene/0?candidate={digest}"
            with mock.patch.object(
                local_preview,
                "render_document",
                side_effect=["first renderer", "changed renderer"],
            ):
                self.assertEqual(urlopen(route).read(), b"first renderer")
                self.assertEqual(urlopen(route).read(), b"changed renderer")
            self.assertEqual(
                before, {path.name: path.read_bytes() for path in root.iterdir()}
            )
            newer = design_candidate()
            newer["scenes"][0]["title"] = "새 후보"
            (root / "10-candidate.json").write_text(json.dumps(newer))
            self.assertIn("새 후보", urlopen(address + "/test/").read().decode())
            with self.assertRaises(HTTPError) as caught:
                urlopen(route)
            self.assertEqual(caught.exception.code, 409)
            caught.exception.close()

    def test_html_is_sandboxed_and_no_arbitrary_files_are_served(self):
        with saved_run() as root, preview_server(root) as address:
            snapshot = local_preview.read_snapshot(root)
            route = address + f"/test/scene/0?candidate={snapshot['digest']}"
            content = urlopen(route).read().decode()
            self.assertIn("Content-Security-Policy", content)
            page = urlopen(address + "/test/").read().decode()
            self.assertIn('sandbox="allow-scripts"', page)
            self.assertNotIn("allow-same-origin", page)
            with self.assertRaises(HTTPError) as caught:
                urlopen(
                    Request(address + "/test/", headers={"Host": "untrusted.example"})
                )
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
            for path in ("/input.json", "/.env", "/../sources.json", "/test/scene/2"):
                with self.assertRaises(HTTPError) as caught:
                    urlopen(address + path)
                self.assertEqual(caught.exception.code, 404)
                caught.exception.close()
            bad = design_candidate()
            bad["scenes"][0]["states"][0]["html"] = "<script>alert(1)</script>"
            (root / "2-candidate.json").write_text(json.dumps(bad))
            with self.assertRaises(HTTPError) as caught:
                urlopen(address + "/test/")
            self.assertEqual(caught.exception.code, 422)
            caught.exception.close()

    def test_bad_flag_combinations_never_create_a_gateway(self):
        for args in (
            ["--render-design-run", "/tmp/run"],
            ["--local-fast"],
            ["--preview-design-model", "qwen/qwen3.8-flash"],
            ["--first-content-timeout", "120"],
            [
                "--local-preview",
                "test",
                "--render-design-run",
                "/tmp/run",
                "--local-fast",
            ],
            [
                "--local-preview",
                "test",
                "--render-design-run",
                "/tmp/run",
                "--resume-design-run",
                "/tmp/run",
            ],
            ["--local-preview", "test", "--preview-port", "4011"],
        ):
            with (
                self.subTest(args=args),
                mock.patch.object(main_main, "OpenRouterGateway") as gateway,
                mock.patch("sys.stderr", new_callable=io.StringIO),
            ):
                with self.assertRaises(SystemExit):
                    main_main.main(args)
                gateway.assert_not_called()


class LocalProfileTest(unittest.TestCase):
    def config(self):
        return {
            "design_model_fallback": ["deepseek/primary", "qwen/qwen3.8-flash"],
            "design_review_model_fallback": ["glm/reviewer", "qwen/qwen3.8-flash"],
            "review_enabled": True,
            "design_required": True,
            "design_max_tokens": None,
        }

    def test_opt_in_changes_only_local_model_order_and_deadline(self):
        config = self.config()
        original = copy.deepcopy(config)
        changed, deadline = local_settings(config, fast=True)
        self.assertEqual(deadline, 120)
        self.assertEqual(
            changed["design_model_fallback"],
            list(reversed(original["design_model_fallback"])),
        )
        self.assertEqual(config, original)
        for key in config.keys() - {"design_model_fallback"}:
            self.assertEqual(changed[key], config[key])
        unchanged, deadline = local_settings(config)
        self.assertEqual(unchanged, original)
        self.assertIsNone(deadline)
        changed, deadline = local_settings(
            config, fast=True, model="deepseek/primary", timeout=240
        )
        self.assertEqual(changed, original)
        self.assertEqual(deadline, 240)

    def test_unknown_model_or_nonpositive_deadline_is_rejected(self):
        for settings in ({"model": "unknown"}, {"timeout": 0}, {"timeout": -1}):
            with self.assertRaises(ValueError):
                local_settings(self.config(), **settings)

    def test_local_fast_cli_keeps_review_and_original_config(self):
        config = self.config()
        with (
            mock.patch.object(main_main, "load_dotenv"),
            mock.patch.object(main_main, "load_config", return_value=config),
            mock.patch.object(main_main, "OpenRouterGateway") as gateway,
            mock.patch.object(main_main, "JekyllPreviewPublisher"),
            mock.patch.object(main_main, "GeneratorPipeline") as pipeline,
        ):
            pipeline.return_value.run.return_value = 0
            self.assertEqual(
                main_main.main(["--local-preview", "fast-test", "--local-fast"]), 0
            )
            gateway.assert_called_once_with(first_content_timeout=120)
            used = pipeline.call_args.kwargs["cfg"]
            self.assertTrue(used["review_enabled"])
            self.assertTrue(used["design_required"])
            self.assertEqual(used["design_model_fallback"][0], "qwen/qwen3.8-flash")
            self.assertEqual(config, self.config())

    def test_design_only_preview_reuses_body_and_retains_review_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft, sources = root / "after.md", root / "source.xml"
            draft.write_text("제목: 확인 설명\n\n" + DESIGN_BODY)
            sources.write_text(DESIGN_SOURCES)
            with (
                mock.patch.object(preview_design, "load_dotenv"),
                mock.patch.object(
                    preview_design, "load_config", return_value=self.config()
                ),
                mock.patch.object(preview_design, "OpenRouterGateway") as gateway,
                mock.patch.object(preview_design, "ArticleDesignPipeline") as designer,
                mock.patch.object(
                    preview_design, "JekyllPreviewPublisher"
                ) as publisher,
            ):
                self.assertEqual(
                    preview_design.main(
                        [
                            "--draft",
                            str(draft),
                            "--sources",
                            str(sources),
                            "--name",
                            "fast-test",
                            "--local-fast",
                        ]
                    ),
                    0,
                )
                gateway.assert_called_once_with(first_content_timeout=120)
                args = designer.return_value.enhance.call_args.args
                self.assertEqual(args[0].body, DESIGN_BODY)
                self.assertEqual(args[1], DESIGN_SOURCES)
                self.assertTrue(args[2]["design_required"])
                publisher.return_value.publish.assert_called_once_with(
                    designer.return_value.enhance.return_value
                )


class PreviewContractTest(unittest.TestCase):
    def test_same_model_experiment_overrides_only_local_contract_and_provider(self):
        config = {
            "design_model_fallback": ["writer", "fallback"],
            "design_review_model_fallback": ["reviewer"],
            "design_generation_format": "compact",
            "design_provider_preferences": {"sort": "price"},
            "design_required": True,
        }
        original = deepcopy(config)
        with tempfile.TemporaryDirectory() as directory:
            draft, sources = (
                Path(directory) / "draft.md",
                Path(directory) / "source.xml",
            )
            draft.write_text("제목: 정책\n\n" + COMPACT_BODY, encoding="utf-8")
            sources.write_text(COMPACT_SOURCES, encoding="utf-8")
            with (
                mock.patch.object(preview_design, "load_dotenv"),
                mock.patch.object(preview_design, "load_config", return_value=config),
                mock.patch.object(preview_design, "OpenRouterGateway") as gateway,
                mock.patch.object(preview_design, "ArticleDesignPipeline") as pipeline,
                mock.patch.object(preview_design, "JekyllPreviewPublisher"),
            ):
                self.assertEqual(
                    preview_design.main(
                        [
                            "--draft",
                            str(draft),
                            "--sources",
                            str(sources),
                            "--name",
                            "contract-test",
                            "--generation-format",
                            "legacy",
                            "--provider-order",
                            "deepinfra/fp8",
                            "--provider-sort",
                            "latency",
                        ]
                    ),
                    0,
                )
                gateway.assert_called_once_with(
                    first_content_timeout=None,
                    provider_preferences={
                        "sort": "latency",
                        "order": ["deepinfra/fp8"],
                    },
                )
                used = pipeline.return_value.enhance.call_args.args[2]
                self.assertEqual(used["design_generation_format"], "legacy")
                self.assertEqual(
                    used["design_model_fallback"], config["design_model_fallback"]
                )
                self.assertEqual(
                    used["design_review_model_fallback"],
                    config["design_review_model_fallback"],
                )
                self.assertEqual(config, original)
