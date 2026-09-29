"""Opt-in Chromium checks for rendering, motion and accessibility."""

from __future__ import annotations

import html
import json
import math
import os
import unittest
from datetime import datetime, timedelta, timezone

from generator.design.design_browser import BrowserSceneVerifier
from generator.design.scene_document import render_document, validate_design
from generator.tests.fixtures.design import DESIGN_BODY, design_candidate
from generator.tests.fixtures.scenes import continuous_candidate


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1",
    "set DESIGN_BROWSER_TESTS=1 for Chromium integration",
)
class ContinuousRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.scene = validate_design(json.dumps(continuous_candidate()), DESIGN_BODY)[
            "scenes"
        ][0]
        self.document = render_document(self.scene)

    def load(self, *, reduced=False, width=700):
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        self.browser = BrowserSceneVerifier()._launch(self.playwright)
        self.addCleanup(self.playwright.stop)
        self.addCleanup(self.browser.close)
        self.context = self.browser.new_context(
            reduced_motion="reduce" if reduced else "no-preference",
            viewport={"width": width + 16, "height": 1100},
            service_workers="block",
        )
        self.addCleanup(self.context.close)
        self.requests = []
        self.errors = []
        self.context.route(
            "**/*",
            lambda route: (self.requests.append(route.request.url), route.abort()),
        )
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.page.clock.install(time=start)
        self.page.clock.pause_at(start + timedelta(seconds=1))
        self.page.set_default_timeout(2000)
        self.page.set_content(
            '<iframe id="scene" sandbox="allow-scripts" '
            'style="width:100%;height:950px;border:0" srcdoc="'
            + html.escape(self.document, quote=True)
            + '"></iframe>'
        )
        self.frame = self.page.frame_locator("#scene")
        self.content = self.frame.locator("#scene-content")
        self.content.locator("[data-entity]").first.wait_for()
        self.play = self.frame.locator("#scene-play")

    def reset(self):
        self.frame.locator("#scene-reset").click()

    def assert_state(self, sid, phase="settled"):
        self.assertEqual(self.content.get_attribute("data-state"), sid)
        self.assertEqual(self.content.get_attribute("data-phase"), phase)
        self.assertFalse(self.errors)
        self.assertFalse(self.requests)

    def point(self):
        return BrowserSceneVerifier._center(
            self.content.locator(".scene-transfer-token")
        )

    def test_production_gate_checks_real_motion_and_both_scenario_routes(self):
        report = BrowserSceneVerifier().check(self.scene, self.document)
        self.assertEqual(report["moving_steps_checked"], 10)
        self.assertEqual(report["scenario_routes_checked"], 4)

    def test_gate_rejects_stationary_or_invisible_transfer_tokens(self):
        # Inject defective rendering after validation to ensure the browser gate
        # catches a broken executor too, not just malformed model JSON.
        for css, message in (
            (
                ".scene-transfer-token {left:120px!important;top:60px!important}",
                "실제 전달 이동 없음",
            ),
            (".scene-transfer-token {opacity:0!important}", "숨겨지거나 잘려서"),
        ):
            document = self.document.replace("</style>", css + "</style>", 1)
            with self.subTest(css=css), self.assertRaisesRegex(ValueError, message):
                BrowserSceneVerifier().check(self.scene, document)

    def test_gate_rejects_overlapping_transfer_endpoints(self):
        scene = self.scene.copy()
        scene["css"] += (
            ".scene-content .node {position:absolute;left:50px;top:20px;width:80px}"
        )
        with self.assertRaisesRegex(ValueError, "출발·도착 위치가 겹쳐"):
            BrowserSceneVerifier().check(scene, render_document(scene))

    def long_label_document(self):
        label = "요청자의 메시지를 중계자가 받아 처리자에게 안전하게 전달합니다"
        self.assertLessEqual(len(label), 40)
        self.scene["transitions"][0]["steps"][0]["label"] = label
        # The fixture gives the wrapped token enough vertical room. Generated
        # layouts must independently pass the same ancestor clipping checks.
        self.scene["css"] += ".scene-content .board {padding:60px 0}"
        self.document = render_document(self.scene)

    def test_long_korean_label_wraps_inside_visible_mobile_token(self):
        self.long_label_document()
        self.load(width=320)
        self.reset()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(250)
        token = self.content.locator(".scene-transfer-token")
        measurements = token.evaluate("""el => {
          const range = document.createRange(); range.selectNodeContents(el);
          return {scrollWidth:el.scrollWidth, clientWidth:el.clientWidth,
            lines:range.getClientRects().length};
        }""")
        self.assertLessEqual(
            measurements["scrollWidth"], measurements["clientWidth"] + 1
        )
        self.assertGreater(measurements["lines"], 1)
        self.point()  # Includes actual glyph bounds as well as the token box.
        self.page.clock.run_for(1900)
        self.assert_state("delivered")

    def test_gate_rejects_overflowing_text_even_when_token_box_fits(self):
        self.long_label_document()
        document = self.document.replace(
            "</style>", ".scene-transfer-token {white-space:nowrap}</style>", 1
        )
        with self.assertRaisesRegex(ValueError, "숨겨지거나 잘려서"):
            BrowserSceneVerifier().check(self.scene, document)

    def test_result_changes_only_after_all_transfers_arrive(self):
        self.load(width=320)
        self.reset()
        self.content.locator('[data-entity="sender"]').evaluate(
            "el => { window.originalSender = el; }"
        )
        action = self.frame.locator('button[data-action="0"]')
        action.focus()
        action.press("Enter")
        self.assert_state("ready", "moving")
        self.page.clock.run_for(250)
        before = self.point()
        self.page.clock.run_for(400)
        self.assertGreater(math.dist(before, self.point()), 5)
        self.assert_state("ready", "moving")
        self.assertTrue(
            self.content.evaluate(
                "el => window.originalSender === el.querySelector('[data-entity=sender]')"
            )
        )
        self.page.clock.run_for(400)
        self.assert_state("ready", "moving")
        self.assertEqual(
            self.content.locator(".scene-transfer-token").get_attribute("data-source"),
            "relay",
        )
        self.page.clock.run_for(1050)
        self.assert_state("delivered")
        self.assertEqual(self.content.locator(".scene-transfer-token").count(), 0)

    def test_pause_and_resume_preserves_in_flight_progress(self):
        self.load()
        self.reset()
        self.play.click()
        self.page.clock.run_for(3350)
        self.assert_state("ready", "moving")
        self.play.click()
        before = self.point()
        self.page.clock.run_for(6000)
        self.assert_state("ready", "moving")
        self.assertLess(math.dist(before, self.point()), 0.5)
        self.play.click()
        self.page.clock.run_for(300)
        self.assertGreater(math.dist(before, self.point()), 2)
        self.assert_state("ready", "moving")
        self.page.clock.run_for(1400)
        self.assert_state("delivered")

    def test_reset_cancels_pending_transfer_and_late_result(self):
        self.load()
        self.reset()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(450)
        self.reset()
        self.assert_state("ready")
        self.assertEqual(self.content.locator(".scene-transfer-token").count(), 0)
        self.page.clock.run_for(12000)
        self.assert_state("ready")

    def test_previous_during_transfer_cancels_without_late_commit(self):
        self.load()
        self.reset()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(2100)
        self.assert_state("delivered")
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(250)
        previous = self.frame.locator("#scene-previous")
        previous.focus()
        previous.press("Enter")
        self.assert_state("delivered")
        self.page.clock.run_for(12000)
        self.assert_state("delivered")
        previous.click()
        self.assert_state("ready")

    def test_offscreen_suspends_and_visibility_resumes_same_transfer(self):
        self.load()
        self.reset()
        self.play.click()
        self.page.clock.run_for(3350)
        self.assert_state("ready", "moving")
        self.page.locator("#scene").evaluate("el => { el.style.marginTop = '2500px'; }")
        self.page.wait_for_function(
            "document.querySelector('#scene').getBoundingClientRect().top > innerHeight"
        )
        # IntersectionObserver is delivered by layout, independent of timer clock.
        from playwright.sync_api import expect

        expect(self.content).to_have_attribute("data-playback", "suspended")
        before = self.content.locator(".scene-transfer-token").evaluate(
            "el => [el.style.left, el.style.top, el.dataset.progress]"
        )
        self.page.clock.run_for(6000)
        self.assert_state("ready", "moving")
        self.assertEqual(
            self.content.locator(".scene-transfer-token").evaluate(
                "el => [el.style.left, el.style.top, el.dataset.progress]"
            ),
            before,
        )
        self.page.locator("#scene").evaluate("el => { el.style.marginTop = '0px'; }")
        expect(self.content).not_to_have_attribute("data-playback", "suspended")
        self.page.clock.run_for(1750)
        self.assert_state("delivered")

    def test_resize_during_transfer_keeps_progress_and_mobile_bounds(self):
        self.load()
        self.reset()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(350)
        token = self.content.locator(".scene-transfer-token")
        progress = float(token.get_attribute("data-progress"))
        self.page.set_viewport_size({"width": 336, "height": 1100})
        self.page.clock.run_for(32)
        self.assert_state("ready", "moving")
        self.assertGreaterEqual(float(token.get_attribute("data-progress")), progress)
        self.point()  # Includes the same visibility and clipping checks as production.
        self.page.clock.run_for(1750)
        self.assert_state("delivered")
        self.assertFalse(
            self.content.evaluate(
                "el => document.documentElement.scrollWidth > innerWidth + 1"
            )
        )

    def test_scenario_switch_during_motion_cancels_previous_route(self):
        self.load()
        self.reset()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(350)
        selector = self.frame.locator(
            '#scene-scenarios button[data-scenario="disconnect"]'
        )
        selector.focus()
        selector.press("Enter")
        self.assert_state("ready")
        self.assertEqual(selector.get_attribute("aria-pressed"), "true")
        self.page.clock.run_for(8000)
        self.assert_state("ready")
        self.play.click()
        self.page.clock.run_for(4100)
        self.assert_state("lost")
        self.page.clock.run_for(4100)
        self.assert_state("returned")
        self.assertEqual(self.play.get_attribute("aria-pressed"), "false")

    def test_reduced_motion_has_no_autostart_and_same_terminal_result(self):
        self.load(reduced=True, width=320)
        self.page.clock.run_for(15000)
        self.assert_state("ready")
        self.assertEqual(self.play.get_attribute("aria-pressed"), "false")
        self.frame.locator('button[data-action="0"]').click()
        self.assert_state("delivered")
        self.assertEqual(self.content.locator(".scene-transfer-token").count(), 0)
        self.reset()
        self.play.click()
        self.page.clock.run_for(6000)
        self.assert_state("confirmed")
        self.assertEqual(self.play.get_attribute("aria-pressed"), "false")


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1", "set DESIGN_BROWSER_TESTS=1"
)
class SceneRuntimeBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        cls.browser = BrowserSceneVerifier()._launch(cls.playwright)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 700, "height": 700})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.page.clock.install(time=now)
        self.page.clock.pause_at(now + timedelta(seconds=1))
        value = design_candidate()
        self.scene = value["scenes"][0]
        self.scene["playback"]["steps"] = ["start", "confirmed"]
        self.scene["css"] += ".scene-content .board {min-height:100px}"

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def load(self, reduced=False):
        self.page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
        self.page.set_content(render_document(self.scene))
        self.page.locator("#scene-content[data-state]").wait_for()
        self.page.clock.run_for(100)

    def state(self):
        return self.page.locator("#scene-content").get_attribute("data-state")

    def scroll(self, away):
        from playwright.sync_api import expect

        self.page.evaluate(
            "away => { if (!document.getElementById('spacer')) {const spacer = document.createElement('div'); spacer.id='spacer'; spacer.style.height='2000px'; document.body.append(spacer);} window.scrollTo(0, away ? 1700 : 0); }",
            away,
        )
        self.page.clock.run_for(100)
        if self.page.locator("#scene-play").get_attribute("aria-pressed") == "true":
            expect(self.page.locator("#scene-content")).to_have_attribute(
                "data-playback", "suspended" if away else "playing"
            )

    def test_offscreen_pause_resumes_then_stays_completed_and_replays(self):
        self.load()
        self.assertEqual(
            self.page.locator("#scene-play").get_attribute("aria-pressed"), "true"
        )
        self.page.clock.run_for(500)
        self.scroll(True)
        self.page.clock.run_for(10000)
        self.assertEqual(self.state(), "start")
        self.scroll(False)
        self.page.clock.run_for(3000)
        self.assertEqual(self.state(), "confirmed")
        self.assertEqual(self.page.locator("#scene-play").inner_text(), "다시 재생")
        self.scroll(True)
        self.scroll(False)
        self.page.clock.run_for(10000)
        self.assertEqual(self.state(), "confirmed")
        self.page.locator("#scene-play").click()
        self.assertEqual(self.state(), "start")
        self.page.clock.run_for(3000)
        self.assertEqual(self.state(), "confirmed")

    def test_manual_pause_and_reset_do_not_autoresume(self):
        self.load()
        self.page.locator("#scene-play").click()
        self.scroll(True)
        self.scroll(False)
        self.page.clock.run_for(10000)
        self.assertEqual(self.state(), "start")
        self.assertEqual(
            self.page.locator("#scene-play").get_attribute("aria-pressed"), "false"
        )
        self.page.locator("#scene-play").click()
        self.page.locator("#scene-reset").click()
        self.scroll(True)
        self.scroll(False)
        self.page.clock.run_for(10000)
        self.assertEqual(self.state(), "start")

    def test_hidden_document_suspends_and_restores_playback_intent(self):
        self.load()
        # Exercise visibility handler deterministically; headless has no user tabs.
        self.page.evaluate(
            "Object.defineProperty(document, 'hidden', {configurable:true, value:true}); document.dispatchEvent(new Event('visibilitychange'))"
        )
        self.page.clock.run_for(10000)
        self.assertEqual(self.state(), "start")
        self.page.evaluate(
            "Object.defineProperty(document, 'hidden', {configurable:true, value:false}); document.dispatchEvent(new Event('visibilitychange'))"
        )
        self.page.clock.run_for(3000)
        self.assertEqual(self.state(), "confirmed")

    def test_reduced_motion_disables_auto_but_allows_explicit_play(self):
        self.load(reduced=True)
        self.page.clock.run_for(10000)
        self.assertEqual(self.state(), "start")
        self.page.locator("#scene-play").click()
        self.page.clock.run_for(3000)
        self.assertEqual(self.state(), "confirmed")
        self.assertEqual(self.page.evaluate("document.getAnimations().length"), 0)

    def test_preference_change_stops_active_play_and_animation(self):
        from playwright.sync_api import expect

        self.load()
        self.page.emulate_media(reduced_motion="reduce")
        expect(self.page.locator("#scene-play")).to_have_attribute(
            "aria-pressed", "false"
        )
        self.page.clock.run_for(10000)
        self.assertEqual(self.state(), "start")
        self.assertEqual(self.page.evaluate("document.getAnimations().length"), 0)

    def test_entity_moves_without_animating_whole_scene(self):
        self.scene["css"] += (
            ".scene-content .board {display:flex;justify-content:flex-start}.scene-content .end {justify-content:flex-end}"
        )
        self.scene["states"][1]["html"] = self.scene["states"][0]["html"].replace(
            'class="board"', 'class="board end"'
        )
        self.load()
        self.page.clock.run_for(3000)
        animations = self.page.evaluate(
            "document.getAnimations().map(a => ({entity:a.effect.target.dataset.entity, frames:a.effect.getKeyframes()}))"
        )
        self.assertEqual(len(animations), 1)
        self.assertEqual(animations[0]["entity"], "broker")
        self.assertIn("translate", animations[0]["frames"][0])
        self.assertNotEqual(animations[0]["frames"][0]["translate"], "0px")

    def test_changed_label_is_highlighted(self):
        self.load()
        self.page.clock.run_for(3000)
        self.assertEqual(
            self.page.evaluate(
                "document.getAnimations().map(a => a.effect.target.dataset.entity)"
            ),
            ["broker"],
        )


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1", "set DESIGN_BROWSER_TESTS=1"
)
class PixelGateBrowserTest(unittest.TestCase):
    @staticmethod
    def static_scene(height, extra_css=""):
        scene = design_candidate()["scenes"][0]
        scene["states"] = scene["states"][:1]
        scene["states"][0]["actions"] = []
        scene["playback"]["steps"] = []
        # Fixture-only body height, independent of any model's chosen layout.
        document = render_document(scene).replace(
            "</style>", f"body{{min-height:{height}px}}{extra_css}</style>", 1
        )
        return scene, document

    def test_small_vertical_excess_is_reported_not_rejected(self):
        for height in (950, 951, 1050):
            with self.subTest(height=height):
                report = BrowserSceneVerifier().check(*self.static_scene(height))
                self.assertEqual(len(report["warnings"]), 0 if height == 950 else 2)
                self.assertTrue(
                    all(w["height_px"] == height for w in report["warnings"])
                )
        with self.assertRaisesRegex(ValueError, "1051px"):
            BrowserSceneVerifier().check(*self.static_scene(1051))

    def test_tolerance_never_allows_overflow_clipping_hidden_or_tiny_text(self):
        for css in (
            ".scene-content{width:1400px}",
            ".scene-content{min-height:0;max-height:5px;overflow:hidden}",
            ".scene-content{visibility:hidden}",
            ".scene-content *{font-size:5px}",
        ):
            with (
                self.subTest(css=css),
                self.assertRaisesRegex(ValueError, "화면 검사 실패"),
            ):
                BrowserSceneVerifier().check(*self.static_scene(972, css))

    def test_browser_gate_rejects_different_markup_with_identical_pixels(self):
        value = design_candidate()
        scene = value["scenes"][0]
        scene["states"][1]["html"] = scene["states"][0]["html"].replace(
            'class="board"', 'class="board unused"'
        )
        scene = validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]
        with self.assertRaisesRegex(ValueError, "화면에 변화가 없음"):
            BrowserSceneVerifier().check(scene, render_document(scene))
