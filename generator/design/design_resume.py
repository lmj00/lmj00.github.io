"""저장된 본문/후보/검수 이력을 읽어 디자인 단계에서 이어 실행한다."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from generator.contracts import Article, GeneratedText, ModelGatewayError
from generator.design.visual_contracts import source_sections, validate_review


@dataclass(frozen=True)
class SavedDesign:
    article: Article
    sources: str
    candidate: GeneratedText
    author_models: tuple[str, ...]
    review_context: dict | None
    compact_candidate: dict | None = None


def load_saved_design(run_dir: Path) -> SavedDesign:
    """로컬 디자인 실행 기록만 사용. 원본 파일/주제 상태는 변경하지 않는다."""
    try:
        inputs = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
        sources = inputs["sources"]
        sections = source_sections(sources)
        if inputs["current_official_sections"] != sections:
            raise ValueError("저장된 공식문서와 색인이 일치하지 않음")
        title, body, tags = inputs["article_title"], inputs["article"], inputs["tags"]
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(body, str)
            or not body.strip()
        ):
            raise ValueError("저장된 본문/제목이 없음")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError("저장된 태그 형식 오류")
        candidates = sorted(
            (int(match[1]), path)
            for path in run_dir.glob("*-candidate.json")
            if (match := re.fullmatch(r"([1-9][0-9]*)-candidate\.json", path.name))
        )
        if not candidates:
            raise ValueError("이어 실행할 디자인 후보가 없음")
        latest_attempt, latest = candidates[-1]
        content = latest.read_text(encoding="utf-8")
        json.loads(content)
        compact_candidate = None
        provenance = {}
        compact_path = run_dir / f"{latest_attempt}-compact.json"
        provenance_path = run_dir / "provenance.json"
        if provenance_path.exists():
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            if (
                provenance.get("compact_candidate_expected")
                and not compact_path.exists()
            ):
                raise ValueError("저장된 compact 원본 파일이 없음")
        if compact_path.exists():
            from generator.design.compact_scenes import compile_compact_design
            from generator.design.evidence_repair import source_excerpts

            compact_candidate = json.loads(compact_path.read_text(encoding="utf-8"))
            headings = {
                f"section_{i}": text for i, text in enumerate(inputs["headings"], 1)
            }
            compiled = compile_compact_design(
                compact_candidate, headings, source_excerpts(sections)
            )
            if compiled != json.loads(content):
                raise ValueError("저장된 compact 원본과 렌더링 후보가 일치하지 않음")
        # Include every contributing author, not just the last repair model.
        authors = set()
        original_models = []
        for path in run_dir.glob("*-response.json"):
            if re.fullmatch(
                r"[1-9][0-9]*-(designer|scene-repair|field-repair|evidence-repair|saved)-response\.json",
                path.name,
            ):
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value.get("model"), str) and value["model"]:
                    authors.add(value["model"])
                    if "-designer-" in path.name or "-saved-" in path.name:
                        original_models.append(
                            (int(path.name.split("-", 1)[0]), value["model"])
                        )
        state_file = run_dir / "result.json"
        if state_file.exists():
            known = json.loads(state_file.read_text(encoding="utf-8")).get(
                "author_models", []
            )
            if not isinstance(known, list) or not all(
                isinstance(model, str) and model for model in known
            ):
                raise ValueError("저장된 작성 모델 목록 오류")
            authors.update(known)
        if not authors:
            raise ValueError("독립 검수에 필요한 작성 모델 기록이 없음")
        if not original_models:
            raise ValueError("최초 디자인 작성 모델 기록이 없음")
        original_model = min(original_models)[1]
        review_context = None
        inherited_context = run_dir / "saved-review-context.json"
        if inherited_context.exists():
            context = json.loads(inherited_context.read_text(encoding="utf-8"))
            inherited_report = validate_review(
                json.dumps(context["report"]),
                candidate=context["candidate"],
                inputs=inputs,
                previous_review=context.get("previous_review"),
                editable_visuals=True,
            )
            if any(
                issue["target"] == "renderer" for issue in inherited_report["issues"]
            ):
                raise ValueError("고정 실행기 오류는 장면 재생성으로 해결할 수 없음")
            review_context = {**context, "report": inherited_report}
        for attempt, candidate_path in candidates:
            report_path = run_dir / f"{attempt}-review.json"
            if not report_path.exists():
                continue
            reviewed_candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            review_input = json.loads(
                (run_dir / f"{attempt}-review-input.json").read_text(encoding="utf-8")
            )
            report = validate_review(
                report_path.read_text(encoding="utf-8"),
                candidate=reviewed_candidate,
                inputs=inputs,
                previous_review=review_input.get("previous_review"),
                editable_visuals=True,
            )
            if provenance.get("settings", {}).get("design_clarity_required"):
                from generator.design.reader_review import build_reader_evidence, validate_reader_checks

                evidence = build_reader_evidence(reviewed_candidate)
                if review_input.get("reader_evidence") != evidence:
                    raise ValueError("저장된 독자 검수 근거와 후보가 일치하지 않음")
                checks = json.loads(
                    (run_dir / f"{attempt}-reader-checks.json").read_text(encoding="utf-8")
                )
                validate_reader_checks(
                    json.dumps({**report, "reader_checks": checks}), evidence
                )
            if any(issue["target"] == "renderer" for issue in report["issues"]):
                raise ValueError("고정 실행기 오류는 장면 재생성으로 해결할 수 없음")
            review_context = {
                "report": report,
                "candidate": reviewed_candidate,
                "previous_review": review_input.get("previous_review"),
            }
        article = Article(
            title,
            body,
            "saved-reviewed-body",
            tuple(tags),
            tuple(section["url"] for section in sections),
        )
        # Original attribution is retained in author_models even across mixed-model repairs.
        return SavedDesign(
            article,
            sources,
            GeneratedText(content, original_model),
            tuple(sorted(authors)),
            review_context,
            compact_candidate,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ModelGatewayError(f"저장된 디자인 실행을 읽을 수 없음: {exc}") from exc
