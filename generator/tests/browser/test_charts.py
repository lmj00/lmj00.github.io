"""Opt-in Chromium checks for rendering, motion and accessibility."""

from __future__ import annotations

import html
import os
import unittest

from generator.design.scene_charts import verify_chart_graphics
from generator.paths import PROJECT_ROOT
from generator.tests.fixtures.scenes import numeric_scene


@unittest.skipUnless(
    os.environ.get("DESIGN_BROWSER_TESTS") == "1",
    "set DESIGN_BROWSER_TESTS=1 for Chromium integration",
)
class SceneChartsBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        from generator.design.design_browser import BrowserSceneVerifier

        cls.playwright = sync_playwright().start()
        cls.browser = BrowserSceneVerifier()._launch(cls.playwright)
        cls.script = PROJECT_ROOT / "assets/js/scene-charts.js"

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(
            viewport={"width": 700, "height": 900}, reduced_motion="reduce"
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors, self.requests = [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.context.route(
            "**/*",
            lambda route: (self.requests.append(route.request.url), route.abort()),
        )
        self.page.set_content(
            '<main id="content" style="font:16px/1.5 sans-serif;background:#14171d;color:#d6dae0"></main>'
        )
        self.page.add_script_tag(path=str(self.script))

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.assertEqual(self.requests, [])

    def draw(self, scene, state="counter"):
        self.page.evaluate(
            """([scene, state]) => {
          const content = document.querySelector('#content');
          content.innerHTML = scene.states.find(item => item.id === state).html;
          window.ArticleCharts.draw(content, scene, state);
        }""",
            [scene, state],
        )

    def test_sibling_preserves_fallback_and_updates_true_shape(self):
        scene = numeric_scene()
        self.draw(scene)
        host = self.page.locator('[data-entity="measure"]')
        before = host.inner_text()
        self.assertEqual(before, "선택한 설명용 수치: 누적 완료 0 → 1 → 2")
        self.assertEqual(host.locator("svg, table, [data-chart-for]").count(), 0)
        self.assertEqual(self.page.locator("[data-chart-for] [data-entity]").count(), 0)
        line_before = self.page.locator(
            'polyline[data-chart-series="count"]'
        ).get_attribute("points")
        limits = self.page.locator("figure").evaluate(
            "n => [n.dataset.chartMin, n.dataset.chartMax]"
        )
        self.draw(scene, "gauge")
        self.assertEqual(
            self.page.locator('polyline[data-chart-series="count"]').get_attribute(
                "points"
            ),
            line_before,
        )
        self.assertNotEqual(
            self.page.locator('polyline[data-chart-series="current"]').get_attribute(
                "points"
            ),
            line_before,
        )
        self.assertEqual(
            self.page.locator('polyline[data-chart-active="true"]').get_attribute(
                "data-chart-series"
            ),
            "current",
        )
        self.assertEqual(
            self.page.locator("figure").evaluate(
                "n => [n.dataset.chartMin, n.dataset.chartMax]"
            ),
            limits,
        )
        self.assertEqual(limits, ["0", "2"])
        self.assertEqual(
            self.page.locator('svg circle[data-chart-active="true"]').evaluate_all(
                "nodes => nodes.map(n => n.dataset.chartValue)"
            ),
            ["0", "1", "0"],
        )
        self.page.evaluate(
            "scene => ArticleCharts.draw(document.querySelector('#content'), scene, 'gauge')",
            scene,
        )
        self.assertEqual(self.page.locator("figure").count(), 1)

    def test_table_keyboard_and_graph_are_exactly_consistent(self):
        scene = numeric_scene("bar")
        scene["charts"][0]["views"][0]["active_series"] = ["count", "current"]
        self.draw(scene)
        summary = self.page.locator(".scene-chart-details summary")
        summary.press("Enter")
        self.assertTrue(self.page.locator(".scene-chart-table").is_visible())
        self.assertEqual(self.page.locator("tbody tr").count(), 3)
        points = self.page.locator("svg [data-chart-index]").evaluate_all(
            "nodes => Object.fromEntries(nodes.map(n => [n.dataset.chartSeries + ':' + n.dataset.chartIndex, n.dataset.chartValue]))"
        )
        table = self.page.locator("tbody td").evaluate_all(
            "nodes => Object.fromEntries(nodes.map(n => [n.dataset.chartSeries + ':' + n.dataset.chartIndex, n.textContent]))"
        )
        self.assertEqual(points, table)
        summary.press("Space")
        self.assertFalse(self.page.locator(".scene-chart-table").is_visible())

    def test_signed_bars_have_a_shared_zero_baseline_and_true_height(self):
        scene = numeric_scene("bar")
        scene["charts"][0]["series"][0]["values"] = [-4, 0, 8]
        self.draw(scene)
        bars = self.page.locator('svg rect[data-chart-series="count"]').evaluate_all(
            "nodes => nodes.map(n => ({y:+n.getAttribute('y'), h:+n.getAttribute('height'), value:+n.dataset.chartValue}))"
        )
        self.assertAlmostEqual(bars[0]["y"], bars[1]["y"])
        self.assertAlmostEqual(bars[2]["y"] + bars[2]["h"], bars[0]["y"])
        self.assertAlmostEqual(bars[2]["h"], bars[0]["h"] * 2)
        self.assertEqual(bars[1]["h"], 0)

    def test_all_zero_series_have_finite_graph_coordinates(self):
        scene = numeric_scene("bar")
        for series in scene["charts"][0]["series"]:
            series["values"] = [0, 0, 0]
        self.draw(scene)
        graphic = self.page.locator("svg").inner_html()
        self.assertNotIn("NaN", graphic)
        self.assertNotIn("Infinity", graphic)
        self.assertEqual(
            self.page.locator("figure").get_attribute("data-chart-max"), "1"
        )
        verify_chart_graphics(
            self.page.locator("figure"), scene["charts"][0], "counter"
        )

    def test_actual_graph_verifier_rejects_missing_paint_tiny_area_or_false_geometry(
        self,
    ):
        scene = numeric_scene()
        for tamper in (
            "root.querySelector('svg').style.height='1px'",
            "root.querySelector('polyline').style.stroke='transparent'",
            "root.querySelector('circle').style.fill='transparent'",
            "root.querySelector('circle').style.cy='40px'",
            "root.querySelector('circle').remove()",
        ):
            with self.subTest(tamper=tamper):
                self.draw(scene)
                root = self.page.locator("figure")
                verify_chart_graphics(root, scene["charts"][0], "counter")
                root.evaluate("root => {" + tamper + "}")
                with self.assertRaisesRegex(ValueError, "수치 차트"):
                    verify_chart_graphics(root, scene["charts"][0], "counter")

    def test_generic_attribute_style_cannot_override_numeric_svg_paint_or_geometry(
        self,
    ):
        self.page.add_style_tag(
            content="#content [fill]{fill:transparent;stroke:transparent;fill-opacity:0;stroke-opacity:0;transform:scale(0);width:1px;height:1px;cx:0;cy:0;r:0}"
        )
        for kind in ("line", "bar"):
            with self.subTest(kind=kind):
                scene = numeric_scene(kind)
                self.draw(scene)
                verify_chart_graphics(
                    self.page.locator("figure"), scene["charts"][0], "counter"
                )

    def test_process_reveals_only_declared_points_on_stable_axes(self):
        scene = numeric_scene(mode="process")
        scene["charts"][0]["views"][0]["visible_points"] = 1
        self.draw(scene)
        self.assertEqual(self.page.locator("svg circle").count(), 2)
        self.assertEqual(self.page.locator("tbody tr").count(), 1)
        self.assertEqual(
            self.page.locator("figure").get_attribute("data-chart-max"), "2"
        )

    def test_mobile_and_long_korean_labels_stay_readable(self):
        scene = numeric_scene()
        scene["charts"][0]["labels"] = ["관측지점의상세한한국어설명" * 3] * 3
        for width in (320, 700):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 1200})
                self.draw(scene)
                self.page.locator(".scene-chart-details summary").press("Enter")
                sizes = self.page.evaluate("""() => ({
                  width: innerWidth, scroll: document.documentElement.scrollWidth,
                  fonts: [...document.querySelectorAll('.scene-chart-axis, .scene-chart-caption, .scene-chart-table')].map(n => parseFloat(getComputedStyle(n).fontSize)),
                  animations: document.getAnimations().length
                })""")
                self.assertLessEqual(sizes["scroll"], sizes["width"])
                self.assertTrue(all(size >= 12 for size in sizes["fonts"]))
                self.assertEqual(sizes["animations"], 0)

    def test_untrusted_text_cannot_execute_or_create_extra_markup(self):
        scene = numeric_scene()
        scene["charts"][0]["label"] = '<img src=x onerror="window.chartInjected=true">'
        self.draw(scene)
        self.assertEqual(self.page.locator(".scene-chart img").count(), 0)
        self.assertFalse(self.page.evaluate("Boolean(window.chartInjected)"))
        self.assertIn("<img", self.page.locator("figcaption").inner_text())
        scene["charts"][0]["series"][0]["values"][0] = "not a number"
        self.draw(scene)
        self.assertEqual(self.page.locator("figure").count(), 0)

    def test_full_sandbox_document_keeps_chart_and_host_on_state_change(self):
        from generator.design.scene_document import render_document
        from generator.tests.fixtures.scenes import effect_scene

        scene = effect_scene()
        scene.update(numeric_scene())
        scene["title"] = "설명용 관측 수치를 모양으로 비교하기"
        scene["css"] = ".scene-content {min-width:0}"
        scene["effects"] = [
            {
                "from": "counter",
                "to": "gauge",
                "kind": "compare",
                "entities": ["measure"],
                "duration_ms": 900,
            }
        ]
        scene["scenarios"] = [
            {"id": "gauge", "label": "진행 중 요청 강조", "steps": ["counter", "gauge"]}
        ]
        scene["playback"] = {"steps": ["counter", "gauge"], "interval_ms": 2000}
        scene["explanation"]["key_entities"] = ["measure"]
        for state in scene["states"]:
            state["description"] = (
                "가상 수치를 선의 높이로 비교하며 실제 측정값은 아닙니다."
            )
            state["actions"] = (
                [{"label": "진행 중 요청 강조", "target": "gauge"}]
                if state["id"] == "counter"
                else []
            )
        for width in (320, 700):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 1200})
                self.page.set_content(
                    '<iframe id="chart-scene" sandbox="allow-scripts" style="display:block;width:100%;height:1100px;border:0" srcdoc="'
                    + html.escape(render_document(scene), quote=True)
                    + '"></iframe>'
                )
                frame = self.page.frame_locator("#chart-scene")
                chart = frame.locator(".scene-chart")
                chart.wait_for()
                self.assertEqual(chart.get_attribute("data-chart-state"), "counter")
                self.assertEqual(
                    chart.evaluate("n => getComputedStyle(n).color"),
                    "rgb(214, 218, 224)",
                )
                frame.locator('button[data-action="0"]').click()
                self.assertEqual(chart.get_attribute("data-chart-state"), "gauge")
                self.assertEqual(
                    chart.locator('polyline[data-chart-active="true"]').get_attribute(
                        "data-chart-series"
                    ),
                    "current",
                )
                self.assertEqual(
                    frame.locator('[data-entity="measure"] [data-chart-for]').count(), 0
                )
                frame.locator(".scene-chart-details summary").press("Enter")
                self.assertTrue(frame.locator(".scene-chart-table").is_visible())
                self.assertEqual(frame.locator("tbody td").count(), 6)
                dimensions = frame.locator("body").evaluate(
                    "n => ({scroll:document.documentElement.scrollWidth,width:innerWidth})"
                )
                self.assertLessEqual(dimensions["scroll"], dimensions["width"])
