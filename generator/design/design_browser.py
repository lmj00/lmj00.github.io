"""네트워크 없는 Chromium에서 생성된 시각화의 상태·전이를 검사한다."""

from __future__ import annotations

import html
import math
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from generator.design.layout_diagnostics import BrowserLayoutError, observe_layout
from generator.design.scene_charts import verify_chart_graphics
from generator.design.scene_document import state_paths

# A reading-length target is not a rendering failure. Keep the hard limit below
# the parent frame's 1100px cap (assets/js/article-scenes.js), including resize padding.
SCENE_HEIGHT_TARGET_PX = 950
SCENE_HEIGHT_LIMIT_PX = 1050


class BrowserUnavailable(RuntimeError):
    pass


class BrowserSceneVerifier:
    @staticmethod
    def _check_height(height, width, state_id, phase="settled", *, frame=None):
        if height > SCENE_HEIGHT_LIMIT_PX:
            message = (
                f"{width}px / {state_id} ({phase}) 화면 높이 {height}px > "
                f"최대 허용 {SCENE_HEIGHT_LIMIT_PX}px"
            )
            if frame is not None:
                raise BrowserLayoutError(
                    message,
                    [
                        observe_layout(
                            frame, state_id, phase, ["height"], SCENE_HEIGHT_LIMIT_PX
                        )
                    ],
                )
            raise ValueError(message)
        if height > SCENE_HEIGHT_TARGET_PX:
            return {
                "kind": "height",
                "severity": "warning",
                "width_px": width,
                "state": state_id,
                "phase": phase,
                "height_px": height,
                "target_px": SCENE_HEIGHT_TARGET_PX,
                "limit_px": SCENE_HEIGHT_LIMIT_PX,
            }
        return None

    def _check_settled_layouts(self, page, frame, scene, paths, height_warnings):
        """Collect every settled width/state before transition checks can fail."""
        diagnostics = []
        messages = []
        for width in (320, 700):
            page.set_viewport_size({"width": width + 16, "height": 1200})
            for state in scene["states"]:
                if len(scene["states"]) > 1:
                    frame.locator("#scene-reset").click()
                for index in paths[state["id"]]:
                    frame.locator(f'button[data-action="{index}"]').click()
                if (
                    frame.locator("#scene-content").get_attribute("data-state")
                    != state["id"]
                ):
                    raise ValueError("상태 이동 실패")
                measurements = frame.locator("body").evaluate("""body => {
                  const content = document.getElementById('scene-content');
                  return {overflow: document.documentElement.scrollWidth > innerWidth + 1,
                    height: body.scrollHeight, visible: content.getBoundingClientRect().height,
                    clipped: content.scrollWidth > content.clientWidth + 1 || content.scrollHeight > content.clientHeight + 1,
                    hidden: [content, ...content.querySelectorAll('*')].some(el => el.textContent.trim() && (getComputedStyle(el).visibility === 'hidden' || getComputedStyle(el).display === 'none' || Number(getComputedStyle(el).opacity) === 0)),
                    tiny: [...content.querySelectorAll('*')].some(el => el.textContent.trim() && parseFloat(getComputedStyle(el).fontSize) < 12)};
                }""")
                failures = [
                    key
                    for key in ("overflow", "hidden", "clipped", "tiny")
                    if measurements[key]
                ]
                if measurements["visible"] < 35:
                    failures.append("short")
                if measurements["height"] > SCENE_HEIGHT_LIMIT_PX:
                    failures.append("height")
                if failures:
                    diagnostics.append(
                        observe_layout(
                            frame,
                            state["id"],
                            "settled",
                            failures,
                            SCENE_HEIGHT_LIMIT_PX,
                        )
                    )
                    if failures == ["height"]:
                        messages.append(
                            f"{width}px / {state['id']} (settled) 화면 높이 {measurements['height']}px > 최대 허용 {SCENE_HEIGHT_LIMIT_PX}px"
                        )
                    else:
                        messages.append(
                            f"{width}px / {state['id']} 화면 검사 실패: {measurements}"
                        )
                else:
                    warning = self._check_height(
                        measurements["height"], width, state["id"]
                    )
                    if warning:
                        height_warnings.append(warning)
                    try:
                        self._check_chart_tables(
                            frame, scene, state["id"], width, height_warnings
                        )
                        self._check_expanded_panels(
                            frame, state["id"], width, height_warnings
                        )
                    except BrowserLayoutError as exc:
                        diagnostics.extend(exc.layout_diagnostics)
                        messages.append(str(exc))
        if diagnostics:
            raise BrowserLayoutError("; ".join(messages[:8]), diagnostics)

    @staticmethod
    def _check_expanded_panels(frame, state_id, width, height_warnings):
        """Native details can coexist; inspect their maximal visible combination."""
        available = frame.locator(
            "#scene-content figure.scene-chart[data-chart-for] > details.scene-chart-details, "
            "#scene-change-summary > details.scene-change-details, #scene-extra-details"
        )
        panels = [
            (details, details.get_attribute("open") is not None)
            for details in available.all()
            if details.is_visible()
        ]
        if len(panels) < 2:
            return 0
        try:
            for details, was_open in panels:
                if was_open:
                    continue
                summary = details.locator(":scope > summary")
                if summary.count() != 1 or not summary.is_visible():
                    raise ValueError("동시 확장할 설명 패널의 키보드 조작이 없음")
                summary.focus()
                summary.press("Enter")
                if details.get_attribute("open") is None:
                    raise ValueError("설명 패널을 키보드로 동시에 펼칠 수 없음")
            for details, _ in panels:
                values = details.locator(
                    "table.scene-chart-table, .scene-change-row, #scene-status"
                )
                if not values.count():
                    raise ValueError("동시에 펼친 설명 패널에 원래 값이 없음")
                for value in values.all():
                    if not value.is_visible():
                        raise ValueError(
                            "동시에 펼친 설명 패널의 원래 값이 표시되지 않음"
                        )
                    BrowserSceneVerifier._check_text_visibility(
                        value, "동시에 펼친 설명"
                    )
            warning = BrowserSceneVerifier._check_height(
                frame.locator("body").evaluate("body => body.scrollHeight"),
                width,
                state_id,
                "expanded-all",
                frame=frame,
            )
            if warning and warning not in height_warnings:
                height_warnings.append(warning)
        except BrowserLayoutError:
            raise
        except ValueError as exc:
            detail = str(exc)
            violation = (
                "tiny"
                if "tiny-text" in detail
                else "overflow"
                if "offscreen-text" in detail
                else "clipped"
                if "clipped-text" in detail
                else "hidden"
            )
            raise BrowserLayoutError(
                detail,
                [
                    observe_layout(
                        frame,
                        state_id,
                        "expanded-all",
                        [violation],
                        SCENE_HEIGHT_LIMIT_PX,
                    )
                ],
            ) from exc
        finally:
            for details, was_open in reversed(panels):
                if (details.get_attribute("open") is not None) != was_open:
                    summary = details.locator(":scope > summary")
                    summary.focus()
                    summary.press("Enter")
        if any(
            (details.get_attribute("open") is not None) != was_open
            for details, was_open in panels
        ):
            raise ValueError("동시에 펼친 설명 패널의 원래 접힘 상태를 복원할 수 없음")
        return 1

    @staticmethod
    def _check_chart_tables(frame, scene, state_id, width, height_warnings):
        """A numerical fallback is real accessible content, not a hidden claim."""
        for chart in scene.get("charts", []):
            root = frame.locator(
                f'figure.scene-chart[data-chart-for="{chart["entity"]}"]'
            )
            if (
                root.count() != 1
                or not root.is_visible()
                or root.get_attribute("data-chart-state") != state_id
            ):
                raise ValueError("수치 차트가 현재 상태의 설명 대상에 표시되지 않음")
            verify_chart_graphics(root, chart, state_id)
            details = root.locator(":scope > details.scene-chart-details")
            summary = details.locator(":scope > summary")
            if (
                details.count() != 1
                or summary.count() != 1
                or not summary.is_visible()
                or summary.inner_text().strip()
                not in {"정확한 수치 표 보기", "관측 지점 번호와 정확한 수치 표 보기"}
            ):
                raise ValueError("수치 차트의 정확한 값 표를 여는 조작이 없음")
            was_open = details.get_attribute("open") is not None
            if not was_open:
                summary.focus()
                summary.press("Enter")
            try:
                table = details.locator("table.scene-chart-table")
                if (
                    details.get_attribute("open") is None
                    or table.count() != 1
                    or not table.is_visible()
                ):
                    raise ValueError("수치 표를 키보드로 펼쳐 읽을 수 없음")
                BrowserSceneVerifier._check_text_visibility(table, "수치 차트 표")
                warning = BrowserSceneVerifier._check_height(
                    root.evaluate("() => document.body.scrollHeight"),
                    width,
                    state_id,
                    "expanded-chart",
                    frame=frame,
                )
                if warning and warning not in height_warnings:
                    height_warnings.append(warning)
            finally:
                if not was_open and details.get_attribute("open") is not None:
                    summary.press("Enter")
            if (details.get_attribute("open") is not None) != was_open:
                raise ValueError("수치 표의 접힘 상태를 키보드로 복원할 수 없음")

    def _launch(self, playwright):
        options = {"headless": True}
        if executable := os.environ.get("DESIGN_CHROMIUM_EXECUTABLE"):
            options["executable_path"] = executable
        return playwright.chromium.launch(**options)

    def preflight(self) -> None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                self._launch(playwright).close()
        except Exception as exc:
            raise BrowserUnavailable(
                "브라우저 검사기 미설치/실행 불가 — python -m playwright install chromium 필요"
            ) from exc

    def check(self, scene: dict, document: str) -> dict:
        from playwright.sync_api import sync_playwright

        paths = state_paths(scene)
        checked = 0
        clarity_checked = 0
        additional_descriptions_checked = 0
        height_warnings = []
        with sync_playwright() as playwright:
            browser = self._launch(playwright)
            try:
                requests, errors = [], []
                visual_changes = 0
                with self._scene_page(
                    browser, document, errors, requests, reduced_motion="reduce"
                ) as (page, frame):
                    # Hidden content must reach the explicit visibility checks,
                    # rather than time out while waiting for a visible element.
                    frame.locator("#scene-content[data-state]").wait_for(
                        state="attached"
                    )
                    self._check_settled_layouts(
                        page, frame, scene, paths, height_warnings
                    )
                    for width in (320, 700):
                        page.set_viewport_size({"width": width + 16, "height": 1200})
                        for state in scene["states"]:

                            def navigate():
                                if len(scene["states"]) > 1:
                                    frame.locator("#scene-reset").click()
                                for index in paths[state["id"]]:
                                    frame.locator(
                                        f'button[data-action="{index}"]'
                                    ).click()

                            navigate()
                            if (
                                frame.locator("#scene-content").get_attribute(
                                    "data-state"
                                )
                                != state["id"]
                            ):
                                raise ValueError("상태 이동 실패")
                            for index, action in enumerate(state["actions"]):
                                navigate()
                                button = frame.locator(f'button[data-action="{index}"]')
                                before = frame.locator("#scene-content").screenshot()
                                self._check_change_origin(
                                    frame, scene, state["id"], action["target"]
                                )
                                button.focus()
                                button.press("Enter")
                                if (
                                    frame.locator("#scene-content").get_attribute(
                                        "data-state"
                                    )
                                    != action["target"]
                                ):
                                    raise ValueError("버튼 전이 실패")
                                if (
                                    before
                                    == frame.locator("#scene-content").screenshot()
                                ):
                                    raise ValueError(
                                        "버튼은 작동하지만 시각화 화면에 변화가 없음"
                                    )
                                clarity_checked += self._check_change_summary(
                                    frame,
                                    scene,
                                    state["id"],
                                    action["target"],
                                    width,
                                    height_warnings,
                                )
                                additional_descriptions_checked += (
                                    self._check_additional_description(
                                        frame,
                                        scene,
                                        state["id"],
                                        action["target"],
                                        width,
                                        height_warnings,
                                    )
                                )
                                visual_changes += 1
                                checked += 1
                        self._check_playback(page, frame, scene)
                    if errors or requests:
                        raise ValueError(
                            f"브라우저 오류 또는 외부 요청 발생: {errors}, {len(requests)} requests"
                        )
                continuity = self._check_continuity(
                    browser, scene, document, errors, requests, height_warnings
                )
                if errors or requests:
                    raise ValueError(
                        f"브라우저 오류 또는 외부 요청 발생: {errors}, {len(requests)} requests"
                    )
            finally:
                browser.close()
        return {
            "widths": [320, 700],
            "states": len(scene["states"]),
            "transitions_checked": checked,
            "visible_changes_checked": visual_changes,
            "change_explanations_checked": clarity_checked,
            "additional_descriptions_checked": additional_descriptions_checked,
            "playback_steps": len(scene.get("playback", {}).get("steps", [])),
            "height_policy": {
                "target_px": SCENE_HEIGHT_TARGET_PX,
                "limit_px": SCENE_HEIGHT_LIMIT_PX,
            },
            "warnings": height_warnings,
            **continuity,
        }

    def _check_continuity(
        self, browser, scene, document, errors, requests, height_warnings
    ):
        """Inspect actual in-flight geometry, not merely two different screenshots."""
        transitions = scene.get("transitions", [])
        effects = scene.get("effects", [])
        result = {
            "moving_steps_checked": 0,
            "state_effects_checked": 0,
            "scenario_routes_checked": 0,
        }
        if not transitions and not effects:
            return result
        with self._scene_page(
            browser, document, errors, requests, reduced_motion="no-preference"
        ) as (page, frame):
            content = frame.locator("#scene-content")
            content.locator("[data-entity]").first.wait_for()
            states = {state["id"]: state for state in scene["states"]}
            paths = state_paths(scene)
            for width in (320, 700):
                page.set_viewport_size({"width": width + 16, "height": 1200})
                # Explicit reset also opts out of the initial automatic run.
                frame.locator("#scene-reset").click()
                for transition in transitions:
                    # Reach the origin instantly, then inspect only this edge in
                    # normal motion. A saved/restored DOM is not a test fixture.
                    page.emulate_media(reduced_motion="reduce")
                    frame.locator("#scene-reset").click()
                    for index in paths[transition["from"]]:
                        frame.locator(f'button[data-action="{index}"]').click()
                    page.emulate_media(reduced_motion="no-preference")
                    action_index = next(
                        index
                        for index, action in enumerate(
                            states[transition["from"]]["actions"]
                        )
                        if action["target"] == transition["to"]
                    )
                    action = frame.locator(f'button[data-action="{action_index}"]')
                    action.focus()
                    action.press("Enter")
                    for step_index, step in enumerate(transition["steps"]):
                        token = content.locator(".scene-transfer-token")
                        self._assert_in_flight(content, transition["from"])
                        if (
                            token.count() != 1
                            or token.get_attribute("data-source") != step["source"]
                            or token.get_attribute("data-target") != step["target"]
                            or token.inner_text().strip() != step["label"]
                        ):
                            raise ValueError(
                                f"{width}px / {transition['from']} 이동 객체와 선언된 경로가 다름"
                            )
                        source = self._center(
                            content.locator(f'[data-entity="{step["source"]}"]')
                        )
                        target = self._center(
                            content.locator(f'[data-entity="{step["target"]}"]')
                        )
                        path_length = math.dist(source, target)
                        if path_length < 16:
                            raise ValueError(
                                f"{width}px / {transition['from']} 출발·도착 위치가 겹쳐 이동을 읽을 수 없음"
                            )
                        quarter = round(step["duration_ms"] * 0.25)
                        middle = round(step["duration_ms"] * 0.35)
                        page.clock.run_for(quarter)
                        warning = self._check_height(
                            content.evaluate("() => document.body.scrollHeight"),
                            width,
                            transition["from"],
                            "moving",
                            frame=frame,
                        )
                        if warning and warning not in height_warnings:
                            height_warnings.append(warning)
                        before = self._center(token)
                        self._assert_in_flight(content, transition["from"])
                        page.clock.run_for(middle)
                        after = self._center(token)
                        self._assert_in_flight(content, transition["from"])
                        if (
                            math.dist(before, after) < 2
                            or math.dist(after, target) >= math.dist(before, target) - 1
                        ):
                            raise ValueError(
                                f"{width}px / {transition['from']} 실제 전달 이동 없음 — 색상·테두리 변경만으로는 통과할 수 없음"
                            )
                        result["moving_steps_checked"] += 1
                        page.clock.run_for(step["duration_ms"] - quarter - middle)
                        # RAF completion can land one frame after the requested
                        # duration. Only advance to this step's exact boundary.
                        for _ in range(8):
                            current_step = (
                                token.get_attribute("data-step")
                                if token.count()
                                else None
                            )
                            if content.get_attribute(
                                "data-phase"
                            ) == "settled" or current_step != str(step_index):
                                break
                            page.clock.run_for(16)
                    if (
                        content.get_attribute("data-state") != transition["to"]
                        or content.get_attribute("data-phase") != "settled"
                        or content.locator(".scene-transfer-token").count()
                    ):
                        raise ValueError(
                            "전달 도착 후 결과가 반영되지 않거나 이동 객체가 남아 있음"
                        )
                for effect in effects:
                    page.emulate_media(reduced_motion="reduce")
                    frame.locator("#scene-reset").click()
                    for index in paths[effect["from"]]:
                        frame.locator(f'button[data-action="{index}"]').click()
                    page.emulate_media(reduced_motion="no-preference")
                    entities = [
                        content.locator(f'[data-entity="{entity}"]')
                        for entity in effect["entities"]
                    ]
                    before_text = [entity.inner_text().strip() for entity in entities]
                    before_height = [
                        entity.bounding_box()["height"] for entity in entities
                    ]
                    index = next(
                        index
                        for index, action in enumerate(
                            states[effect["from"]]["actions"]
                        )
                        if action["target"] == effect["to"]
                    )
                    button = frame.locator(f'button[data-action="{index}"]')
                    button.focus()
                    button.press("Enter")
                    self._assert_in_flight(content, effect["from"])
                    if content.locator(".scene-transfer-token").count():
                        raise ValueError("비전송 효과가 존재하지 않는 전달을 그림")
                    quarter = round(effect["duration_ms"] * 0.25)
                    middle = round(effect["duration_ms"] * 0.35)
                    page.clock.run_for(quarter)
                    appearance = "el => {const s=getComputedStyle(el), r=el.getBoundingClientRect(); return [s.opacity,s.translate,r.height];}"
                    first = [entity.evaluate(appearance) for entity in entities]
                    for entity in entities:
                        self._center(entity)
                    page.clock.run_for(middle)
                    self._assert_in_flight(content, effect["from"])
                    second = [entity.evaluate(appearance) for entity in entities]
                    if any(a == b for a, b in zip(first, second)):
                        raise ValueError(
                            "실제 내용 전환 애니메이션 없음 — 테두리 변화만으로는 통과할 수 없음"
                        )
                    warning = self._check_height(
                        content.evaluate("() => document.body.scrollHeight"),
                        width,
                        effect["from"],
                        "moving",
                        frame=frame,
                    )
                    if warning and warning not in height_warnings:
                        height_warnings.append(warning)
                    page.clock.run_for(effect["duration_ms"] - quarter - middle + 128)
                    if (
                        content.get_attribute("data-state") != effect["to"]
                        or content.get_attribute("data-phase") != "settled"
                        or content.locator(".scene-effect-layer").count()
                    ):
                        raise ValueError("상태 효과 완료 후 결과 미반영 또는 잔상 존재")
                    if any(
                        entity.inner_text().strip() == old
                        for entity, old in zip(entities, before_text)
                    ):
                        raise ValueError(
                            "상태 효과가 실제 읽을 수 있는 내용을 바꾸지 않음"
                        )
                    if effect["kind"] == "reveal" and not any(
                        abs(entity.bounding_box()["height"] - old) > 2
                        for entity, old in zip(entities, before_height)
                    ):
                        raise ValueError(
                            "reveal은 실제 펼치거나 접히는 화면 높이 변화 필요"
                        )
                    result["state_effects_checked"] += 1
                for scenario in scene.get("scenarios", []):
                    selector = frame.locator(
                        f'#scene-scenarios button[data-scenario="{scenario["id"]}"]'
                    )
                    selector.focus()
                    selector.press("Enter")
                    if selector.get_attribute("data-scenario-action") == "true":
                        origin, destination = scenario["steps"]
                        edge = next(
                            (
                                edge
                                for edge in transitions
                                if edge["from"] == origin and edge["to"] == destination
                            ),
                            None,
                        )
                        duration = (
                            sum(step["duration_ms"] for step in edge["steps"])
                            if edge
                            else 0
                        )
                        duration += next(
                            (
                                effect["duration_ms"]
                                for effect in effects
                                if effect["from"] == origin
                                and effect["to"] == destination
                            ),
                            0,
                        )
                        page.clock.run_for(duration + 128)
                        if (
                            content.get_attribute("data-state") != destination
                            or selector.get_attribute("aria-pressed") != "true"
                        ):
                            raise ValueError(
                                "단일 단계 선택이 결과를 즉시 실행하거나 선택 상태를 반영하지 않음"
                            )
                        if (
                            frame.locator("#scene-play").get_attribute("aria-pressed")
                            != "false"
                        ):
                            raise ValueError(
                                "단일 단계 선택 완료 후 자동 재생이 계속됨"
                            )
                        self._check_change_summary(
                            frame, scene, origin, destination, width, height_warnings
                        )
                        page.clock.run_for(
                            scene.get("playback", {}).get("interval_ms", 3000) * 2
                        )
                        if content.get_attribute("data-state") != destination:
                            raise ValueError("선택한 결과가 의도치 않게 바뀜")
                        result["scenario_routes_checked"] += 1
                        continue
                    if (
                        content.get_attribute("data-state") != scenario["steps"][0]
                        or selector.get_attribute("aria-pressed") != "true"
                    ):
                        raise ValueError(
                            "시나리오를 키보드로 선택하거나 처음 상태로 이동할 수 없음"
                        )
                    frame.locator("#scene-play").click()
                    interval = scene.get("playback", {}).get("interval_ms", 3000)
                    for origin, destination in zip(
                        scenario["steps"], scenario["steps"][1:]
                    ):
                        edge = next(
                            (
                                edge
                                for edge in transitions
                                if edge["from"] == origin and edge["to"] == destination
                            ),
                            None,
                        )
                        duration = (
                            sum(step["duration_ms"] + 32 for step in edge["steps"])
                            if edge
                            else 0
                        )
                        duration += next(
                            (
                                effect["duration_ms"]
                                for effect in effects
                                if effect["from"] == origin
                                and effect["to"] == destination
                            ),
                            0,
                        )
                        page.clock.run_for(interval + duration + 32)
                        if content.get_attribute("data-state") != destination:
                            raise ValueError("선택한 시나리오의 전달 경로 실행 실패")
                    if (
                        frame.locator("#scene-play").get_attribute("aria-pressed")
                        != "false"
                    ):
                        raise ValueError("시나리오가 마지막 단계에서 멈추지 않음")
                    page.clock.run_for(interval * 2)
                    if content.get_attribute("data-state") != scenario["steps"][-1]:
                        raise ValueError("완료된 시나리오가 의도치 않게 반복됨")
                    result["scenario_routes_checked"] += 1
        return result

    @staticmethod
    def _check_visible_entity_value(frame, identifier, value, phase):
        entity = frame.locator(f'#scene-content [data-entity="{identifier}"]')
        if (
            entity.count() != 1
            or not entity.is_visible()
            or " ".join(value.split()) not in " ".join(entity.inner_text().split())
        ):
            raise ValueError(
                f"{phase} 값이 실제 설명 대상 {identifier}에 표시되지 않음"
            )
        BrowserSceneVerifier._check_text_visibility(entity, f"{phase} 값 {identifier}")

    @staticmethod
    def _check_text_visibility(entity, label):
        # is_visible() ignores transparent paint and clipped glyphs. Check the
        # actual text nodes, including inherited styles, rather than trusting a
        # visible wrapper box or textContent echoed into the comparison ledger.
        observation = entity.evaluate("""entity => {
          function alpha(color) {
            if (color === 'transparent') return 0;
            const match = color.match(/(?:rgba|hsla)\\([^)]*,\\s*([\\d.]+)(%)?\\s*\\)$/) || color.match(/\\/\\s*([\\d.]+)(%)?\\s*\\)$/);
            return match ? Number(match[1]) / (match[2] ? 100 : 1) : 1;
          }
          const walker = document.createTreeWalker(entity, NodeFilter.SHOW_TEXT);
          let count = 0;
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (!node.nodeValue.trim()) continue;
            const parent = node.parentElement;
            const style = getComputedStyle(parent);
            if (alpha(style.color) === 0 || alpha(style.webkitTextFillColor) === 0) return 'transparent-text';
            if (parseFloat(style.fontSize) < 12) return 'tiny-text';
            const range = document.createRange();
            range.selectNodeContents(node);
            const boxes = [...range.getClientRects()].filter(box => box.width > 0 && box.height > 0);
            if (!boxes.length) return 'no-painted-glyph-area';
            if (boxes.some(box => box.left < -1 || box.right > innerWidth + 1)) return 'offscreen-text';
            for (let ancestor = parent; ancestor; ancestor = ancestor.parentElement) {
              const appearance = getComputedStyle(ancestor), bounds = ancestor.getBoundingClientRect();
              if (appearance.display === 'none' || appearance.visibility !== 'visible' ||
                  appearance.contentVisibility === 'hidden' || Number(appearance.opacity) === 0 ||
                  /(?:^|\\s)opacity\\(\\s*0(?:\\.0+)?%?\\s*\\)/.test(appearance.filter)) return 'hidden-text-ancestor';
              if (['hidden', 'clip', 'scroll', 'auto'].includes(appearance.overflowX) &&
                  boxes.some(box => box.left < bounds.left - 1 || box.right > bounds.right + 1)) return 'clipped-text-x';
              if (['hidden', 'clip', 'scroll', 'auto'].includes(appearance.overflowY) &&
                  boxes.some(box => box.top < bounds.top - 1 || box.bottom > bounds.bottom + 1)) return 'clipped-text-y';
            }
            count += 1;
          }
          return count ? 'readable' : 'no-text-nodes';
        }""")
        if observation != "readable":
            raise ValueError(
                f"{label}의 실제 텍스트가 숨겨지거나 잘려서 읽을 수 없음: {observation}"
            )

    @staticmethod
    def _check_additional_description(
        frame, scene, origin, destination, width, height_warnings
    ):
        explanation = next(
            (
                item
                for item in scene.get("change_explanations", [])
                if item["from"] == origin and item["to"] == destination
            ),
            None,
        )
        if explanation is None:
            return 0
        description = next(
            state["description"]
            for state in scene["states"]
            if state["id"] == destination
        )
        status = frame.locator("#scene-status")
        if " ".join(description.split()) == " ".join(explanation["reason"].split()):
            if status.is_visible():
                raise ValueError("같은 설명 문장이 변경 이유와 상태 설명에 중복 표시됨")
            return 0
        details = frame.locator("#scene-extra-details")
        if (
            details.count() != 1
            or not details.is_visible()
            or details.get_attribute("open") is not None
        ):
            raise ValueError("추가 설명을 보존한 접기 조작이 기본 상태에 제공되지 않음")
        summary = details.locator("summary")
        if (
            summary.count() != 1
            or not summary.is_visible()
            or summary.inner_text().strip() != "추가 설명"
        ):
            raise ValueError("추가 설명을 여는 조작의 이름 또는 표시가 없음")
        summary.focus()
        summary.press("Enter")
        try:
            if (
                details.get_attribute("open") is None
                or not status.is_visible()
                or " ".join(status.inner_text().split())
                != " ".join(description.split())
            ):
                raise ValueError("펼친 추가 설명에서 원래 상태 설명을 읽을 수 없음")
            BrowserSceneVerifier._check_text_visibility(status, "추가 설명")
            warning = BrowserSceneVerifier._check_height(
                details.evaluate("() => document.body.scrollHeight"),
                width,
                destination,
                "expanded-description",
                frame=frame,
            )
            if warning and warning not in height_warnings:
                height_warnings.append(warning)
        finally:
            if details.get_attribute("open") is not None:
                summary.press("Enter")
        if details.get_attribute("open") is not None:
            raise ValueError("추가 설명을 키보드로 다시 접을 수 없음")
        return 1

    @staticmethod
    def _check_change_origin(frame, scene, origin, destination):
        explanation = next(
            (
                item
                for item in scene.get("change_explanations", [])
                if item["from"] == origin and item["to"] == destination
            ),
            None,
        )
        if explanation is None:
            return
        for item, value in [
            (change, change["before"]) for change in explanation["changes"]
        ] + [
            (invariant, invariant["value"]) for invariant in explanation["invariants"]
        ]:
            BrowserSceneVerifier._check_visible_entity_value(
                frame, item["entity"], value, "변경 전"
            )

    @staticmethod
    def _check_change_summary(
        frame, scene, origin, destination, width=None, height_warnings=None
    ):
        """A declared explanation must remain readable, not only exist in JSON."""
        explanation = next(
            (
                item
                for item in scene.get("change_explanations", [])
                if item["from"] == origin and item["to"] == destination
            ),
            None,
        )
        if explanation is None:
            return 0
        panel = frame.locator("#scene-change-summary")
        if panel.count() != 1 or not panel.is_visible():
            raise ValueError("변경 전후 비교가 화면에 표시되지 않음")
        if (
            panel.get_attribute("data-from") != origin
            or panel.get_attribute("data-to") != destination
        ):
            raise ValueError("변경 설명이 현재 선택한 상태와 다름")
        if panel.locator(".scene-change-row").count() != len(explanation["changes"]):
            raise ValueError("화면의 변경 필드 개수가 선언과 다름")
        primary = panel.locator(':scope > .scene-change-row[data-primary="true"]')
        details = panel.locator(":scope > details.scene-change-details")
        secondary_count = len(explanation["changes"]) - 1
        if primary.count() != 1 or not primary.is_visible():
            raise ValueError("핵심 변경 하나가 기본 화면에 표시되지 않음")
        if secondary_count:
            if (
                details.count() != 1
                or not details.is_visible()
                or details.get_attribute("open") is not None
                or details.locator('.scene-change-row[data-primary="false"]').count()
                != secondary_count
            ):
                raise ValueError(
                    "보조 변경을 보존한 접기 조작이 기본 상태에 제공되지 않음"
                )
            summary = details.locator(":scope > summary")
            if (
                summary.count() != 1
                or summary.inner_text().strip() != f"추가 변경 {secondary_count}개"
            ):
                raise ValueError("추가 변경을 여는 조작의 이름 또는 표시가 없음")
        elif details.count():
            raise ValueError("보조 변경이 없는데 비어 있는 접기 조작이 표시됨")
        if " ".join(
            panel.locator(".scene-change-reason").inner_text().split()
        ) != " ".join(explanation["reason"].split()):
            raise ValueError("변경 이유가 화면에서 확인되지 않음")
        if panel.locator(".scene-change-invariant").count() != len(
            explanation["invariants"]
        ):
            raise ValueError("유지되는 값이 화면에서 확인되지 않음")
        for index, invariant in enumerate(explanation["invariants"]):
            row = panel.locator(".scene-change-invariant").nth(index)
            if row.get_attribute("data-entity") != invariant["entity"]:
                raise ValueError("유지되는 필드가 선언된 대상과 다름")
            if " ".join(
                row.locator(".scene-change-invariant-value").inner_text().split()
            ) != " ".join(invariant["value"].split()):
                raise ValueError("유지되는 값의 표시가 선언과 다름")
            BrowserSceneVerifier._check_visible_entity_value(
                frame, invariant["entity"], invariant["value"], "유지되는"
            )
        BrowserSceneVerifier._check_summary_readability(panel)
        if secondary_count:
            summary.focus()
            summary.press("Enter")
        try:
            if secondary_count and details.get_attribute("open") is None:
                raise ValueError("추가 변경을 키보드로 펼칠 수 없음")
            # The primary row is selected for reading value, not input order.
            # Match all fields by stable entity ID, including the opened rows.
            for change in explanation["changes"]:
                row = panel.locator(
                    f'.scene-change-row[data-entity="{change["entity"]}"]'
                )
                if row.count() != 1:
                    raise ValueError("변경 필드가 선언된 대상과 다름")
                for selector, key in (
                    (".scene-change-label", "label"),
                    (".scene-change-before", "before"),
                    (".scene-change-after", "after"),
                ):
                    if row.locator(selector).count() != 1 or " ".join(
                        row.locator(selector).inner_text().split()
                    ) != " ".join(change[key].split()):
                        raise ValueError(
                            "변경 전 원본 또는 변경 후 값이 화면에서 보존되지 않음"
                        )
                    BrowserSceneVerifier._check_text_visibility(
                        row.locator(selector), "변경 필드"
                    )
                BrowserSceneVerifier._check_visible_entity_value(
                    frame, change["entity"], change["after"], "변경 후"
                )
            BrowserSceneVerifier._check_summary_readability(panel)
            if secondary_count:
                warning = BrowserSceneVerifier._check_height(
                    panel.evaluate("() => document.body.scrollHeight"),
                    width if width is not None else panel.evaluate("() => innerWidth"),
                    destination,
                    "expanded-changes",
                    frame=frame,
                )
                if (
                    warning
                    and height_warnings is not None
                    and warning not in height_warnings
                ):
                    height_warnings.append(warning)
        finally:
            if secondary_count and details.get_attribute("open") is not None:
                summary.press("Enter")
        if secondary_count and details.get_attribute("open") is not None:
            raise ValueError("추가 변경을 키보드로 다시 접을 수 없음")
        return 1

    @staticmethod
    def _check_summary_readability(panel):
        readable = panel.evaluate("""panel => {
          const elements = [panel, ...panel.querySelectorAll('*')].filter(el => {
            const closed = el.closest('details.scene-change-details:not([open])');
            return !closed || el === closed || el === closed.querySelector(':scope > summary');
          });
          return elements.every(el => {
            const style = getComputedStyle(el), box = el.getBoundingClientRect();
            if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) < .1) return false;
            if (box.width <= 0 || box.height <= 0 || box.left < -1 || box.right > innerWidth + 1) return false;
            if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) return false;
            return parseFloat(style.fontSize) >= 12;
          });
        }""")
        if not readable:
            raise ValueError(
                "변경 전후 비교 또는 이유가 숨겨지거나 잘려서 읽을 수 없음"
            )

    @staticmethod
    def _assert_in_flight(content, origin):
        if (
            content.get_attribute("data-state") != origin
            or content.get_attribute("data-phase") != "moving"
        ):
            raise ValueError("전달 도착 전에 결과 상태가 먼저 반영됨")

    @staticmethod
    def _center(locator):
        readable = locator.evaluate("""el => {
          const bounds = el.getBoundingClientRect();
          // A capped box can fit while a nowrap text node still extends beyond
          // it. The traveller's actual glyph rectangles must fit, not just its
          // border box; otherwise a long, schema-valid label gets cut off.
          if (el.classList.contains('scene-transfer-token')) {
            const range = document.createRange();
            range.selectNodeContents(el);
            if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1 ||
                [...range.getClientRects()].some(text =>
                  text.left < bounds.left - 1 || text.right > bounds.right + 1 ||
                  text.top < bounds.top - 1 || text.bottom > bounds.bottom + 1)) return false;
          }
          const ancestors = [];
          for (let node = el; node; node = node.parentElement) ancestors.push(node);
          return bounds.width > 0 && bounds.height > 0 &&
            bounds.left >= -1 && bounds.right <= innerWidth + 1 &&
            bounds.top >= -1 && bounds.bottom <= innerHeight + 1 &&
            ancestors.every(node => {
              const style = getComputedStyle(node);
              if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) < .1) return false;
              if (node === el) return parseFloat(style.fontSize) >= 12;
              const box = node.getBoundingClientRect();
              if (['hidden', 'clip', 'scroll', 'auto'].includes(style.overflowX) &&
                  (bounds.left < box.left - 1 || bounds.right > box.right + 1)) return false;
              if (['hidden', 'clip', 'scroll', 'auto'].includes(style.overflowY) &&
                  (bounds.top < box.top - 1 || bounds.bottom > box.bottom + 1)) return false;
              return true;
            });
        }""")
        if not readable:
            raise ValueError(
                "이동 객체 또는 전달 지점이 숨겨지거나 잘려서 읽을 수 없음"
            )
        bounds = locator.bounding_box()
        if not bounds or bounds["width"] <= 0 or bounds["height"] <= 0:
            raise ValueError("이동 객체 또는 전달 지점이 화면에 보이지 않음")
        point = (bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
        if not all(math.isfinite(value) for value in point):
            raise ValueError("전달 경로 좌표가 유효하지 않음")
        return point

    @staticmethod
    @contextmanager
    def _scene_page(browser, document, errors, requests, *, reduced_motion):
        """Same isolated frame for static and moving checks; always close on failure."""
        context = browser.new_context(
            reduced_motion=reduced_motion, service_workers="block"
        )
        try:
            context.route(
                "**/*",
                lambda route: (requests.append(route.request.url), route.abort()),
            )
            page = context.new_page()
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            page.clock.install(time=start)
            page.clock.pause_at(start + timedelta(seconds=1))
            page.set_default_timeout(2000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(
                '<iframe id="test-scene" sandbox="allow-scripts" '
                'style="width:100%;height:1100px;border:0" '
                f'srcdoc="{html.escape(document, quote=True)}"></iframe>'
            )
            yield page, page.frame_locator("#test-scene")
        finally:
            context.close()

    @staticmethod
    def _check_playback(page, frame, scene):
        playback = scene.get("playback", {"steps": []})
        if playback["steps"]:
            frame.locator("#scene-reset").click()
            frame.locator("#scene-play").click()
            for sid in playback["steps"][1:]:
                page.clock.run_for(playback["interval_ms"])
                if frame.locator("#scene-content").get_attribute("data-state") != sid:
                    raise ValueError("자동 재생 경로 실행 실패")
            if frame.locator("#scene-play").get_attribute("aria-pressed") != "false":
                raise ValueError("자동 재생이 마지막 단계에서 멈추지 않음")
            page.clock.run_for(playback["interval_ms"] * 2)
            if (
                frame.locator("#scene-content").get_attribute("data-state")
                != playback["steps"][-1]
            ):
                raise ValueError("자동 재생이 의도치 않게 반복됨")
