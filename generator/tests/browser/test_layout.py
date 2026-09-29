"""Opt-in Chromium checks for rendering, motion and accessibility."""

from __future__ import annotations

import copy
import html
import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from jsonschema import Draft202012Validator

from generator.design.compact_scenes import compile_compact_design
from generator.design.design_browser import BrowserSceneVerifier
from generator.design.layout_diagnostics import (
    LAYOUT_DIAGNOSTIC_SCHEMA,
    BrowserLayoutError,
)
from generator.design.prompt_examples import numeric_example
from generator.design.scene_document import render_document, validate_design
from generator.tests.fixtures.design import DESIGN_BODY
from generator.tests.fixtures.scenes import (
    clarity_scene,
    compact_panels_scene,
    continuous_candidate,
    multi_change_scene,
)


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1", "set DESIGN_BROWSER_TESTS=1"
)
class BrowserLayoutDiagnosticTest(unittest.TestCase):
    @contextmanager
    def panel_frame(self, scene, css=""):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = BrowserSceneVerifier()._launch(playwright)
            try:
                page = browser.new_page(
                    viewport={"width": 336, "height": 1200}, reduced_motion="reduce"
                )
                page.set_default_timeout(2000)
                document = render_document(scene).replace(
                    "</style>", css + "</style>", 1
                )
                page.set_content(
                    '<iframe id="test" sandbox="allow-scripts" style="width:100%;height:1100px;border:0" srcdoc="'
                    + html.escape(document, quote=True)
                    + '"></iframe>'
                )
                frame = page.frame_locator("#test")
                frame.locator('button[data-action="0"]').click()
                yield frame
            finally:
                browser.close()

    def check_fails(self, scene, css):
        document = render_document(scene).replace("</style>", css + "</style>", 1)
        with self.assertRaises(BrowserLayoutError) as result:
            BrowserSceneVerifier().check(scene, document)
        for observation in result.exception.layout_diagnostics:
            Draft202012Validator(LAYOUT_DIAGNOSTIC_SCHEMA).validate(observation)
        return result.exception

    def test_all_widths_and_states_report_height_and_region_ownership(self):
        scene = clarity_scene()
        before = copy.deepcopy(scene)
        error = self.check_fails(scene, "body{min-height:1169px}")
        self.assertEqual(scene, before)
        observations = error.layout_diagnostics
        self.assertEqual(
            {(item["width_px"], item["state"]) for item in observations},
            {(width, state["id"]) for width in (320, 700) for state in scene["states"]},
        )
        for item in observations:
            self.assertEqual(item["phase"], "settled")
            self.assertEqual(item["document_height_px"], 1169)
            self.assertEqual(item["height_limit_px"], 1050)
            self.assertEqual(item["excess_height_px"], 119)
            regions = {region["name"]: region for region in item["regions"]}
            self.assertEqual(regions["canvas"]["owner"], "model")
            self.assertEqual(regions["change_summary"]["owner"], "renderer")
            self.assertEqual(regions["caption"]["owner"], "renderer")
            self.assertGreater(regions["canvas"]["height_px"], 0)

    def test_tiny_fields_include_actual_font_entity_and_bounded_count(self):
        scene = clarity_scene()
        for state in scene["states"]:
            state["html"] += (
                '<div class="tiny-fields">'
                + "".join(f"<span>tiny field {index}</span> " for index in range(12))
                + "</div>"
            )
        error = self.check_fails(
            scene,
            ".scene-content .tiny-fields span{font-size:11px}.scene-content [data-entity]{font-size:11px}",
        )
        for item in error.layout_diagnostics:
            self.assertIn("tiny", item["violations"])
            self.assertEqual(len(item["problem_elements"]), 8)
            self.assertGreaterEqual(item["tiny_text_count"], 14)
            self.assertTrue(item["problems_truncated"])
            self.assertTrue(
                all(
                    problem["font_size_px"] == 11
                    for problem in item["problem_elements"]
                )
            )
            self.assertTrue(
                any(
                    problem["entity"] == "namespace"
                    for problem in item["problem_elements"]
                )
            )
            self.assertTrue(
                all(problem["owner"] == "model" for problem in item["problem_elements"])
            )

    def test_moving_failure_has_exact_phase_without_loosening_height(self):
        error = self.check_fails(
            clarity_scene(), '.scene-content[data-phase="moving"]{min-height:1100px}'
        )
        item = error.layout_diagnostics[0]
        self.assertEqual(item["phase"], "moving")
        self.assertEqual(item["state"], "ready")
        self.assertEqual(item["width_px"], 320)
        self.assertGreater(item["document_height_px"], 1050)

    def test_description_expansion_keeps_limit_and_identifies_renderer_height(self):
        error = self.check_fails(
            clarity_scene(),
            'body:has(#scene-content[data-state="team"]) #scene-extra-details[open] #scene-status{min-height:1100px}',
        )
        item = error.layout_diagnostics[0]
        self.assertEqual(item["phase"], "expanded-description")
        region = next(
            region for region in item["regions"] if region["name"] == "description"
        )
        self.assertEqual(region["owner"], "renderer")
        self.assertGreater(region["height_px"], 1100)

    def test_secondary_changes_are_checked_after_keyboard_expansion(self):
        scene = multi_change_scene()
        for edge in scene["change_explanations"]:
            state = next(
                state for state in scene["states"] if state["id"] == edge["to"]
            )
            state["description"] = edge["reason"]
        error = self.check_fails(
            scene, ".scene-change-details[open]{min-height:1100px}"
        )
        item = error.layout_diagnostics[0]
        self.assertEqual(item["phase"], "expanded-changes")
        self.assertEqual(item["height_limit_px"], 1050)
        self.assertGreater(item["document_height_px"], 1050)

    def test_numeric_table_expansion_is_checked_and_owned_by_renderer(self):
        example = numeric_example()
        scene = compile_compact_design(
            example["output"],
            example["input"]["headings"],
            example["input"]["source_excerpts"],
        )["scenes"][0]
        error = self.check_fails(scene, ".scene-chart-details[open]{min-height:1100px}")
        self.assertTrue(error.layout_diagnostics)
        for item in error.layout_diagnostics:
            self.assertEqual(item["phase"], "expanded-chart")
            region = next(
                region for region in item["regions"] if region["name"] == "chart"
            )
            self.assertEqual(region["owner"], "renderer")
            self.assertGreater(region["height_px"], 1100)

    def test_individual_panels_fit_but_combined_expansion_is_held(self):
        scene = compact_panels_scene()
        css = "#scene-extra-details[open] #scene-status{min-height:130px}"
        with self.panel_frame(scene, css) as frame:
            for selector in (".scene-change-details", "#scene-extra-details"):
                details = frame.locator(selector)
                summary = details.locator(":scope > summary")
                summary.press("Enter")
                self.assertLessEqual(
                    frame.locator("body").evaluate("body => body.scrollHeight"), 1050
                )
                summary.press("Enter")
            with self.assertRaises(BrowserLayoutError) as result:
                BrowserSceneVerifier._check_expanded_panels(frame, "team", 320, [])
            self.assertEqual(
                result.exception.layout_diagnostics[0]["phase"], "expanded-all"
            )
            self.assertGreater(
                result.exception.layout_diagnostics[0]["document_height_px"], 1050
            )
            self.assertEqual(frame.locator("details[open]").count(), 0)
        error = self.check_fails(scene, css)
        self.assertEqual(error.layout_diagnostics[0]["phase"], "expanded-all")

    def test_combined_expansion_passes_and_restores_mixed_original_open_states(self):
        scene = compact_panels_scene()
        with self.panel_frame(scene) as frame:
            ledger = frame.locator(".scene-change-details")
            description = frame.locator("#scene-extra-details")
            for originally_open in (False, True):
                if originally_open:
                    ledger.locator(":scope > summary").press("Enter")
                warnings = []
                self.assertEqual(
                    BrowserSceneVerifier._check_expanded_panels(
                        frame, "team", 320, warnings
                    ),
                    1,
                )
                self.assertEqual(
                    ledger.get_attribute("open") is not None, originally_open
                )
                self.assertIsNone(description.get_attribute("open"))
                self.assertTrue(
                    any(item["phase"] == "expanded-all" for item in warnings)
                )
        report = BrowserSceneVerifier().check(scene, render_document(scene))
        self.assertEqual(report["change_explanations_checked"], 4)

    def test_combined_expansion_rejects_unreadable_values_and_restores_panels(self):
        with self.panel_frame(
            compact_panels_scene(),
            ".scene-change-details[open] .scene-change-after{color:transparent}",
        ) as frame:
            with self.assertRaises(BrowserLayoutError) as result:
                BrowserSceneVerifier._check_expanded_panels(frame, "team", 320, [])
            observation = result.exception.layout_diagnostics[0]
            self.assertEqual(observation["phase"], "expanded-all")
            self.assertIn("hidden", observation["violations"])
            self.assertEqual(frame.locator("details[open]").count(), 0)

    def test_strict_diagnostic_schema_rejects_unexpected_fields(self):
        item = self.check_fails(
            clarity_scene(), "body{min-height:1169px}"
        ).layout_diagnostics[0]
        item["execute_css"] = "body{font-size:1px}"
        self.assertFalse(Draft202012Validator(LAYOUT_DIAGNOSTIC_SCHEMA).is_valid(item))


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1", "set DESIGN_BROWSER_TESTS=1"
)
class SceneMobileFocusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        cls.browser = BrowserSceneVerifier()._launch(cls.playwright)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def load(self, height=700):
        self.context = self.browser.new_context(
            viewport={"width": 390, "height": height},
            reduced_motion="no-preference",
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(self.errors, []))
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.page.clock.install(time=start)
        self.page.clock.pause_at(start + timedelta(seconds=1))
        value = continuous_candidate()
        value["scenes"][0]["css"] += (
            ".scene-content .board {min-height:460px;align-content:space-between}"
        )
        scene = validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]
        self.page.set_content(
            '<div style="height:600px">글의 앞부분</div>'
            '<iframe id="scene" sandbox="allow-scripts" '
            'style="display:block;width:100%;height:864px;border:0" srcdoc="'
            + html.escape(render_document(scene), quote=True)
            + '"></iframe><div style="height:1200px">글의 뒷부분</div>'
        )
        self.frame = self.page.frame_locator("#scene")
        self.content = self.frame.locator("#scene-content")
        self.play = self.frame.locator("#scene-play")
        self.content.wait_for(state="attached")
        self.content.evaluate(
            """() => {
                window.stageRevealCalls = 0;
                const original = Element.prototype.scrollIntoView;
                Element.prototype.scrollIntoView = function(...args) {
                    if (this.id === 'scene-content') window.stageRevealCalls++;
                    return original.apply(this, args);
                };
            }"""
        )
        self.advance(100)
        self.assertLessEqual(
            self.content.evaluate("() => document.body.scrollHeight"), 900
        )

    def advance(self, duration):
        self.page.clock.run_for(duration)
        # IntersectionObserver delivery uses browser rendering, not a timer.
        self.page.wait_for_timeout(30)

    def ratio(self):
        rect = self.content.bounding_box()
        height = self.page.viewport_size["height"]
        return (
            max(0, min(height, rect["y"] + rect["height"]) - max(0, rect["y"]))
            / rect["height"]
        )

    def reset_below_stage(self):
        self.frame.locator("#scene-reset").click()
        self.advance(100)
        self.assertLess(self.ratio(), 0.5)

    def reveal_calls(self):
        return self.content.evaluate("() => window.stageRevealCalls")

    def progress(self):
        return float(
            self.content.locator(".scene-transfer-token").get_attribute("data-progress")
        )

    def test_explicit_play_reveals_valid_stage_in_short_mobile_viewports(self):
        for height in (700, 844):
            with self.subTest(height=height):
                self.load(height)
                self.reset_below_stage()
                self.assertEqual(self.reveal_calls(), 0)
                self.play.click()
                self.advance(100)
                self.assertGreaterEqual(self.ratio(), 0.5)
                self.assertEqual(self.play.get_attribute("aria-pressed"), "true")
                self.assertEqual(self.content.get_attribute("data-playback"), "playing")
                self.advance(3300)
                self.assertEqual(self.content.get_attribute("data-phase"), "moving")
                self.assertGreater(self.progress(), 0)
                self.assertGreater(self.reveal_calls(), 0)

    def test_manual_action_and_resume_reveal_the_same_in_flight_stage(self):
        self.load()
        self.reset_below_stage()
        self.frame.locator('button[data-action="0"]').click()
        self.advance(100)
        self.advance(350)
        self.assertGreaterEqual(self.ratio(), 0.5)
        self.assertEqual(self.content.get_attribute("data-phase"), "moving")
        self.assertGreater(self.progress(), 0)
        self.play.click()
        frozen = self.progress()
        self.advance(5000)
        self.assertEqual(self.progress(), frozen)
        self.play.click()
        self.advance(100)
        self.advance(300)
        self.assertGreaterEqual(self.ratio(), 0.5)
        self.assertGreater(self.progress(), frozen)
        self.assertEqual(self.content.get_attribute("data-state"), "ready")

    def test_offscreen_automatic_playback_never_scrolls_the_article(self):
        self.load()
        self.advance(4000)
        self.assertEqual(self.page.evaluate("scrollY"), 0)
        self.assertEqual(self.reveal_calls(), 0)
        # Simulate the reader scrolling the article until its stage is visible.
        self.page.evaluate("window.scrollTo(0, 638)")
        self.advance(100)
        self.advance(3300)
        self.assertEqual(self.content.get_attribute("data-phase"), "moving")
        self.assertEqual(self.reveal_calls(), 0)
        self.page.evaluate("window.scrollTo(0, 0)")
        self.advance(100)
        frozen = self.progress()
        self.advance(10000)
        self.assertEqual(self.content.get_attribute("data-playback"), "suspended")
        self.assertEqual(self.progress(), frozen)
        self.assertEqual(self.page.evaluate("scrollY"), 0)
        self.assertEqual(self.reveal_calls(), 0)

    def test_visible_majority_of_stage_is_not_forced_back_to_center(self):
        self.load()
        self.frame.locator("#scene-reset").click()
        rect = self.content.bounding_box()
        absolute_top = rect["y"] + self.page.evaluate("scrollY")
        self.page.evaluate("top => scrollTo(0, top - 300)", absolute_top)
        self.advance(100)
        self.assertGreaterEqual(self.ratio(), 0.5)
        self.assertLess(self.ratio(), 0.98)
        before = self.page.evaluate("scrollY")
        # Dispatch without Playwright's own automatic scroll-to-button behavior.
        self.frame.locator('button[data-action="0"]').evaluate(
            "button => button.click()"
        )
        self.advance(100)
        self.assertEqual(self.reveal_calls(), 0)
        self.assertEqual(self.page.evaluate("scrollY"), before)

    def test_reset_and_scenario_selection_do_not_request_stage_scroll(self):
        self.load()
        self.reset_below_stage()
        self.assertEqual(self.reveal_calls(), 0)
        self.frame.locator('button[data-scenario="disconnect"]').click()
        self.advance(5000)
        self.assertEqual(self.reveal_calls(), 0)
        self.assertEqual(self.content.get_attribute("data-state"), "ready")
        self.assertEqual(self.play.get_attribute("aria-pressed"), "false")

    def test_play_intent_is_visible_even_when_hidden_document_cannot_start(self):
        self.load()
        self.reset_below_stage()
        self.content.evaluate(
            """() => {
                Object.defineProperty(document, 'hidden', {value:true, configurable:true});
                document.dispatchEvent(new Event('visibilitychange'));
            }"""
        )
        self.play.click()
        self.assertEqual(self.play.get_attribute("aria-pressed"), "true")
        self.assertEqual(self.content.get_attribute("data-playback"), "suspended")
        self.assertEqual(self.reveal_calls(), 0)
