"""저장된 디자인 실행을 오프라인으로 비교한다. 모델 호출/발행/품질 점수 추정 없음."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _read(path, problems):
    try:
        if path.stat().st_size > 20_000_000:
            raise ValueError("artifact exceeds 20 MB")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append({"artifact": str(path), "error": type(exc).__name__})
        return None


def _number(value):
    if type(value) not in (int, float):
        return None
    try:
        return value if math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def _text(value):
    return value if isinstance(value, str) and value else None


def _nested(value, *keys):
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _attempt(path):
    match = re.match(r"(\d+)-", path.name)
    return int(match[1]) if match else 0


def _api_call(path, data):
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    role = re.sub(r"^\d+-|\-http-\d+\.json$", "", path.name)
    return {
        "artifact": str(path),
        "role": role,
        "model": _text(data.get("model")),
        "provider": _text(data.get("provider")),
        "response_model": _text(data.get("response_model")),
        "status": _text(data.get("status")) or "unknown",
        "format_retry": data.get("format_retry"),
        "elapsed_seconds": _number(data.get("elapsed_seconds")),
        "reasoning": _nested(data, "request_parameters", "reasoning"),
        "provider_preferences": _nested(data, "request_parameters", "provider"),
        "response_chars": len(data["content"])
        if isinstance(data.get("content"), str)
        else None,
        "metrics": {
            "input_tokens": _number(usage.get("prompt_tokens")),
            "output_tokens": _number(usage.get("completion_tokens")),
            "reasoning_tokens": _number(
                _nested(usage, "completion_tokens_details", "reasoning_tokens")
            ),
            "cached_input_tokens": _number(
                _nested(usage, "prompt_tokens_details", "cached_tokens")
            ),
            "cache_write_tokens": _number(
                _nested(usage, "prompt_tokens_details", "cache_write_tokens")
            ),
            "reported_cost_usd": _number(usage.get("cost")),
        },
    }


def _total(calls, field):
    values = [
        call["metrics"][field] for call in calls if call["metrics"][field] is not None
    ]
    return {
        "reported": sum(values) if values or not calls else None,
        "known_calls": len(values),
        "unknown_calls": len(calls) - len(values),
        "complete": len(values) == len(calls),
    }


def _json_chars(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def summarize_run(run_dir: Path, *, blind_id="A") -> dict:
    root = Path(run_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"실행 디렉터리를 찾을 수 없음: {root}")
    problems = []
    inputs = _read(root / "input.json", problems)
    state = _read(root / "result.json", problems)
    inputs = inputs if isinstance(inputs, dict) else {}
    state = state if isinstance(state, dict) else {}
    provenance = (
        _read(root / "provenance.json", problems)
        if (root / "provenance.json").exists()
        else {}
    )
    provenance = provenance if isinstance(provenance, dict) else {}
    status = _text(state.get("status")) or "unknown"
    prompts = {}
    prompt_files = {}
    for path in sorted(root.glob("*-prompt.md")):
        try:
            text = path.read_text(encoding="utf-8")
            prompt_files[path.name] = _digest(text)
            if path.stem in {"designer-prompt", "reviewer-prompt"}:
                prompts[path.stem.removesuffix("-prompt")] = text
        except OSError as exc:
            problems.append({"artifact": str(path), "error": type(exc).__name__})
    sources = inputs.get("current_official_sections")
    article = inputs.get("article")
    fingerprints = {
        "sources": _digest(sources) if isinstance(sources, list) and sources else None,
        "article": _digest(article) if isinstance(article, str) and article else None,
        "prompts": _digest(prompts) if prompts else None,
        "prompt_files": prompt_files,
    }
    provenance_mismatches = [
        field
        for field, key in (
            ("sources", "source_digest"),
            ("article", "article_digest"),
            ("prompts", "prompt_digest"),
        )
        if provenance.get(key) and provenance[key] != fingerprints[field]
    ]
    calls = []
    http_paths = sorted(
        root.glob("*-http-*.json"),
        key=lambda path: (
            _attempt(path),
            int(re.search(r"http-(\d+)\.json$", path.name)[1])
            if re.search(r"http-(\d+)\.json$", path.name)
            else 0,
        ),
    )
    for path in http_paths:
        data = _read(path, problems)
        calls.append(_api_call(path, data if isinstance(data, dict) else {}))
    # The usage index is not added a second time. Missing HTTP artifacts retain
    # any indexed usage, while elapsed/provider details remain explicitly unknown.
    index = (
        _read(root / "usage.json", problems) if (root / "usage.json").exists() else []
    )
    seen_artifacts = {path.name for path in http_paths}
    if isinstance(index, list):
        for position, item in enumerate(index):
            if (
                not isinstance(item, dict)
                or _text(item.get("artifact")) in seen_artifacts
            ):
                continue
            fallback_path = root / f"usage.json#{position}"
            call = _api_call(fallback_path, item)
            call["role"] = item.get("purpose", "unknown")
            calls.append(call)
            problems.append(
                {"artifact": str(fallback_path), "error": "missing_http_artifact"}
            )
    metrics = {
        field: _total(calls, field)
        for field in (
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "reported_cost_usd",
        )
    }
    api_times = [
        call["elapsed_seconds"] for call in calls if call["elapsed_seconds"] is not None
    ]
    candidates = []
    for path in sorted(root.glob("*-candidate.json"), key=_attempt):
        candidate = _read(path, problems)
        compact_path = root / f"{_attempt(path)}-compact.json"
        compact = _read(compact_path, problems) if compact_path.exists() else None
        candidates.append(
            {
                "attempt": _attempt(path),
                "expanded_artifact": str(path),
                "expanded_json_chars": _json_chars(candidate)
                if candidate is not None
                else None,
                "compact_artifact": str(compact_path)
                if compact_path.exists()
                else None,
                "compact_json_chars": _json_chars(compact)
                if compact is not None
                else None,
            }
        )
    browser = [
        {
            "attempt": _attempt(path),
            "artifact": str(path),
            "reports": _read(path, problems),
        }
        for path in sorted(root.glob("*-browser.json"), key=_attempt)
    ]
    validation = []
    for path in sorted(root.glob("*-validation-issues.json"), key=_attempt):
        issues = _read(path, problems)
        if isinstance(issues, list):
            validation.append(
                {
                    "attempt": _attempt(path),
                    "artifact": str(path),
                    "counts": dict(
                        Counter(
                            item.get("kind", "unknown")
                            for item in issues
                            if isinstance(item, dict)
                        )
                    ),
                }
            )
    designer_calls = [
        call
        for call in calls
        if call["role"]
        in {"designer", "scene-repair", "field-repair", "evidence-repair"}
    ]
    generation_model = _text(state.get("design_model")) or next(
        (call["model"] for call in designer_calls if call["model"]), None
    )
    latest = candidates[-1] if candidates else None
    return {
        "blind_id": blind_id,
        "run_dir": str(root),
        "article_title": inputs.get("article_title"),
        "status": status,
        "failure_stage": state.get("stage")
        if status not in {"pass", "running"}
        else None,
        "stage": state.get("stage"),
        "attempts": state.get("attempts"),
        "resumed_candidate": state.get("resumed_candidate", False),
        "generation_format": provenance.get("generation_format", "unknown"),
        "generation_model": generation_model,
        "fingerprints": fingerprints,
        "provenance_mismatches": provenance_mismatches,
        "timing": {
            "api_seconds_reported": round(sum(api_times), 3)
            if api_times or not calls
            else None,
            "api_seconds_complete": len(api_times) == len(calls),
            "run_elapsed_seconds": _number(state.get("elapsed_seconds")),
            "scope": "saved design run; excludes earlier article generation and later publication",
        },
        "api_calls": calls,
        "usage": metrics,
        "failures_with_unreported_cost": [
            call["artifact"]
            for call in calls
            if call["status"] != "valid"
            and call["metrics"]["reported_cost_usd"] is None
        ],
        "candidate_sizes": candidates,
        "browser": browser,
        "validation": validation,
        "reader_evidence": {
            "required": bool(provenance.get("settings", {}).get("design_clarity_required")),
            "reports": [
                {"attempt": _attempt(path), "checks": _read(path, problems)}
                for path in sorted(root.glob("*-reader-checks.json"), key=_attempt)
            ],
            "note": "Model answers with DOM/ledger references; not measured human comprehension or a quality score.",
        },
        "human_review": {
            "blind_id": blind_id,
            "candidate": latest["expanded_artifact"] if latest else None,
            "candidate_attempt": latest["attempt"] if latest else None,
            "candidate_is_last_attempt": latest["attempt"] == state.get("attempts")
            if latest
            else False,
            "scene_documents": [
                str(path)
                for path in sorted(root.glob(f"{latest['attempt']}-scene-*.html"))
            ]
            if latest
            else [],
            "note": "Inspect these saved artifacts; a candidate or browser report does not imply publication approval.",
        },
        "artifact_problems": problems,
    }


def compare_runs(run_dirs: list[Path]) -> dict:
    runs = [
        summarize_run(path, blind_id=f"R{index:02d}")
        for index, path in enumerate(run_dirs, 1)
    ]
    grouped = defaultdict(list)
    excluded = []
    for run in runs:
        key = (
            run["fingerprints"]["sources"],
            run["fingerprints"]["article"],
            run["generation_model"],
        )
        if all(key) and not set(run["provenance_mismatches"]) & {"sources", "article"}:
            grouped[key].append(run)
        else:
            excluded.append(run["blind_id"])
    comparisons = []
    for key, members in grouped.items():
        if len(members) < 2:
            excluded.extend(run["blind_id"] for run in members)
            continue
        caveats = []
        for field, label in (
            ("provider", "Provider choices differ or are unknown."),
            ("reasoning", "Reasoning effort/budget differs or is unknown."),
            ("model", "Attempt/reviewer/fallback model sets differ or are unknown."),
        ):
            signatures = [
                sorted(
                    {
                        json.dumps(
                            {"role": call["role"], "value": call[field]}, sort_keys=True
                        )
                        for call in run["api_calls"]
                    }
                )
                for run in members
            ]
            unknown = any(
                not run["api_calls"]
                or any(call[field] is None for call in run["api_calls"])
                for run in members
            )
            if unknown or any(
                signature != signatures[0] for signature in signatures[1:]
            ):
                caveats.append(label)
        if len({run["fingerprints"]["prompts"] for run in members}) > 1:
            caveats.append(
                "Prompts differ; attribute results to the complete configuration, not one isolated factor."
            )
        if any(not run["usage"]["reported_cost_usd"]["complete"] for run in members):
            caveats.append(
                "Some API costs are unreported; reported subtotals are not complete run costs."
            )
        comparisons.append(
            {
                "matching_sources": key[0],
                "matching_article": key[1],
                "generation_model": key[2],
                "runs": [run["blind_id"] for run in members],
                "caveats": caveats,
                "quality_comparison": "human review required; no aggregate quality score inferred",
            }
        )
    return {
        "offline": True,
        "notes": [
            "Only saved artifacts are read; no API calls, browser execution or publication.",
            "Token output already includes reported reasoning; do not add reasoning tokens again. Cached input is likewise a subset of input.",
            "Missing costs/tokens/times remain unknown, never assumed zero. Old elapsed time is not inferred from file timestamps.",
            "Pass/held status is preserved from the run; mechanical/browser success is not a quality score.",
        ],
        "runs": runs,
        "comparisons": comparisons,
        "unmatched_or_incomplete_runs": excluded,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_dirs", nargs="+", type=Path, help="저장된 .design-runs 실행 폴더"
    )
    args = parser.parse_args(argv)
    try:
        report = compare_runs(args.run_dirs)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
