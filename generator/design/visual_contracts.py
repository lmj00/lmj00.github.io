"""Topic-independent visual data contracts."""

from __future__ import annotations


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
