"""Reusable fictional inputs and test doubles; never test cases."""

from __future__ import annotations

import copy
import json
import tempfile
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import generator.tools.local_preview as local_preview
from generator.contracts import Article
from generator.design.compact_scenes import compile_compact_design
from generator.design.evidence_repair import source_excerpts
from generator.design.scene_document import section_ends
from generator.design.visual_contracts import source_sections
from generator.tests.fixtures.design import (
    COMPACT_BODY,
    COMPACT_SOURCES,
    DESIGN_BODY,
    DESIGN_SOURCES,
    compact_candidate,
    design_article,
    design_candidate,
)

PASS = {"verdict": "pass", "issues": [], "previous_issues": []}


def resume_config(**changes):
    return {
        "design_enabled": True,
        "design_required": True,
        "design_interaction_required": True,
        "design_generation_format": "compact",
        "design_model_fallback": ["writer"],
        "design_review_model_fallback": ["reviewer"],
        "design_max_revisions": 1,
        **changes,
    }


def resume_article():
    return Article("정책", COMPACT_BODY, "original", (), ())


def compile_resume_candidate(value):
    headings = {
        f"section_{index}": heading
        for index, heading in enumerate(section_ends(COMPACT_BODY), 1)
    }
    return compile_compact_design(
        value, headings, source_excerpts(source_sections(COMPACT_SOURCES))
    )


def write_saved_snapshot(root, *, compact=True):
    root.mkdir()
    value = compact_candidate()
    expanded = compile_resume_candidate(value)
    inputs = {
        "sources": COMPACT_SOURCES,
        "current_official_sections": source_sections(COMPACT_SOURCES),
        "article_title": "정책",
        "article": COMPACT_BODY,
        "tags": [],
        "headings": list(section_ends(COMPACT_BODY)),
    }
    contents = {
        "input.json": inputs,
        "1-candidate.json": expanded,
        "1-designer-response.json": {
            "content": json.dumps(value if compact else expanded),
            "model": "writer",
        },
        "result.json": {"status": "held", "author_models": ["writer"], "attempts": 1},
    }
    if compact:
        contents["1-compact.json"] = value
    for name, content in contents.items():
        (root / name).write_text(
            json.dumps(content, ensure_ascii=False), encoding="utf-8"
        )
    return value


def write_run_file(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def run_fixture(
    root,
    name,
    *,
    article="같은 본문",
    model="same-model",
    provider="provider-a",
    effort="low",
    status="held",
    cost=0.01,
):
    run = root / name
    run.mkdir()
    inputs = {
        "article": article,
        "article_title": "예시",
        "current_official_sections": [
            {"url": "https://example.test/docs", "content": "공식 원문"}
        ],
    }
    write_run_file(run / "input.json", inputs)
    write_run_file(
        run / "result.json",
        {
            "status": status,
            "stage": "complete" if status == "pass" else "design_validation",
            "attempts": 1,
            "design_model": model,
        },
    )
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 30,
        "completion_tokens_details": {"reasoning_tokens": 10},
        "prompt_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 0},
    }
    if cost is not None:
        usage["cost"] = cost
    write_run_file(
        run / "1-designer-http-1.json",
        {
            "model": model,
            "provider": provider,
            "status": "valid",
            "content": "{}",
            "elapsed_seconds": 4.5,
            "usage": usage,
            "request_parameters": {"reasoning": {"effort": effort, "exclude": True}},
        },
    )
    write_run_file(
        run / "usage.json",
        [
            {
                "artifact": "1-designer-http-1.json",
                "purpose": "designer",
                "model": model,
                "status": "valid",
                "usage": usage,
            }
        ],
    )
    write_run_file(
        run / "1-candidate.json",
        {"summary": "검사 대상", "scenes": [{"states": [{"html": "<p>설명</p>"}]}]},
    )
    write_run_file(
        run / "1-browser.json",
        [
            {
                "widths": [320, 700],
                "moving_steps_checked": 4,
                "scenario_routes_checked": 2,
            }
        ],
    )
    write_run_file(
        run / "1-validation-issues.json", [{"kind": "evidence"}, {"kind": "evidence"}]
    )
    (run / "designer-prompt.md").write_text("designer", encoding="utf-8")
    (run / "reviewer-prompt.md").write_text("reviewer", encoding="utf-8")
    return run


def broken_candidate():
    value = design_candidate()
    value["scenes"][0]["explanation"]["evidence"][0]["quote"] = "요약해서 바꾼 문장"
    return value


def repair_response(excerpt_id="source-1-excerpt-1"):
    return json.dumps(
        {"patches": [{"scene_index": 0, "evidence_index": 0, "excerpt_id": excerpt_id}]}
    )


def interactive_candidate():
    value = design_candidate()
    scene = value["scenes"][0]
    initial = scene["states"][0]
    initial["actions"] = [
        {"label": "첫 조건", "target": "first"},
        {"label": "다른 조건", "target": "second"},
    ]
    scene["states"] = [initial]
    for sid, text in [("first", "첫 결과"), ("second", "다른 결과")]:
        state = copy.deepcopy(initial)
        state.update(id=sid, description=text, actions=[])
        scene["states"].append(state)
    for state in scene["states"]:
        state["html"] = (
            '<div class="board"><p data-entity="broker">발신자</p>'
            '<p data-entity="receiver">수신자</p>'
            f"<p>{state['description']}</p></div>"
        )
    scene["transitions"] = [
        {
            "from": "start",
            "to": sid,
            "steps": [
                {
                    "source": "broker",
                    "target": "receiver",
                    "label": "요청",
                    "duration_ms": 1200,
                }
            ],
        }
        for sid in ("first", "second")
    ]
    scene["scenarios"] = [
        {"id": sid, "label": sid, "steps": ["start", sid]}
        for sid in ("first", "second")
    ]
    scene["playback"]["steps"] = ["start", "first"]
    return value


@contextmanager
def saved_run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "input.json").write_text(
            json.dumps({"article_title": "확인 <설명>", "article": DESIGN_BODY})
        )
        (root / "2-candidate.json").write_text(json.dumps(design_candidate()))
        yield root


@contextmanager
def preview_server(root):
    with ThreadingHTTPServer(
        ("127.0.0.1", 0), local_preview.make_handler(root, "test")
    ) as http:
        worker = Thread(
            target=http.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        worker.start()
        try:
            yield f"http://127.0.0.1:{http.server_port}"
        finally:
            http.shutdown()
            worker.join(timeout=2)


def two_scenes():
    value = design_candidate()
    second = copy.deepcopy(value["scenes"][0])
    second.update(title="별도 설명", after_heading="개요")
    value["scenes"].append(second)
    return value


def scene_repair_inputs():
    article = design_article()
    return {
        "article_title": article.title,
        "tags": list(article.tags),
        "article": article.body,
        "headings": list(section_ends(article.body)),
        "sources": DESIGN_SOURCES,
        "current_official_sections": source_sections(DESIGN_SOURCES),
    }


def break_entities(value, index=0):
    for state in value["scenes"][index]["states"]:
        state["html"] = state["html"].replace(' data-entity="broker"', "")
