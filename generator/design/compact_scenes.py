"""Compile one generated scene template plus safe state values into legacy scenes.

This is an authoring format, not a replacement for design/source/browser review.
Only text nodes and an explicit list of state classes are variable; the compiler
never evaluates generated code, selectors, attribute values, or expressions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString
from jsonschema import Draft202012Validator

from generator.design.scene_document import clean_css, clean_html
from generator.design.visual_contracts import DESIGN_SCHEMA


STATE_CLASSES = (
    "is-active",
    "is-muted",
    "is-success",
    "is-error",
    "is-expanded",
    "is-collapsed",
)
_CLASS_CONFLICTS = (
    {"is-active", "is-muted"},
    {"is-success", "is-error"},
    {"is-expanded", "is-collapsed"},
)
_BINDING = re.compile(r"\{\{([a-z][a-z0-9_]{0,39})\}\}")
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}")


def _object(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _indexes(headings, excerpts):
    if not isinstance(headings, Mapping) or not headings:
        raise ValueError("headings: at least one indexed heading is required")
    heading_index = dict(headings)
    for identifier, heading in heading_index.items():
        if (
            not isinstance(identifier, str)
            or not _ID.fullmatch(identifier)
            or not isinstance(heading, str)
            or not heading.strip()
            or len(heading) > 150
        ):
            raise ValueError("headings: invalid heading ID or exact heading text")
    if len(set(heading_index.values())) != len(heading_index):
        raise ValueError("headings: duplicate heading text is ambiguous")
    if not isinstance(excerpts, Sequence) or isinstance(excerpts, (str, bytes)):
        raise ValueError("excerpts: expected indexed official-source excerpts")
    evidence_index = {}
    for item in excerpts:
        if not isinstance(item, Mapping):
            raise ValueError("excerpts: expected excerpt objects")
        identifier = item.get("excerpt_id")
        url, quote = item.get("source_url"), item.get("quote")
        if (
            not isinstance(identifier, str)
            or not _ID.fullmatch(identifier)
            or identifier in evidence_index
        ):
            raise ValueError("excerpts: invalid or duplicate excerpt_id")
        if (
            not isinstance(url, str)
            or not url.strip()
            or len(url) > 500
            or not isinstance(quote, str)
            or not quote.strip()
            or len(quote) > 500
        ):
            raise ValueError(f"excerpts[{identifier}]: invalid source URL or quote")
        try:
            parsed = urlsplit(url)
        except ValueError as exc:
            raise ValueError(f"excerpts[{identifier}]: invalid source URL") from exc
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError(f"excerpts[{identifier}]: invalid source URL")
        evidence_index[identifier] = {"source_url": url, "quote": quote}
    if not evidence_index:
        raise ValueError("excerpts: at least one official-source excerpt is required")
    return heading_index, evidence_index


def build_compact_schema(
    headings: Mapping[str, str],
    excerpts: Sequence[dict],
    *,
    allow_presentation: bool = False,
    require_clarity: bool = False,
) -> dict:
    """Build a per-request schema using caller-owned heading/evidence ID enums.

    New authoring is custom-layout only. The explicit compatibility flag retains
    presentation for previously saved compact scenes, never as a new default.
    Optional transitions, scenarios and effects are retained in both modes.
    """
    heading_index, evidence_index = _indexes(headings, excerpts)
    schema = deepcopy(DESIGN_SCHEMA)
    scene = schema["properties"]["scenes"]["items"]
    properties = scene["properties"]
    if not allow_presentation:
        properties.pop("presentation", None)
    properties.pop("after_heading")
    properties["heading_id"] = {"type": "string", "enum": list(heading_index)}
    properties["html"] = {
        "type": "string",
        "minLength": 1,
        "maxLength": 7000,
        "description": (
            "One scene-specific HTML template. {{binding_name}} is allowed only "
            "in text nodes, never attributes, tag names, comments or CSS."
        ),
    }
    scene["required"] = [
        "heading_id" if key == "after_heading" else key for key in scene["required"]
    ] + ["html"]
    explanation = properties["explanation"]
    explanation["properties"].pop("evidence")
    explanation["properties"]["excerpt_ids"] = {
        "type": "array",
        "items": {"type": "string", "enum": list(evidence_index)},
        "minItems": 1,
        "maxItems": 3,
        "uniqueItems": True,
    }
    explanation["required"] = [
        "excerpt_ids" if key == "evidence" else key for key in explanation["required"]
    ]
    state = properties["states"]["items"]
    state["properties"].pop("html")
    state["properties"].update(
        values={
            "type": "array",
            "items": _object(
                binding={"type": "string", "pattern": "^[a-z][a-z0-9_]{0,39}$"},
                value={"type": "string", "maxLength": 1000},
            ),
            "minItems": 0,
            "maxItems": 24,
            "description": "Each template binding exactly once; plain text only.",
        },
        entity_classes={
            "type": "array",
            "items": _object(
                entity={"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,31}$"},
                classes={
                    "type": "array",
                    "items": {"type": "string", "enum": list(STATE_CLASSES)},
                    "minItems": 0,
                    "maxItems": len(STATE_CLASSES),
                    "uniqueItems": True,
                },
            ),
            "minItems": 0,
            "maxItems": 24,
            "description": (
                "Optional changes on existing data-entity nodes. Static template "
                "classes are preserved. Unlisted entities receive no state classes."
            ),
        },
    )
    state["required"] = [key for key in state["required"] if key != "html"] + [
        "values",
        "entity_classes",
    ]
    if require_clarity:
        scene["allOf"] = [
            {
                "if": {
                    "properties": {
                        "explanation": {
                            "properties": {"mode": {"const": "interactive"}},
                            "required": ["mode"],
                        }
                    },
                    "required": ["explanation"],
                },
                "then": {"required": ["interaction_mode", "change_explanations"]},
            }
        ]
    return schema


def build_compact_repair_schema(
    headings: Mapping[str, str],
    excerpts: Sequence[dict],
    *,
    allow_presentation: bool = False,
    require_clarity: bool = False,
) -> dict:
    """Repair only explicitly selected scenes, still authoring one template each."""
    scene = build_compact_schema(
        headings,
        excerpts,
        allow_presentation=allow_presentation,
        require_clarity=require_clarity,
    )["properties"]["scenes"]["items"]
    return _object(
        patches={
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": _object(
                scene_index={"type": "integer", "minimum": 0, "maximum": 1},
                scene={"anyOf": [scene, {"type": "null"}]},
            ),
        }
    )


def apply_compact_repair(
    original_compact: dict, raw_patch: str | dict, expected_indices
) -> dict:
    """Apply exact-scope patches; caller compiles and reruns every normal check.

    Core entity IDs stay locked as in legacy scene repair. State IDs may change when
    repairing an invalid graph, but the next compilation/validation must approve it.
    """
    if (
        not isinstance(original_compact, dict)
        or set(original_compact) != {"summary", "scenes"}
        or not isinstance(original_compact["scenes"], list)
        or not 1 <= len(original_compact["scenes"]) <= 2
    ):
        raise ValueError("compact_repair: invalid original design")
    try:
        indices = list(expected_indices)
    except TypeError as exc:
        raise ValueError("compact_repair: expected explicit scene indices") from exc
    if (
        not indices
        or any(
            type(index) is not int or not 0 <= index < len(original_compact["scenes"])
            for index in indices
        )
        or len(set(indices)) != len(indices)
    ):
        raise ValueError("compact_repair: invalid or duplicate expected scene indices")
    if isinstance(raw_patch, str):
        if len(raw_patch) > 100000:
            raise ValueError("compact_repair: response exceeds 100000 characters")
        try:
            patch = json.loads(raw_patch)
        except json.JSONDecodeError as exc:
            raise ValueError("compact_repair: invalid patch JSON") from exc
    else:
        patch = deepcopy(raw_patch)
    if (
        not isinstance(patch, dict)
        or set(patch) != {"patches"}
        or not isinstance(patch["patches"], list)
        or len(patch["patches"]) != len(indices)
    ):
        raise ValueError("compact_repair: return exactly the requested scene patches")
    repaired, seen = deepcopy(original_compact), set()
    for item in patch["patches"]:
        if not isinstance(item, dict) or set(item) != {"scene_index", "scene"}:
            raise ValueError("compact_repair: invalid patch fields")
        index, scene = item["scene_index"], item["scene"]
        if type(index) is not int or index not in indices or index in seen:
            raise ValueError("compact_repair: unknown or duplicate scene_index")
        if scene is None:
            raise ValueError(f"compact_repair/scenes/{index}: no safe repair was found")
        if not isinstance(scene, dict):
            raise ValueError(f"compact_repair/scenes/{index}: expected a compact scene")
        original = original_compact["scenes"][index]
        explanation = (
            original.get("explanation", {}) if isinstance(original, dict) else {}
        )
        entities = (
            explanation.get("key_entities") if isinstance(explanation, dict) else None
        )
        if (
            isinstance(entities, list)
            and entities
            and all(
                isinstance(entity, str)
                and re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", entity)
                for entity in entities
            )
            and len(set(entities)) == len(entities)
        ):
            replacement = scene.get("explanation")
            if (
                not isinstance(replacement, dict)
                or replacement.get("key_entities") != entities
            ):
                raise ValueError(
                    f"compact_repair/scenes/{index}: existing key_entities are locked"
                )
        repaired["scenes"][index] = deepcopy(scene)
        seen.add(index)
    if seen != set(indices):
        raise ValueError("compact_repair: missing requested scene patches")
    return repaired


def _validate_schema(value, schema, *, prefix="compact"):
    error = next(Draft202012Validator(schema).iter_errors(value), None)
    if error is not None:
        path = "/".join(str(component) for component in error.absolute_path)
        raise ValueError(f"{prefix}/{path}: {error.message}")


def _bindings(text, path):
    names = set(_BINDING.findall(text))
    remainder = _BINDING.sub("", text)
    if "{{" in remainder or "}}" in remainder:
        raise ValueError(f"{path}: malformed text binding; use {{{{binding_name}}}}")
    return names


def _template(fragment, path):
    soup = BeautifulSoup(fragment, "html.parser")
    names = set()
    for node in soup.descendants:
        if isinstance(node, Comment):
            if "{{" in str(node) or "}}" in str(node):
                raise ValueError(f"{path}: text bindings are forbidden in comments")
        elif isinstance(node, NavigableString):
            names.update(_bindings(str(node), path))
        elif getattr(node, "attrs", None) is not None:
            if "{{" in node.name or "}}" in node.name:
                raise ValueError(f"{path}: text bindings are forbidden in tag names")
            for key, value in node.attrs.items():
                if "{{" in str((key, value)) or "}}" in str((key, value)):
                    raise ValueError(
                        f"{path}: text bindings are forbidden in attributes"
                    )
            if set(node.get("class", [])) & set(STATE_CLASSES):
                raise ValueError(f"{path}: put state classes in state.entity_classes")
    if len(names) > 24:
        raise ValueError(f"{path}: a scene may define at most 24 text bindings")
    try:
        clean = clean_html(str(soup))
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return BeautifulSoup(clean, "html.parser"), names


def _render_state(template, names, state, path):
    values = {}
    for item in state["values"]:
        name, value = item["binding"], item["value"]
        if name in values:
            raise ValueError(f"{path}/values: duplicate binding {name!r}")
        if "{{" in value or "}}" in value:
            raise ValueError(
                f"{path}/values/{name}: binding values cannot contain bindings"
            )
        values[name] = value
    if set(values) != names:
        missing, unknown = sorted(names - values.keys()), sorted(values.keys() - names)
        raise ValueError(
            f"{path}/values: missing bindings {missing}; unknown bindings {unknown}"
        )
    soup = deepcopy(template)
    for node in list(soup.find_all(string=True)):
        # NavigableString substitution escapes markup and does not recursively
        # interpolate value contents or allow values to become HTML attributes.
        if _BINDING.search(str(node)):
            node.replace_with(
                NavigableString(_BINDING.sub(lambda m: values[m[1]], str(node)))
            )
    entities = {tag["data-entity"]: tag for tag in soup.select("[data-entity]")}
    seen = set()
    for index, patch in enumerate(state["entity_classes"]):
        target, classes = patch["entity"], patch["classes"]
        patch_path = f"{path}/entity_classes/{index}"
        if target not in entities or target in seen:
            raise ValueError(f"{patch_path}: unknown or duplicate entity {target!r}")
        if any(conflict.issubset(classes) for conflict in _CLASS_CONFLICTS):
            raise ValueError(f"{patch_path}: conflicting state classes")
        seen.add(target)
        if classes:
            entities[target]["class"] = entities[target].get("class", []) + classes
    try:
        fragment = clean_html(str(soup))
    except ValueError as exc:
        raise ValueError(f"{path}/html: {exc}") from exc
    return fragment


def compile_compact_design(
    raw: str | dict, headings: Mapping[str, str], excerpts: Sequence[dict]
) -> dict:
    """Expand state values, resolve source IDs, and leave all review gates intact.

    Inputs are not mutated. Callers must persist the original compact response too,
    then run their normal design, source, motion, browser and independent checks.
    """
    heading_index, evidence_index = _indexes(headings, excerpts)
    if isinstance(raw, str):
        if len(raw) > 100000:
            raise ValueError("compact: response exceeds 100000 characters")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"compact: invalid JSON at line {exc.lineno}: {exc.msg}"
            ) from exc
    else:
        value = deepcopy(raw)
    _validate_schema(
        value, build_compact_schema(headings, excerpts, allow_presentation=True)
    )
    compiled = deepcopy(value)
    used_headings = set()
    for scene_index, scene in enumerate(compiled["scenes"]):
        path = f"compact/scenes/{scene_index}"
        heading_id = scene.pop("heading_id")
        if heading_id in used_headings:
            raise ValueError(
                f"{path}/heading_id: duplicate scene heading {heading_id!r}"
            )
        used_headings.add(heading_id)
        scene["after_heading"] = heading_index[heading_id]
        explanation = scene["explanation"]
        explanation["evidence"] = [
            deepcopy(evidence_index[identifier])
            for identifier in explanation.pop("excerpt_ids")
        ]
        template, names = _template(scene.pop("html"), f"{path}/html")
        # Adjacent closing braces are normal at the end of an @media rule.
        if "{{" in scene["css"]:
            raise ValueError(f"{path}/css: text bindings are forbidden in CSS")
        try:
            scene["css"] = clean_css(scene["css"])
        except ValueError as exc:
            raise ValueError(f"{path}/css: {exc}") from exc
        for state_index, state in enumerate(scene["states"]):
            state["html"] = _render_state(
                template, names, state, f"{path}/states/{state_index}"
            )
            del state["values"], state["entity_classes"]
        from generator.design.scene_charts import validate_scene_charts

        try:
            validate_scene_charts(scene)
        except ValueError as exc:
            field = "css" if str(exc).startswith("charts.css:") else "charts"
            raise ValueError(f"{path}/{field}: {exc}") from exc
    _validate_schema(compiled, DESIGN_SCHEMA, prefix="compiled")
    if len(json.dumps(compiled, ensure_ascii=False)) > 100000:
        raise ValueError("compiled: expanded design exceeds 100000 characters")
    return compiled
