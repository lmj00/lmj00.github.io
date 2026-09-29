"""Opt-in Chromium checks for rendering, motion and accessibility."""

from __future__ import annotations

import copy
import html
import os
import unittest
from datetime import datetime, timedelta, timezone

from generator.design.design_browser import BrowserSceneVerifier
from generator.design.scene_document import render_document
from generator.tests.fixtures.scenes import (
    clarity_scene,
    continuous_candidate,
    multi_change_scene,
)


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1",
    "set DESIGN_BROWSER_TESTS=1 for Chromium integration",
)
class ClarityRuntimeTest(unittest.TestCase):
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
        self.scene = clarity_scene()
        self.context = self.browser.new_context(
            viewport={"width": 716, "height": 1200},
            reduced_motion="no-preference",
            service_workers="block",
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors, self.requests = [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.context.route(
            "**/*",
            lambda route: (self.requests.append(route.request.url), route.abort()),
        )
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.page.clock.install(time=start)
        self.page.clock.pause_at(start + timedelta(seconds=1))
        self.page.set_default_timeout(2000)

    def load(self, *, reduced=False):
        self.page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
        document = render_document(self.scene)
        self.page.set_content(
            '<iframe id="scene" sandbox="allow-scripts" style="width:100%;height:1100px;border:0" srcdoc="'
            + html.escape(document, quote=True)
            + '"></iframe>'
        )
        self.frame = self.page.frame_locator("#scene")
        self.content = self.frame.locator("#scene-content")
        self.content.locator("[data-entity]").first.wait_for()

    def state(self):
        return self.content.get_attribute("data-state")

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.assertEqual(self.requests, [])

    def test_compare_and_explore_do_not_start_without_a_choice(self):
        for mode in ("compare", "explore"):
            with self.subTest(mode=mode):
                self.scene["interaction_mode"] = mode
                self.load()
                self.page.clock.run_for(15000)
                self.assertEqual(self.state(), "ready")
                self.assertTrue(self.frame.locator("#scene-change-summary").is_hidden())
                self.assertEqual(
                    self.frame.locator(
                        '#scene-scenarios button[aria-pressed="true"]'
                    ).count(),
                    0,
                )

    def test_process_retains_one_finite_automatic_run(self):
        self.scene["interaction_mode"] = "process"
        self.load()
        self.page.clock.run_for(7000)
        self.assertEqual(self.state(), "team")
        self.page.clock.run_for(15000)
        self.assertEqual(self.state(), "team")
        self.assertEqual(
            self.frame.locator("#scene-play").get_attribute("aria-pressed"), "false"
        )

    def test_one_choice_button_executes_and_preserves_exact_original(self):
        self.load(reduced=True)
        self.assertEqual(
            self.frame.get_by_role("button", name="team 라벨 추가", exact=True).count(),
            1,
        )
        self.assertEqual(self.frame.locator("#scene-controls button").count(), 0)
        self.frame.locator('button[data-action="0"]').press("Enter")
        self.assertEqual(self.state(), "team")
        self.assertEqual(self.frame.locator(".scene-change-before").inner_text(), "{}")
        self.assertEqual(
            self.frame.locator("#scene-progress").inner_text(), "직접 선택한 결과"
        )
        self.assertEqual(
            self.frame.locator(".scene-change-after").inner_text(), '{team: "demo"}'
        )
        self.assertEqual(
            self.frame.locator(".scene-change-invariant-value").inner_text(), "dev"
        )
        self.assertIn(
            "빈 labels", self.frame.locator(".scene-change-reason").inner_text()
        )
        self.assertEqual(self.content.locator('[data-scene-changed="true"]').count(), 1)
        self.assertEqual(
            self.content.locator('[data-scene-changed="true"]').get_attribute(
                "data-entity"
            ),
            "labels",
        )
        self.frame.locator('button[data-scenario="env"]').press("Enter")
        self.assertEqual(self.state(), "env")
        self.assertEqual(self.frame.locator(".scene-change-before").inner_text(), "{}")
        self.assertEqual(
            self.frame.locator(
                '#scene-scenarios button[aria-pressed="true"]'
            ).get_attribute("data-scenario"),
            "env",
        )
        self.page.clock.run_for(12000)
        self.assertEqual(self.state(), "env")

    def test_previous_and_reset_remove_stale_comparison(self):
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.frame.locator("#scene-previous").click()
        self.assertEqual(self.state(), "ready")
        self.assertTrue(self.frame.locator("#scene-change-summary").is_hidden())
        self.assertEqual(
            self.frame.locator('#scene-scenarios button[aria-pressed="true"]').count(),
            0,
        )
        self.frame.locator('button[data-action="1"]').click()
        self.frame.locator("#scene-reset").click()
        self.assertEqual(self.state(), "ready")
        self.assertTrue(self.frame.locator("#scene-change-summary").is_hidden())

    def test_numeric_change_is_primary_and_secondary_values_stay_accessible(self):
        self.scene = multi_change_scene()
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        panel = self.frame.locator("#scene-change-summary")
        primary = panel.locator(":scope > .scene-change-row")
        self.assertEqual(primary.count(), 1)
        self.assertEqual(primary.get_attribute("data-entity"), "value")
        self.assertEqual(primary.get_attribute("data-primary"), "true")
        self.assertEqual(primary.locator(".scene-change-before").inner_text(), "0")
        self.assertEqual(primary.locator(".scene-change-after").inner_text(), "3")
        details = panel.locator("details.scene-change-details")
        self.assertEqual(details.locator("summary").inner_text(), "추가 변경 2개")
        self.assertIsNone(details.get_attribute("open"))
        self.assertEqual(panel.locator(".scene-change-row").count(), 3)
        self.assertTrue(details.locator('[data-entity="name"]').is_hidden())
        self.assertTrue(panel.locator(".scene-change-reason").is_visible())
        self.assertTrue(panel.locator(".scene-change-invariant-value").is_visible())
        details.locator("summary").press("Enter")
        self.assertIsNotNone(details.get_attribute("open"))
        for entity, expected in (("name", "demo"), ("kind", "A")):
            row = details.locator(f'[data-entity="{entity}"]')
            self.assertTrue(row.is_visible())
            self.assertEqual(row.locator(".scene-change-before").inner_text(), "—")
            self.assertEqual(row.locator(".scene-change-after").inner_text(), expected)
        details.locator("summary").press("Space")
        self.assertIsNone(details.get_attribute("open"))

    def test_primary_prefers_numbers_among_empty_placeholders_and_preserves_ties(self):
        self.scene = multi_change_scene()
        self.scene["states"][0]["html"] = self.scene["states"][0]["html"].replace(
            'data-entity="value">0', 'data-entity="value">—'
        )
        for edge in self.scene["change_explanations"]:
            edge["changes"][2]["before"] = "—"
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        primary = self.frame.locator('.scene-change-row[data-primary="true"]')
        self.assertEqual(primary.get_attribute("data-entity"), "value")
        # Without a concrete/numeric distinction, the author's first field wins.
        for state in self.scene["states"][1:]:
            state["html"] = (
                state["html"]
                .replace('data-entity="value">3', 'data-entity="value">many')
                .replace('data-entity="value">1', 'data-entity="value">few')
            )
        for edge in self.scene["change_explanations"]:
            edge["changes"][2]["after"] = "many" if edge["to"] == "team" else "few"
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.assertEqual(
            self.frame.locator('.scene-change-row[data-primary="true"]').get_attribute(
                "data-entity"
            ),
            "name",
        )

    def test_single_change_needs_no_secondary_disclosure(self):
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.assertEqual(self.frame.locator(".scene-change-details").count(), 0)

    def test_labelled_numeric_sequence_is_preferred_over_empty_names(self):
        self.scene = multi_change_scene()
        self.scene["states"][0]["html"] = self.scene["states"][0]["html"].replace(
            'data-entity="value">0', 'data-entity="value">—'
        )
        self.scene["states"][1]["html"] = self.scene["states"][1]["html"].replace(
            'data-entity="value">3', 'data-entity="value">t1:0 · t2:3'
        )
        self.scene["change_explanations"][0]["changes"][2].update(
            before="—", after="t1:0 · t2:3"
        )
        self.scene["change_explanations"][1]["changes"][2]["before"] = "—"
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.assertEqual(
            self.frame.locator('.scene-change-row[data-primary="true"]').get_attribute(
                "data-entity"
            ),
            "value",
        )

    def test_expanded_changes_close_for_next_choice_and_reset_without_stale_rows(self):
        self.scene = multi_change_scene()
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.frame.locator(".scene-change-details summary").press("Enter")
        self.assertIsNotNone(
            self.frame.locator(".scene-change-details").get_attribute("open")
        )
        self.frame.locator('button[data-scenario="env"]').click()
        self.assertIsNone(
            self.frame.locator(".scene-change-details").get_attribute("open")
        )
        self.assertEqual(
            self.frame.locator(
                '.scene-change-row[data-primary="true"] .scene-change-after'
            ).inner_text(),
            "1",
        )
        self.frame.locator("#scene-previous").click()
        self.assertEqual(self.state(), "ready")
        self.assertEqual(self.frame.locator(".scene-change-row").count(), 0)
        self.frame.locator('button[data-action="1"]').click()
        self.frame.locator(".scene-change-details summary").press("Enter")
        self.frame.locator("#scene-reset").click()
        self.assertEqual(self.frame.locator(".scene-change-details").count(), 0)

    def test_expanded_change_space_freezes_during_paused_alternative(self):
        self.scene = multi_change_scene()
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.frame.locator(".scene-change-details summary").press("Enter")
        self.page.emulate_media(reduced_motion="no-preference")
        self.frame.locator('button[data-scenario="env"]').click()
        self.page.clock.run_for(200)
        self.assertIsNotNone(
            self.frame.locator("#scene-change-summary").get_attribute("inert")
        )
        self.frame.locator("#scene-play").click()
        height = self.frame.locator(".scene-change-slot").bounding_box()["height"]
        self.page.clock.run_for(3000)
        self.assertAlmostEqual(
            self.frame.locator(".scene-change-slot").bounding_box()["height"],
            height,
            delta=1,
        )
        self.frame.locator("#scene-play").click()
        self.page.clock.run_for(1200)
        self.assertEqual(self.state(), "env")
        self.assertEqual(self.frame.locator("[inert]").count(), 0)
        self.assertIsNone(
            self.frame.locator(".scene-change-details").get_attribute("open")
        )

    def test_mobile_disclosure_resizes_once_per_actual_height_and_exposes_every_value(
        self,
    ):
        self.scene = multi_change_scene()
        self.page.set_viewport_size({"width": 320, "height": 1200})
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(100)
        self.page.evaluate("""() => {
            window.resizeMessages = [];
            addEventListener('message', e => {
                if(e.data?.type === 'article-scene:resize') resizeMessages.push(e.data.height);
            });
        }""")
        panel = self.frame.locator("#scene-change-summary")

        def toggle_details(expected_messages):
            details = self.frame.locator(".scene-change-details")
            # Native <details> queues its toggle event independently of the
            # mocked clock. Await that event before advancing the resize rAF;
            # otherwise a late toggle can leave its rAF on the paused clock.
            details.evaluate("""el => {
                window.changeToggleDone = new Promise(resolve => {
                    el.addEventListener('toggle', () => resolve(true), {once:true});
                });
            }""")
            details.locator("summary").press("Enter")
            details.evaluate("() => window.changeToggleDone")
            self.page.clock.run_for(100)
            self.page.wait_for_function(
                "expected => resizeMessages.length >= expected",
                arg=expected_messages,
                polling=10,
            )

        compact = panel.bounding_box()["height"]
        toggle_details(1)
        expanded = panel.bounding_box()["height"]
        self.assertGreater(expanded - compact, 70)
        self.assertEqual(panel.locator(".scene-change-row:visible").count(), 3)
        self.assertEqual(len(self.page.evaluate("resizeMessages")), 1)
        self.page.clock.run_for(1000)
        self.page.wait_for_timeout(30)
        self.assertEqual(len(self.page.evaluate("resizeMessages")), 1)
        toggle_details(2)
        self.assertAlmostEqual(panel.bounding_box()["height"], compact, delta=1)
        self.assertEqual(len(self.page.evaluate("resizeMessages")), 2)
        self.assertLessEqual(
            self.content.evaluate("() => document.documentElement.scrollWidth"),
            self.content.evaluate("() => innerWidth"),
        )

    def test_alternative_keeps_previous_view_without_rendering_initial_flash(self):
        self.load()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(1050)
        self.assertEqual(self.state(), "team")
        self.frame.locator('button[data-scenario="env"]').click()
        self.assertEqual(self.state(), "team")
        self.assertEqual(self.content.get_attribute("data-comparison-origin"), "ready")
        self.assertEqual(self.content.get_attribute("data-transition"), "ready->env")
        self.assertIn(
            'team: "demo"', self.content.locator(".scene-effect-layer").inner_text()
        )
        self.assertEqual(
            self.frame.locator(".scene-change-after").inner_text(), '{team: "demo"}'
        )
        self.assertEqual(
            self.frame.locator("#scene-change-summary").get_attribute("aria-busy"),
            "true",
        )
        self.page.clock.run_for(1050)
        self.assertEqual(self.state(), "env")
        self.assertIsNone(self.content.get_attribute("data-comparison-origin"))
        self.assertEqual(self.frame.locator(".scene-change-before").inner_text(), "{}")
        self.assertEqual(
            self.frame.locator(".scene-change-after").inner_text(), '{env: "test"}'
        )
        self.frame.locator("#scene-previous").click()
        self.assertEqual(self.state(), "ready")

    def test_selected_result_is_not_replayed_by_selecting_it_again(self):
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.page.emulate_media(reduced_motion="no-preference")
        self.frame.locator('button[data-scenario="team"]').click()
        self.assertEqual(self.state(), "team")
        self.assertEqual(self.content.get_attribute("data-phase"), "settled")
        self.assertEqual(self.content.locator(".scene-effect-layer").count(), 0)

    def test_change_space_expands_before_result_and_freezes_when_paused(self):
        self.load()
        slot = self.frame.locator(".scene-change-slot")
        self.assertEqual(slot.bounding_box()["height"], 0)
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(300)
        middle = slot.bounding_box()["height"]
        self.assertGreater(middle, 20)
        self.assertTrue(self.frame.locator("#scene-change-summary").is_hidden())
        self.frame.locator("#scene-play").click()
        frozen = slot.bounding_box()["height"]
        self.page.clock.run_for(5000)
        self.assertAlmostEqual(slot.bounding_box()["height"], frozen, delta=1)
        self.frame.locator("#scene-play").click()
        self.page.clock.run_for(500)
        near_end = slot.bounding_box()["height"]
        self.page.clock.run_for(500)
        self.assertGreater(slot.bounding_box()["height"], middle)
        self.assertAlmostEqual(slot.bounding_box()["height"], near_end, delta=12)
        self.assertTrue(self.frame.locator("#scene-change-summary").is_visible())
        self.assertEqual(self.frame.locator("[inert]").count(), 0)
        self.frame.locator("#scene-reset").click()
        self.assertEqual(slot.bounding_box()["height"], 0)

    def test_cancel_alternative_removes_layout_animations_and_restores_original(self):
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.page.emulate_media(reduced_motion="no-preference")
        self.frame.locator('button[data-scenario="env"]').click()
        self.page.clock.run_for(200)
        self.frame.locator("#scene-previous").click()
        self.assertEqual(self.state(), "ready")
        self.assertEqual(
            self.frame.locator(".scene-change-slot").bounding_box()["height"], 0
        )
        self.assertEqual(self.content.locator(".scene-effect-layer").count(), 0)
        self.page.clock.run_for(1500)
        self.assertEqual(self.state(), "ready")

    def test_body_height_changes_in_small_steps_instead_of_at_completion(self):
        self.load()
        self.content.evaluate("""() => {
            window.heightSamples = [document.body.scrollHeight];
            window.sampleHeights = true;
            function sample() {
                heightSamples.push(document.body.scrollHeight);
                if (sampleHeights) requestAnimationFrame(sample);
            }
            requestAnimationFrame(sample);
        }""")
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(1100)
        heights = self.content.evaluate(
            "() => {sampleHeights=false;return heightSamples}"
        )
        self.assertGreater(heights[-1] - heights[0], 50)
        self.assertLessEqual(max(abs(b - a) for a, b in zip(heights, heights[1:])), 32)

    def test_switch_also_animates_a_field_undone_by_the_new_alternative(self):
        for state in self.scene["states"]:
            count = "1" if state["id"] == "team" else "0"
            state["html"] += f'<p data-entity="count">count: {count}</p>'
        self.scene["effects"][0]["entities"].append("count")
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.page.emulate_media(reduced_motion="no-preference")
        self.frame.locator('button[data-scenario="env"]').click()
        self.assertIn(
            "count: 1", self.content.locator(".scene-effect-layer").inner_text()
        )
        self.assertEqual(
            self.content.locator('[data-entity="count"]').evaluate(
                "n => n.getAnimations().length"
            ),
            1,
        )
        self.page.clock.run_for(1100)
        self.assertEqual(
            self.content.locator('[data-entity="count"]').inner_text(), "count: 0"
        )

    def test_resize_requests_are_coalesced_and_same_height_is_not_resent(self):
        self.load()
        self.page.clock.run_for(100)
        self.page.evaluate("""() => {
            window.resizeMessages = [];
            addEventListener('message', e => {
                if(e.data?.type === 'article-scene:resize') resizeMessages.push(e.data.height);
            });
        }""")
        # Real parent measurement request still gets a response at unchanged size.
        self.page.evaluate("""() => {
            for(let i=0;i<5;i++)document.querySelector('iframe').contentWindow.postMessage({type:'article-scene:measure'}, '*');
        }""")
        self.page.wait_for_timeout(30)
        self.page.clock.run_for(64)
        self.page.wait_for_timeout(30)
        self.assertEqual(len(self.page.evaluate("resizeMessages")), 1)
        self.content.evaluate(
            "() => {for(let i=0;i<5;i++)dispatchEvent(new Event('resize'));}"
        )
        self.page.clock.run_for(64)
        self.page.wait_for_timeout(30)
        self.assertEqual(len(self.page.evaluate("resizeMessages")), 1)

    def test_two_names_for_one_outcome_still_produce_one_action(self):
        self.scene["scenarios"][0]["label"] = "팀 라벨이 있는 경우"
        self.load(reduced=True)
        self.assertEqual(
            self.frame.get_by_role("button", name="team 라벨 추가", exact=True).count(),
            1,
        )
        self.assertEqual(self.frame.locator("#scene-controls button").count(), 0)
        self.frame.locator('button[data-action="0"]').click()
        self.assertEqual(self.state(), "team")

    def test_paused_change_cannot_be_replaced_by_another_choice(self):
        self.load()
        self.frame.locator('button[data-action="0"]').click()
        self.page.clock.run_for(250)
        self.frame.locator("#scene-play").click()
        self.assertTrue(self.frame.locator('button[data-scenario="env"]').is_disabled())
        self.page.clock.run_for(8000)
        self.assertEqual(self.state(), "ready")
        self.assertTrue(self.frame.locator("#scene-change-summary").is_hidden())
        self.frame.locator("#scene-play").click()
        self.page.clock.run_for(1000)
        self.assertEqual(self.state(), "team")
        self.assertTrue(self.frame.locator("#scene-change-summary").is_visible())

    def test_reason_repeated_as_state_description_is_shown_once(self):
        reason = self.scene["change_explanations"][0]["reason"]
        self.scene["states"][1]["description"] = reason
        self.load(reduced=True)
        self.frame.locator('button[data-action="0"]').click()
        self.assertTrue(self.frame.locator("#scene-status").is_hidden())
        self.assertEqual(
            self.frame.locator(".scene-change-reason").inner_text(), reason
        )
        self.assertTrue(
            self.frame.locator("#scene-change-summary").evaluate(
                "el => document.activeElement === el"
            )
        )
        self.frame.locator("#scene-reset").click()
        self.assertTrue(self.frame.locator("#scene-status").is_visible())

    def test_distinct_description_is_accessible_and_closes_for_next_choice(self):
        self.load(reduced=True)
        self.assertTrue(self.frame.locator("#scene-status").is_visible())
        self.assertTrue(self.frame.locator("#scene-extra-details summary").is_hidden())
        self.frame.locator('button[data-action="0"]').click()
        details = self.frame.locator("#scene-extra-details")
        self.assertIsNone(details.get_attribute("open"))
        self.assertTrue(self.frame.locator("#scene-status").is_hidden())
        details.locator("summary").press("Enter")
        self.assertEqual(
            self.frame.locator("#scene-status").inner_text(),
            self.scene["states"][1]["description"],
        )
        self.frame.locator('button[data-scenario="env"]').click()
        self.assertIsNone(details.get_attribute("open"))
        self.assertTrue(
            self.frame.locator("#scene-change-summary").evaluate(
                "el => document.activeElement === el"
            )
        )
        self.frame.locator("#scene-reset").click()
        self.assertIsNotNone(details.get_attribute("open"))
        self.assertTrue(details.locator("summary").is_hidden())
        self.assertTrue(self.frame.locator("#scene-status").is_visible())

    def test_manual_long_branch_updates_selected_scenario(self):
        self.scene = copy.deepcopy(continuous_candidate()["scenes"][0])
        self.load(reduced=True)
        self.frame.locator('button[data-action="1"]').click()
        self.assertEqual(self.state(), "lost")
        self.assertEqual(
            self.frame.locator(
                '#scene-scenarios button[aria-pressed="true"]'
            ).get_attribute("data-scenario"),
            "disconnect",
        )
        self.frame.locator("#scene-next").click() if self.frame.locator(
            "#scene-next"
        ).count() else self.frame.locator('button[data-action="0"]').click()
        self.assertEqual(self.state(), "returned")


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1",
    "set DESIGN_BROWSER_TESTS=1 for Chromium integration",
)
class ClarityBrowserGateTest(unittest.TestCase):
    def test_production_gate_checks_every_visible_before_after_pair(self):
        scene = clarity_scene()
        report = BrowserSceneVerifier().check(scene, render_document(scene))
        self.assertEqual(report["change_explanations_checked"], 4)
        self.assertEqual(report["additional_descriptions_checked"], 4)
        self.assertEqual(report["scenario_routes_checked"], 4)

    def test_gate_rejects_hidden_original_even_when_result_changes(self):
        scene = clarity_scene()
        document = render_document(scene).replace(
            "</style>", ".scene-change-before{display:none!important}</style>", 1
        )
        with self.assertRaisesRegex(ValueError, "변경 전후 비교.*숨겨지거나"):
            BrowserSceneVerifier().check(scene, document)

    def test_gate_rejects_transparent_original_value(self):
        scene = clarity_scene()
        scene["css"] += '.scene-content [data-entity="namespace"]{color:transparent}'
        with self.assertRaisesRegex(ValueError, "실제 텍스트.*transparent-text"):
            BrowserSceneVerifier().check(scene, render_document(scene))

    def test_gate_rejects_transparent_text_fill(self):
        scene = clarity_scene()
        document = render_document(scene).replace(
            "</style>",
            '.scene-content [data-entity="namespace"]{-webkit-text-fill-color:rgba(255,255,255,0)}</style>',
            1,
        )
        with self.assertRaisesRegex(ValueError, "실제 텍스트.*transparent-text"):
            BrowserSceneVerifier().check(scene, document)

    def test_gate_rejects_original_inside_zero_opacity_ancestor(self):
        scene = clarity_scene()
        document = render_document(scene).replace(
            "</style>", ".scene-content .policy{opacity:0}</style>", 1
        )
        with self.assertRaisesRegex(
            ValueError, "화면 검사 실패|실제 텍스트.*hidden-text-ancestor"
        ):
            BrowserSceneVerifier().check(scene, document)

    def test_gate_rejects_text_clipped_inside_an_ordinary_wrapper(self):
        scene = clarity_scene()
        document = render_document(scene).replace(
            "</style>",
            '.scene-content [data-entity="namespace"]{display:block;width:1px;overflow:hidden;white-space:nowrap}</style>',
            1,
        )
        with self.assertRaisesRegex(ValueError, "실제 텍스트.*clipped-text-x"):
            BrowserSceneVerifier().check(scene, document)

    def test_gate_rejects_invisible_value_only_in_outcome(self):
        scene = clarity_scene()
        scene["states"][1]["html"] = scene["states"][1]["html"].replace(
            'data-entity="labels"', 'data-entity="labels" class="invisible-outcome"'
        )
        scene["css"] += ".scene-content .invisible-outcome{color:transparent}"
        with self.assertRaisesRegex(
            ValueError, "변경 후 값.*실제 텍스트.*transparent-text"
        ):
            BrowserSceneVerifier().check(scene, render_document(scene))

    def test_gate_rejects_offscreen_original_even_if_wrapper_still_has_text(self):
        scene = clarity_scene()
        scene["css"] += (
            '.scene-content [data-entity="namespace"]{display:inline-block;transform:translateX(-10000px)}'
        )
        with self.assertRaisesRegex(ValueError, "실제 텍스트.*offscreen-text"):
            BrowserSceneVerifier().check(scene, render_document(scene))

    def test_collapsing_long_description_does_not_bypass_expanded_height_limit(self):
        scene = clarity_scene()
        scene["states"][1]["description"] = "원래 상태 설명의 문장입니다. " * 35
        self.assertLessEqual(len(scene["states"][1]["description"]), 700)
        with self.assertRaisesRegex(
            ValueError, "expanded-description.*최대 허용 1050px"
        ):
            BrowserSceneVerifier().check(scene, render_document(scene))
