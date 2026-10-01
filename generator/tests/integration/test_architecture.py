"""Pipeline, persistence and local-tool integration; model calls are mocked."""

from __future__ import annotations

import ast
import importlib.util as importlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import generator.providers.openrouter as llm
import generator.publishing.jekyll as publishing
import generator.sources.source_context as source_context
import generator.sources.topics as topic_module
from generator.contracts import (
    LanguageModelGateway,
    Publisher,
    SourceGateway,
    TextCompletionGateway,
    TopicRepository,
)
from generator.paths import (
    ASSETS_DIR,
    GENERATOR_DIR,
    PROJECT_ROOT,
    PROMPTS_DIR,
    STATE_DIR,
)


class PackageStructureTest(unittest.TestCase):
    def test_production_never_imports_examples_or_tests(self):
        failures = []
        for path in GENERATOR_DIR.rglob("*.py"):
            relative = path.relative_to(GENERATOR_DIR)
            if relative.parts[0] in {"examples", "tests", ".venv"}:
                continue
            package = "generator." + ".".join(relative.parts[:-1])
            package = package.rstrip(".")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.level:
                        module = importlib.util.resolve_name(
                            "." * node.level + module, package
                        )
                    names = [module] + [
                        module + "." + alias.name for alias in node.names
                    ]
                for name in names:
                    if any(
                        name == prefix or name.startswith(prefix + ".")
                        for prefix in ("generator.examples", "generator.tests")
                    ):
                        failures.append(f"{relative}:{node.lineno}: {name}")
        self.assertEqual(failures, [])

    def test_entrypoint_imports_without_example_packages(self):
        script = """
import importlib.abc
import sys
class NoExamples(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("generator.examples", "generator.tests")):
            raise AssertionError("Production tried to import " + fullname)
sys.meta_path.insert(0, NoExamples())
from generator.main import main
main(["--help"])
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--local-preview", result.stdout)
        self.assertNotIn("--motion-source-dir", result.stdout)
        self.assertNotIn("--preview-name", result.stdout)

    def test_old_script_entrypoint_works_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(GENERATOR_DIR / "main.py"), "--help"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--local-preview", result.stdout)

    def test_rooted_resources_keep_existing_locations(self):
        from generator.design import scene_document
        from generator.publishing import post_writer
        from generator.sources import dedup, difficulty
        from generator.tools import local_preview

        self.assertEqual(scene_document.HERE, GENERATOR_DIR)
        self.assertEqual(post_writer.OUT_DIR, PROJECT_ROOT / "_posts/ai-notes")
        self.assertEqual(post_writer.ASSETS_DIR, ASSETS_DIR / "diagrams")
        self.assertEqual(dedup.STATE_FILE, STATE_DIR / "topics_done.json")
        self.assertEqual(difficulty.CACHE_FILE, STATE_DIR / "difficulty.json")
        self.assertEqual(local_preview.ASSETS, ASSETS_DIR)
        self.assertTrue((PROMPTS_DIR / "designer_compact.md").is_file())
        self.assertTrue((ASSETS_DIR / "js/scene-runtime.js").is_file())

    def test_production_schema_has_no_rabbitmq_contract(self):
        from generator.design import visual_contracts

        self.assertFalse(hasattr(visual_contracts, "MOTION_SCHEMA"))
        self.assertFalse((PROMPTS_DIR / "motion_writer.md").exists())
        self.assertFalse((PROMPTS_DIR / "motion_reviewer.md").exists())

    def test_prompt_examples_are_production_resources(self):
        from generator.design import design_inputs, prompt_examples

        self.assertIs(design_inputs.select_examples, prompt_examples.select_examples)


class ArchitectureContractTest(unittest.TestCase):
    def test_current_adapters_implement_protocols(self) -> None:
        self.assertIsInstance(llm.OpenRouterGateway(), LanguageModelGateway)
        self.assertIsInstance(llm.OpenRouterGateway(), TextCompletionGateway)
        self.assertIsInstance(publishing.JekyllPublisher(), Publisher)
        self.assertIsInstance(
            source_context.OfficialDocumentSourceGateway(),
            SourceGateway,
        )
        self.assertIsInstance(
            topic_module.CatalogTopicRepository(),
            TopicRepository,
        )

    def test_scoring_and_selection_do_not_import_provider_or_authentication(self):
        for name in ("difficulty", "topics"):
            tree = ast.parse((GENERATOR_DIR / "sources" / f"{name}.py").read_text())
            modules = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    modules.append(node.module or "")
            self.assertFalse(
                any(
                    module in {"os", "requests"}
                    or module.startswith("generator.providers")
                    for module in modules
                )
            )


class BrowserLifecycleTest(unittest.TestCase):
    def test_scene_context_is_closed_on_setup_failure_and_validation_failure(self):
        from generator.design.design_browser import BrowserSceneVerifier

        for failure in ("setup", "validation", None):
            with self.subTest(failure=failure):
                browser = mock.Mock()
                context = browser.new_context.return_value
                page = context.new_page.return_value
                if failure == "setup":
                    page.set_content.side_effect = ValueError("setup")

                def check():
                    with BrowserSceneVerifier._scene_page(
                        browser, "<main>scene</main>", [], [], reduced_motion="reduce"
                    ) as (actual_page, _):
                        self.assertIs(actual_page, page)
                        if failure == "validation":
                            raise ValueError("validation")

                if failure:
                    with self.assertRaisesRegex(ValueError, failure):
                        check()
                else:
                    check()
                context.close.assert_called_once()
                browser.new_context.assert_called_once_with(
                    reduced_motion="reduce", service_workers="block"
                )
                page.set_default_timeout.assert_called_once_with(2000)
                page.clock.install.assert_called_once()
                page.clock.pause_at.assert_called_once()
                route = mock.Mock()
                context.route.call_args.args[1](route)
                route.abort.assert_called_once()
