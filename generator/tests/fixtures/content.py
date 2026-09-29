"""Reusable fictional inputs and test doubles; never test cases."""

from __future__ import annotations


def design_review_report(*, path="/candidate/scenes/0/caption", verdict="revise"):
    return {
        "verdict": verdict,
        "issues": [
            {
                "id": "I1",
                "target": "content",
                "path": path,
                "kind": "readability",
                "problem": "설명이 불명확하다.",
                "suggestion": "뜻을 구체적으로 설명한다.",
                "source_url": "",
                "source_quote": "",
            }
        ]
        if verdict == "revise"
        else [],
        "previous_issues": [],
    }


def reader_report(evidence, verdict="pass"):
    return {
        "verdict": verdict,
        "issues": [],
        "previous_issues": [],
        "reader_checks": [
            {
                "edge_ref": edge["edge_ref"],
                "change_answer": "버튼을 눌러 라벨 또는 검사 결과가 어떻게 달라지는지 확인한다.",
                "reason_answer": "각 버튼에 해당하는 가상의 정책이 결과를 결정한다.",
                "invariant_answer": "원본 요청의 앱 이름은 그대로 남아 있다.",
                "visible_refs": [
                    item["visible_ref"] for item in edge["visible_values"]
                ],
            }
            for edge in evidence
        ],
    }


def review_report(
    *, verdict: str = "pass", score: int = 5, issues: list[dict] | None = None
) -> dict:
    return {
        "verdict": verdict,
        "scores": {
            "grounding": score,
            "coverage": score,
            "coherence": score,
            "readability": score,
            "visual_clarity": score,
        },
        "issues": issues or [],
    }
