"""Opt-in Chromium checks for rendering, motion and accessibility."""

from __future__ import annotations

import html
import json
import os
import unittest
from datetime import datetime, timedelta, timezone

from generator.design.design_browser import BrowserSceneVerifier
from generator.design.scene_document import render_document, validate_design
from generator.paths import PROJECT_ROOT
from generator.tests.fixtures.design import DESIGN_BODY, design_candidate
from generator.tests.fixtures.scenes import (
    MOTION_BODY,
    diagram_candidate,
    effect_scene,
)


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1",
    "set DESIGN_BROWSER_TESTS=1 for Chromium integration",
)
class DesignBrowserTest(unittest.TestCase):
    def test_playback_path_is_checked_by_the_normal_browser_gate(self):
        value = design_candidate()
        value["scenes"][0]["playback"]["steps"] = ["start", "confirmed"]
        scene = validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]
        result = BrowserSceneVerifier().check(scene, render_document(scene))
        self.assertEqual(result["playback_steps"], 2)

    def test_autoplay_pause_end_and_reduced_motion(self):
        from playwright.sync_api import expect, sync_playwright

        value = design_candidate()
        value["scenes"][0]["playback"]["steps"] = ["start", "confirmed"]
        scene = validate_design(json.dumps(value), DESIGN_BODY)["scenes"][0]
        document = render_document(scene)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for reduced in (False, True):
                    context = browser.new_context(
                        reduced_motion="reduce" if reduced else "no-preference"
                    )
                    page = context.new_page()
                    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
                    page.clock.install(time=start)
                    page.clock.pause_at(start + timedelta(seconds=1))
                    page.set_content(
                        '<iframe id="scene" sandbox="allow-scripts" style="width:700px;height:900px" srcdoc="'
                        + html.escape(document, quote=True)
                        + '"></iframe>'
                    )
                    frame = page.frame_locator("#scene")
                    play = frame.locator("#scene-play")
                    expect(play).to_have_attribute(
                        "aria-pressed", "false" if reduced else "true"
                    )
                    if not reduced:
                        play.click()  # Pause the automatically started route.
                    page.clock.run_for(6000)
                    expect(frame.locator("#scene-content")).to_have_attribute(
                        "data-state", "start"
                    )
                    play.click()  # Explicit playback is available even with reduced motion.
                    page.clock.run_for(3000)
                    expect(frame.locator("#scene-content")).to_have_attribute(
                        "data-state", "confirmed"
                    )
                    expect(play).to_have_attribute("aria-pressed", "false")
                    page.clock.run_for(9000)
                    expect(frame.locator("#scene-content")).to_have_attribute(
                        "data-state", "confirmed"
                    )
                    context.close()
            finally:
                browser.close()

    def test_real_sandbox_and_all_transitions(self):
        scene = validate_design(json.dumps(design_candidate()), DESIGN_BODY)["scenes"][
            0
        ]
        verifier = BrowserSceneVerifier()
        verifier.preflight()
        result = verifier.check(scene, render_document(scene))
        self.assertEqual(result["transitions_checked"], 2)

    def test_overflow_is_rejected(self):
        scene = design_candidate()["scenes"][0]
        scene["css"] = ".scene-content {width:1400px}"
        with self.assertRaises(ValueError):
            BrowserSceneVerifier().check(scene, render_document(scene))

    def test_hidden_or_clipped_text_is_rejected(self):
        for css in (
            ".scene-content p {display:none}",
            ".scene-content p {opacity:0}",
            ".scene-content {height:40px}.scene-content .board {height:300px}",
        ):
            scene = design_candidate()["scenes"][0]
            scene["css"] = css
            with self.subTest(css=css), self.assertRaises(ValueError):
                BrowserSceneVerifier().check(scene, render_document(scene))


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1", "set DESIGN_BROWSER_TESTS=1"
)
class DiagramBrowserTest(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={"width": 698, "height": 1100})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.page.clock.install(time=now)
        self.page.clock.pause_at(now + timedelta(seconds=1))

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def load(self, layout="branch"):
        self.page.emulate_media(reduced_motion="reduce")
        self.page.set_content(render_document(diagram_candidate(layout)["scenes"][0]))
        self.page.locator(".diagram-symbol svg").first.wait_for()
        self.page.clock.run_for(100)

    def test_real_698px_article_uses_branch_not_stacked_cards(self):
        self.load()
        boxes = self.page.locator(".diagram-symbol").evaluate_all(
            "els => els.map(e => {const r=e.getBoundingClientRect();return {x:r.x,y:r.y}})"
        )
        self.assertLess(boxes[0]["x"], boxes[1]["x"])
        self.assertLess(boxes[1]["x"], boxes[2]["x"])
        self.assertAlmostEqual(boxes[0]["y"], boxes[1]["y"], delta=1)
        self.assertLess(boxes[2]["y"], boxes[3]["y"])
        self.assertEqual(self.page.locator(".diagram-link").count(), 3)
        self.assertLess(
            self.page.locator("#scene-play").bounding_box()["y"], boxes[0]["y"]
        )

    def test_mobile_branch_remains_two_rows_with_all_labels(self):
        self.page.set_viewport_size({"width": 320, "height": 1100})
        self.load()
        self.assertLessEqual(self.page.evaluate("document.body.scrollHeight"), 950)
        self.assertLessEqual(self.page.evaluate("document.body.scrollWidth"), 320)
        boxes = self.page.locator(".diagram-symbol").evaluate_all(
            "els => els.map(e => {const r=e.getBoundingClientRect();return {x:r.x,y:r.y}})"
        )
        self.assertAlmostEqual(boxes[0]["y"], boxes[1]["y"], delta=1)
        self.assertAlmostEqual(boxes[2]["y"], boxes[3]["y"], delta=1)
        self.assertLess(boxes[0]["y"], boxes[2]["y"])

    def test_signal_then_payload_and_next_previous_reset(self):
        self.load("flow")
        self.page.emulate_media(reduced_motion="no-preference")
        self.page.locator("#scene-next").click()
        self.page.clock.run_for(350)
        token = self.page.locator(".scene-transfer-token")
        self.assertEqual(token.get_attribute("data-kind"), "signal")
        self.assertEqual(
            self.page.locator("#scene-content").get_attribute("data-state"), "ready"
        )
        self.page.locator("#scene-play").click()
        before = token.bounding_box()
        self.page.clock.run_for(500)
        self.assertEqual(before, token.bounding_box())
        self.page.locator("#scene-play").click()
        self.page.clock.run_for(850)
        self.assertEqual(token.get_attribute("data-kind"), "message")
        self.page.clock.run_for(1000)
        self.assertEqual(
            self.page.locator("#scene-content").get_attribute("data-state"), "delivered"
        )
        self.assertEqual(self.page.locator(".diagram-symbol svg").count(), 3)
        self.assertEqual(self.page.locator(".diagram-links").count(), 1)
        self.page.locator("#scene-previous").click()
        self.assertEqual(
            self.page.locator("#scene-content").get_attribute("data-state"), "ready"
        )
        self.page.locator("#scene-reset").click()
        self.assertEqual(self.page.locator("#scene-next").is_enabled(), True)

    def test_cached_frame_is_measured_when_parent_listener_loads_late(self):
        self.page.emulate_media(reduced_motion="reduce")
        document = render_document(diagram_candidate()["scenes"][0])
        self.page.set_content(
            '<iframe class="ai-scene-frame" sandbox="allow-scripts" '
            'style="width:100%;height:220px;border:0" '
            f'srcdoc="{html.escape(document, quote=True)}"></iframe>'
        )
        self.page.frame_locator("iframe").locator(
            ".diagram-symbol svg"
        ).first.wait_for()
        self.page.clock.run_for(100)
        self.assertEqual(
            self.page.locator("iframe").evaluate("e => e.clientHeight"), 220
        )
        script = PROJECT_ROOT / "assets/js/article-scenes.js"
        self.page.add_script_tag(content=script.read_text())
        self.page.clock.run_for(100)
        self.assertGreater(
            self.page.locator("iframe").evaluate("e => e.clientHeight"), 500
        )

    def test_parent_accepts_tolerated_height_and_motion_padding_with_a_cap(self):
        from playwright.sync_api import expect

        self.page.set_content(
            '<iframe class="ai-scene-frame" sandbox="allow-scripts"></iframe>'
        )
        script = PROJECT_ROOT / "assets/js/article-scenes.js"
        self.page.add_script_tag(content=script.read_text())
        child = self.page.frames[1]
        for requested, expected in ((1013, 1013), (1062, 1062), (2000, 1100)):
            child.evaluate(
                "height => parent.postMessage({type:'article-scene:resize',height}, '*')",
                requested,
            )
            expect(self.page.locator("iframe")).to_have_css("height", f"{expected}px")
        child.evaluate(
            "parent.postMessage({type:'article-scene:resize',height:'500'}, '*')"
        )
        self.page.evaluate("postMessage({type:'article-scene:resize',height:500}, '*')")
        self.page.clock.run_for(100)
        expect(self.page.locator("iframe")).to_have_css("height", "1100px")

    def test_long_mobile_connector_labels_wrap_without_clipping_or_node_collisions(
        self,
    ):
        self.page.set_viewport_size({"width": 320, "height": 1100})
        self.page.emulate_media(reduced_motion="reduce")
        for layout in ("branch", "flow"):
            with self.subTest(layout=layout):
                scene = diagram_candidate(layout)["scenes"][0]
                for link in scene["presentation"]["links"]:
                    link["label"] = "전달흐름설명" * 5 + "요청"
                self.page.set_content(render_document(scene))
                self.page.locator(".diagram-link-label").first.wait_for()
                self.page.clock.run_for(100)
                measures = self.page.locator(".diagram-link-label").evaluate_all(
                    """labels => labels.map(label => {
                      const box = label.getBoundingClientRect();
                      const content = document.querySelector('.scene-content').getBoundingClientRect();
                      const range = document.createRange(); range.selectNodeContents(label);
                      const glyphs = [...range.getClientRects()];
                      const nodes = [...document.querySelectorAll('.diagram-node')].map(node => node.getBoundingClientRect());
                      const intersects = (a,b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
                      return {text:label.textContent, wrapped:box.height > 17,
                        fits:glyphs.every(g => g.left >= content.left && g.right <= content.right && g.top >= content.top && g.bottom <= content.bottom),
                        collision:nodes.some(node => intersects(box,node))};
                    })"""
                )
                for measured in measures:
                    self.assertEqual(len(measured["text"]), 32)
                    self.assertTrue(measured["wrapped"])
                    self.assertTrue(measured["fits"], measured)
                    self.assertFalse(measured["collision"], measured)
                before = self.page.locator(".diagram-board").bounding_box()["height"]
                self.page.evaluate("dispatchEvent(new Event('resize'))")
                self.page.evaluate("dispatchEvent(new Event('resize'))")
                self.assertEqual(
                    self.page.locator(".diagram-board").bounding_box()["height"], before
                )
                self.assertEqual(self.page.locator(".diagram-labels").count(), 1)


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1",
    "set DESIGN_BROWSER_TESTS=1 for Chromium integration",
)
class SceneEffectsBrowserTest(unittest.TestCase):
    def setUp(self):
        self.scene = validate_design(
            json.dumps({"summary": "예시", "scenes": [effect_scene()]}), MOTION_BODY
        )["scenes"][0]
        self.document = render_document(self.scene)

    def load(self, width=700, reduced=False):
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = BrowserSceneVerifier()._launch(playwright)
        self.addCleanup(playwright.stop)
        self.addCleanup(browser.close)
        context = browser.new_context(
            viewport={"width": width + 16, "height": 1100},
            reduced_motion="reduce" if reduced else "no-preference",
            service_workers="block",
        )
        self.addCleanup(context.close)
        self.requests, self.errors = [], []
        context.route(
            "**/*",
            lambda route: (self.requests.append(route.request.url), route.abort()),
        )
        self.page = context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.page.clock.install(time=start)
        self.page.clock.pause_at(start + timedelta(seconds=1))
        self.page.set_default_timeout(2000)
        self.page.set_content(
            '<iframe id="scene" sandbox="allow-scripts" style="width:100%;height:950px;border:0" srcdoc="'
            + html.escape(self.document, quote=True)
            + '"></iframe>'
        )
        self.frame = self.page.frame_locator("#scene")
        self.content = self.frame.locator("#scene-content")
        self.content.locator('[data-entity="result"]').wait_for()
        self.frame.locator("#scene-reset").click()

    def assert_state(self, state, phase="settled"):
        self.assertEqual(self.content.get_attribute("data-state"), state)
        self.assertEqual(self.content.get_attribute("data-phase"), phase)
        self.assertFalse(self.errors)
        self.assertFalse(self.requests)

    def test_production_gate_inspects_every_effect_and_scenario_on_both_widths(self):
        report = BrowserSceneVerifier().check(self.scene, self.document)
        self.assertEqual(report["state_effects_checked"], 6)
        self.assertEqual(report["moving_steps_checked"], 0)
        self.assertEqual(report["scenario_routes_checked"], 6)

    def test_gate_rejects_nonmoving_value_effect_even_if_final_text_changes(self):
        document = self.document.replace(
            "</style>",
            ".scene-content .result{opacity:1!important;translate:0px 0px!important}</style>",
            1,
        )
        with self.assertRaisesRegex(ValueError, "실제 내용 전환 애니메이션 없음"):
            BrowserSceneVerifier().check(self.scene, document)

    def test_effect_is_continuous_and_preserves_context_and_icons(self):
        self.load(width=320)
        self.assertEqual(self.content.locator("span[data-icon] svg").count(), 1)
        self.content.locator('[data-entity="policy"]').evaluate(
            "el => {window.savedPolicy=el;}"
        )
        self.frame.locator('button[data-action="0"]').press("Enter")
        self.assert_state("ready", "moving")
        self.page.clock.run_for(250)
        first = self.content.get_attribute("data-effect-progress")
        self.page.clock.run_for(400)
        self.assertNotEqual(first, self.content.get_attribute("data-effect-progress"))
        self.assertTrue(
            self.content.evaluate(
                "el => window.savedPolicy === el.querySelector('[data-entity=policy]')"
            )
        )
        self.assertEqual(self.content.locator(".scene-transfer-token").count(), 0)
        self.page.clock.run_for(700)
        self.assert_state("accepted")
        self.assertEqual(self.content.locator(".scene-effect-layer").count(), 0)

    def test_pause_resume_and_previous_cancel_effect_without_late_commit(self):
        self.load()
        self.frame.locator('button[data-action="1"]').click()
        self.page.clock.run_for(300)
        self.frame.locator("#scene-play").click()
        first = self.content.get_attribute("data-effect-progress")
        self.page.clock.run_for(6000)
        self.assertEqual(first, self.content.get_attribute("data-effect-progress"))
        self.assert_state("ready", "moving")
        self.frame.locator("#scene-play").click()
        self.page.clock.run_for(250)
        self.assertNotEqual(first, self.content.get_attribute("data-effect-progress"))
        self.frame.locator("#scene-previous").press("Enter")
        self.assert_state("ready")
        self.page.clock.run_for(6000)
        self.assert_state("ready")

    def test_reset_and_reduced_motion_keep_same_outcomes(self):
        self.load(reduced=True, width=320)
        self.page.clock.run_for(12000)
        self.assert_state("ready")
        for index, target in enumerate(("accepted", "encoded", "expanded")):
            self.frame.locator('button[data-action="' + str(index) + '"]').press(
                "Enter"
            )
            self.assert_state(target)
            self.assertEqual(self.content.locator(".scene-effect-layer").count(), 0)
            self.frame.locator("#scene-reset").click()
            self.assert_state("ready")

    def test_reduced_motion_toggle_commits_same_result_without_late_animation(self):
        from playwright.sync_api import expect

        self.load()
        self.frame.locator('button[data-action="1"]').click()
        self.page.clock.run_for(350)
        self.assert_state("ready", "moving")
        self.page.emulate_media(reduced_motion="reduce")
        expect(self.content).to_have_attribute("data-state", "encoded")
        self.assert_state("encoded")
        self.assertEqual(self.content.locator(".scene-effect-layer").count(), 0)
        self.page.clock.run_for(9000)
        self.assert_state("encoded")

    def test_offscreen_suspends_effect_and_return_resumes_same_value_change(self):
        from playwright.sync_api import expect

        self.load()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(350)
        self.page.locator("#scene").evaluate("el => {el.style.marginTop='2500px';}")
        expect(self.content).to_have_attribute("data-playback", "suspended")
        progress = self.content.get_attribute("data-effect-progress")
        self.page.clock.run_for(6000)
        self.assertEqual(progress, self.content.get_attribute("data-effect-progress"))
        self.page.locator("#scene").evaluate("el => {el.style.marginTop='0px';}")
        expect(self.content).to_have_attribute("data-playback", "manual")
        self.page.clock.run_for(1300)
        self.assert_state("accepted")

    def test_reveal_animates_height_not_only_color(self):
        self.load(width=320)
        result = self.content.locator('[data-entity="result"]')
        self.frame.locator('button[data-action="2"]').click()
        self.page.clock.run_for(250)
        before = result.bounding_box()["height"]
        self.page.clock.run_for(400)
        self.assertGreater(result.bounding_box()["height"], before + 2)
        self.frame.locator("#scene-reset").click()
        self.page.clock.run_for(6000)
        self.assert_state("ready")
