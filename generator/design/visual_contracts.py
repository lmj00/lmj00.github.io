"""Topic-independent visual and review contracts."""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET

from jsonschema import Draft202012Validator, ValidationError

from generator.contracts import ModelGatewayError
from generator.design.scene_charts import SCENE_CHARTS_SCHEMA


def _object(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _text(limit, *, empty=False):
    return {"type": "string", "minLength": 0 if empty else 1, "maxLength": limit}


def _array(items, minimum, maximum):
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


REVIEW_SCHEMA = _object(
    verdict={"type": "string", "enum": ["pass", "revise"]},
    issues=_array(
        _object(
            id={**_text(30), "pattern": "^I[1-9][0-9]*$"},
            target={"type": "string", "enum": ["content", "renderer"]},
            path=_text(200),
            kind={"type": "string", "enum": ["factual", "readability", "visual"]},
            problem=_text(700),
            suggestion=_text(700),
            source_url=_text(500, empty=True),
            source_quote=_text(700, empty=True),
        ),
        0,
        8,
    ),
    previous_issues=_array(
        _object(
            id={**_text(30), "pattern": "^I[1-9][0-9]*$"},
            status={"type": "string", "enum": ["resolved", "unresolved", "withdrawn"]},
            reason=_text(700),
        ),
        0,
        8,
    ),
)


EXPLANATION_SCHEMA = _object(
    mode={"type": "string", "enum": ["static", "interactive"]},
    learning_goal=_text(180),
    reader_action=_text(180),
    observable_change=_text(240),
    takeaway=_text(180),
    assumptions=_array(_text(180), 0, 3),
    key_entities=_array({**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"}, 1, 6),
    evidence=_array(_object(source_url=_text(500), quote=_text(500)), 1, 3),
)


SCENE_TRANSITIONS_SCHEMA = _array(
    _object(
        **{
            "from": {**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            "to": {**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            "steps": _array(
                _object(
                    source={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
                    target={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
                    label={
                        **_text(40),
                        "description": "Plain text, never executable HTML.",
                    },
                    duration_ms={"type": "integer", "minimum": 600, "maximum": 2400},
                ),
                1,
                4,
            ),
        }
    ),
    0,
    32,
)
# Older scenes have no kind; the trusted renderer treats those tokens as messages.
SCENE_TRANSITIONS_SCHEMA["items"]["properties"]["steps"]["items"]["properties"][
    "kind"
] = {
    "type": "string",
    "enum": ["signal", "message"],
    "description": "Control/acknowledgement signal versus transferred message/data.",
}

SCENE_PRESENTATION_SCHEMA = _object(
    layout={"type": "string", "enum": ["flow", "branch"]},
    eyebrow=_text(48),
    links=_array(
        _object(
            source={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            target={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            label=_text(32),
        ),
        1,
        3,
    ),
)

SCENE_EFFECTS_SCHEMA = _array(
    _object(
        **{
            "from": {**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            "to": {**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            "kind": {"type": "string", "enum": ["compare", "transform", "reveal"]},
            "entities": {
                **_array({**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"}, 1, 6),
                "uniqueItems": True,
            },
            "duration_ms": {"type": "integer", "minimum": 600, "maximum": 2400},
        }
    ),
    0,
    32,
)

SCENE_SCENARIOS_SCHEMA = _array(
    _object(
        id={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
        label=_text(40),
        steps={
            **_array({**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"}, 2, 8),
            "uniqueItems": True,
        },
    ),
    2,
    3,
)


def _clarity_text(limit):
    return {
        **_text(limit),
        "pattern": r"^(?=[\s\S]*\S)(?![\s\S]*<\s*(?:/?[A-Za-z][\w:-]*(?:\s|/?>)|!))[\s\S]+$",
        "description": "Short plain text, never HTML. Values must match actual entity text.",
    }


SCENE_CHANGE_EXPLANATIONS_SCHEMA = _array(
    _object(
        **{
            "from": {**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            "to": {**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            "reason": _clarity_text(240),
            "changes": _array(
                _object(
                    entity={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
                    label=_clarity_text(60),
                    before=_clarity_text(120),
                    after=_clarity_text(120),
                ),
                1,
                3,
            ),
            "invariants": _array(
                _object(
                    entity={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
                    label=_clarity_text(60),
                    value=_clarity_text(120),
                ),
                1,
                2,
            ),
        }
    ),
    1,
    16,
)


DESIGN_SCHEMA = _object(
    summary=_text(600),
    scenes=_array(
        _object(
            title=_text(100),
            after_heading=_text(150),
            caption=_text(700),
            explanation=EXPLANATION_SCHEMA,
            css=_text(14000),
            initial={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
            playback=_object(
                steps=_array(_text(32), 0, 8),
                interval_ms={"type": "integer", "minimum": 1500, "maximum": 6000},
            ),
            states=_array(
                _object(
                    id={**_text(32), "pattern": "^[a-z][a-z0-9_-]*$"},
                    html=_text(7000),
                    description=_text(700),
                    actions=_array(_object(label=_text(60), target=_text(32)), 0, 4),
                ),
                1,
                8,
            ),
        ),
        1,
        2,
    ),
)

# Optional additions keep previously generated state-only scenes readable. New
# production interaction requirements are checked separately from this schema.
DESIGN_SCHEMA["properties"]["scenes"]["items"]["properties"].update(
    transitions=SCENE_TRANSITIONS_SCHEMA,
    effects=SCENE_EFFECTS_SCHEMA,
    scenarios=SCENE_SCENARIOS_SCHEMA,
    presentation=SCENE_PRESENTATION_SCHEMA,
    interaction_mode={"type": "string", "enum": ["compare", "process", "explore"]},
    change_explanations=SCENE_CHANGE_EXPLANATIONS_SCHEMA,
    charts=SCENE_CHARTS_SCHEMA,
)

RUNTIME_CONTRACT = {
    "charts": "Optional subject-specific line/bar charts take finite numeric series, labels, units and per-state views, never generated SVG/JS. Trusted graphics and a keyboard-accessible numeric table are inserted beside a readable HTML host; that host and the original HTML evidence remain intact. All views use the same zero-inclusive scale across every series. Compare/explore keep all points visible and only emphasize selected series; progressive point disclosure is reserved for a source-supported process. Numeric consistency is not proof that illustrative values or mechanisms are source-grounded. Review exact values, caption assumptions, units, labels and state views as well as HTML.",
    "change_explanations": "Optional legacy-compatible action-edge explanations identify 1–3 exact visible before/after values, 1–2 values that remain unchanged, and the reason. New clarity-enabled interactive scenes require them for every non-self action. The compiler checks whitespace-normalized substrings against the corresponding named data-entity DOM text, real changed text, and effect targets; this is not factual or browser-visibility verification. Labels and reasons remain source-reviewed. The trusted renderer preserves a before/after summary without evaluating HTML in these fields.",
    "interaction_mode": "Explicit compare and explore scenes are reader-controlled, not autoplaying tours; process scenes may play a finite causal sequence. Missing interaction_mode preserves legacy behavior. Generated scene-specific layout remains independent of these trusted control semantics.",
    "effects": "Optional compare/transform/reveal edges animate changing values or expanding/collapsing detail instead of inventing a transfer. Each edge names 1–6 stable readable data-entity IDs whose actual text changes, takes 600–2400ms, and must match a non-self action edge. No duplicate or transfer-overlapping edge. Reveal changes content amount; compare/transform crossfade and move changed values while preserving stable surrounding context. Effects have the same pause/reset/previous/reduced-motion semantics as transfers. Generated code cannot define animations or JavaScript.",
    "playback": "A finite, source-grounded path through generated action edges; auto-start once when visible, suspend offscreen/hidden and resume on return unless manually stopped or completed. Play/pause/replay/reset and previous-step navigation. Pause also suspends an in-flight transfer; the source state remains current until the final transfer arrives. Reduced motion disables automatic playback and skips visual motion while preserving the same action outcomes.",
    "motion": "Matching data-entity IDs track the SAME conceptual object across states. Optional transitions declare ordered transfer steps between two visible entity anchors; the trusted player moves a plain-text token on the current stage and commits the destination state only after arrival. Anchors remain visible in every state. A transfer depicts a source-grounded relationship, not physical routing or measured timing; there is no topic-specific simulation engine. Legacy state-only scenes retain layout displacement/highlighting.",
    "scenarios": "Optional 2–3 named scenarios are distinct simple paths through existing action edges from the initial state. The reader can choose a scenario or a genuine branching action and replay to compare outcomes. Generated HTML does not implement these controls.",
    "controls": "The trusted player renders action buttons, scenario choices, playback controls and status; generated code cannot replace these controls.",
    "presentation": "Optional flow/branch diagram presets use fixed participant structure, allowlisted code-owned icons, short generated labels/statuses and source-grounded connector metadata. Layout, typography and responsive CSS are trusted renderer responsibilities; generated CSS is ignored for preset scenes. Non-preset scenes retain generated scoped HTML/CSS. Transfer kind distinguishes control signals from message/data without topic-specific interpretation.",
    "sandbox": "No arbitrary JavaScript, network requests or parent-page access. Generated content remains editable within its validated contract; trusted preset SVG/CSS is not generated by the model.",
}


def source_sections(sources: str) -> list[dict]:
    """Index the same fetched document bundle used to write/review any topic."""
    from generator.sources.source_context import xml_source_whitespace

    try:
        # The production source gateway supplies sibling <document> nodes.
        root = ET.fromstring(f"<sources>{xml_source_whitespace(sources)}</sources>")
    except ET.ParseError as exc:
        raise ReviewContractError("Official source XML cannot be indexed") from exc
    sections = []
    for document in root.iter("document"):
        url = document.findtext("source_url")
        content = document.findtext("document_content")
        if url and content and content.strip():
            sections.append({"url": url.strip(), "content": content})
    if not sections:
        raise ReviewContractError("No indexed official source documents")
    return sections


class ReviewContractError(ModelGatewayError):
    """Unusable review evidence/history must not become instructions to the writer."""


class RendererReviewError(RuntimeError):
    """The trusted renderer needs developer attention, not another article rewrite."""


def _resolve(document, pointer):
    if not pointer.startswith("/"):
        raise ReviewContractError("Review path must be a JSON pointer")
    value = document
    try:
        for part in pointer[1:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", part):
                    raise ValueError("Invalid array index")
                value = value[int(part)]
            else:
                value = value[part]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ReviewContractError(f"Review refers to missing field: {pointer}") from exc
    return value


def is_chart_numeric_target(path, value):
    """Only model-owned chart numbers are additional editable scalar targets."""
    return (
        isinstance(path, str)
        and type(value) in (int, float)
        and -1e12 <= value <= 1e12
        and math.isfinite(value)
        and re.fullmatch(
            r"/candidate/scenes/[0-9]+/charts/[0-9]+/(?:"
            r"series/[0-9]+/values/[0-9]+|views/[0-9]+/visible_points)",
            path,
        ) is not None
    )


def validate_review(
    raw,
    *,
    candidate,
    inputs,
    frames=None,
    previous_review=None,
    editable_visuals=False,
):
    """Check shape, writable targets, actual source excerpts and prior issue accounting.

    An existing quotation is NOT proof that the review's interpretation is correct.
    Semantic judgments still belong to the independent reviewer and later evaluation.
    """
    try:
        report = json.loads(raw)
        Draft202012Validator(REVIEW_SCHEMA).validate(report)
    except (ValueError, ValidationError) as exc:
        raise ReviewContractError("Invalid motion review JSON/schema") from exc
    issues = report["issues"]
    if (report["verdict"] == "pass") != (not issues):
        raise ReviewContractError("Pass requires no issues; revise requires issues")
    ids = [issue["id"] for issue in issues]
    if len(set(ids)) != len(ids):
        raise ReviewContractError("Duplicate review issue IDs")
    # Only the freshly fetched, indexed official sections can ground factual claims.
    sources = {}
    for item in inputs.get("current_official_sections", []):
        sources[item["url"]] = sources.get(item["url"], "") + "\n" + item["content"]
    document = {
        "candidate": candidate,
        "compiled_frames": frames,
        "renderer": RUNTIME_CONTRACT,
    }
    for issue in issues:
        for key in ("problem", "suggestion"):
            if not issue[key].strip():
                raise ReviewContractError(f"Empty review {key}")
        prefix = (
            "/candidate/"
            if issue["target"] == "content"
            else ("/compiled_frames/", "/renderer/")
        )
        if not issue["path"].startswith(prefix):
            raise ReviewContractError("Review target and path disagree")
        value = _resolve(document, issue["path"])
        if issue["target"] == "content" and not (
            isinstance(value, str) or is_chart_numeric_target(issue["path"], value)
        ):
            raise ReviewContractError(
                "Content issues must identify an editable text/action or chart number field"
            )
        if (
            issue["kind"] == "visual"
            and issue["target"] != "renderer"
            and not editable_visuals
        ):
            raise ReviewContractError("Fixed visual problems belong to the renderer")
        if issue["kind"] == "factual":
            quote = " ".join(issue["source_quote"].split())
            source = " ".join(sources.get(issue["source_url"], "").split())
            if not quote or not source or quote not in source:
                raise ReviewContractError(
                    "Factual review needs a verbatim excerpt from a supplied official section"
                )
        elif issue["source_url"] or issue["source_quote"]:
            raise ReviewContractError(
                "Non-factual issues must leave source fields empty"
            )
    prior = {issue["id"]: issue for issue in (previous_review or {}).get("issues", [])}
    checks = report["previous_issues"]
    if len(checks) != len(prior) or {item["id"] for item in checks} != set(prior):
        raise ReviewContractError(
            "Re-review must account for every previous issue exactly once"
        )
    by_id = {issue["id"]: issue for issue in issues}
    for check in checks:
        if not check["reason"].strip():
            raise ReviewContractError("Previous issue disposition needs a reason")
        unresolved = check["status"] == "unresolved"
        if unresolved != (check["id"] in by_id):
            raise ReviewContractError(
                "Previous issue status contradicts current issues"
            )
        if unresolved:
            current, old = by_id[check["id"]], prior[check["id"]]
            if (current["target"], current["path"]) != (old["target"], old["path"]):
                raise ReviewContractError(
                    "A retained issue ID cannot change its target"
                )
    return report
