"""초안을 독립 검수하고 필요한 수정·재검수를 수행한다."""

from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path

from contracts import Article, LanguageModelGateway, ReviewReport
from quality import extract_title
from source_context import as_cdata


class ReviewRejectedError(RuntimeError):
    """허용된 수정 횟수 안에 글이 검수 기준을 통과하지 못했다."""


def article_text(article: Article) -> str:
    return f"제목: {article.title}\n\n{article.body.strip()}"


def independent_review_models(
    models: list[str],
    writer_model: str,
) -> list[str]:
    """가능하면 방금 글을 쓴 모델을 검수 후보에서 제외한다."""
    independent = [model for model in models if model != writer_model]
    return independent or models


def print_review(report: ReviewReport, reviewer_model: str) -> None:
    scores = report["scores"]
    score_text = ", ".join(f"{key}={value}" for key, value in scores.items())
    print(f"  검수 모델: {reviewer_model} / 판정: {report['verdict']} / {score_text}")
    for issue in report["issues"]:
        print(
            f"  [{issue['severity']}] {issue['category']}: "
            f"{issue['description']} → {issue['suggestion']}"
        )


def save_review_artifacts(
    base_dir: Path,
    topic_id: str,
    sources_block: str,
    draft: str,
    report: ReviewReport,
    final: str,
    final_report: ReviewReport | None = None,
    review_history: list[ReviewReport] | None = None,
) -> None:
    """요청된 로컬 디렉터리에 동일 초안의 검수 전·후 자료를 저장한다."""
    configured = os.environ.get("REVIEW_ARTIFACT_DIR")
    if not configured:
        return
    root = Path(configured)
    if not root.is_absolute():
        root = base_dir / root
    safe_id = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", topic_id).strip("-")[:120]
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = root / f"{timestamp}-{safe_id or 'review'}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "source-documents.xml").write_text(
        f"<source_documents>\n{sources_block}\n</source_documents>\n",
        encoding="utf-8",
    )
    (run_dir / "before.md").write_text(draft + "\n", encoding="utf-8")
    (run_dir / "review.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if final_report is not None:
        (run_dir / "final-review.json").write_text(
            json.dumps(final_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if review_history and len(review_history) > 1:
        (run_dir / "review-history.json").write_text(
            json.dumps(review_history, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (run_dir / "after.md").write_text(final + "\n", encoding="utf-8")
    diff = difflib.unified_diff(
        draft.splitlines(keepends=True),
        final.splitlines(keepends=True),
        fromfile="before.md",
        tofile="after.md",
    )
    (run_dir / "changes.diff").write_text("".join(diff), encoding="utf-8")
    print(f"  검수 비교 자료: {run_dir}")


class ArticleReviewPipeline:
    """모델 제공자와 무관하게 검수·수정 정책을 실행한다."""

    def __init__(
        self,
        model_gateway: LanguageModelGateway,
        prompt_loader: Callable[[str], str],
        artifact_base_dir: Path,
    ) -> None:
        self._models = model_gateway
        self._load_prompt = prompt_loader
        self._artifact_base_dir = artifact_base_dir

    def run(
        self,
        article: Article,
        *,
        topic_id: str,
        sources_block: str,
        system_prompt: str,
        writer_models: list[str],
        cfg: dict,
    ) -> Article:
        draft_article = article_text(article)
        review_prompt = self._load_prompt(
            cfg.get("review_user_prompt", "review_template.md")
        ).format(
            sources_block=sources_block,
            draft_article=as_cdata(draft_article),
        )
        review_system = self._load_prompt(
            cfg.get("review_system_prompt", "reviewer.md")
        )
        print("독립 품질 검수 중...")
        reviewed = self._models.review(
            review_system,
            review_prompt,
            independent_review_models(
                cfg.get("review_model_fallback", []), article.model
            ),
            max_tokens=cfg.get("review_max_tokens", 4000),
            reasoning_tokens=cfg.get("review_reasoning_tokens", 1200),
        )
        review_report = dict(reviewed.report)
        review_report["reviewer_model"] = reviewed.model
        print_review(review_report, reviewed.model)
        review_history = [review_report]
        final_review_report = None
        final_article = article

        if review_report["verdict"] == "revise":
            final_article, final_review_report = self._revise_until_passed(
                article,
                topic_id=topic_id,
                initial_report=review_report,
                review_system=review_system,
                sources_block=sources_block,
                system_prompt=system_prompt,
                writer_models=writer_models,
                cfg=cfg,
                review_history=review_history,
            )

        save_review_artifacts(
            self._artifact_base_dir,
            topic_id,
            sources_block,
            draft_article,
            review_report,
            article_text(final_article),
            final_review_report,
            review_history,
        )
        return final_article

    def _revise_until_passed(
        self,
        article: Article,
        *,
        topic_id: str,
        initial_report: ReviewReport,
        review_system: str,
        sources_block: str,
        system_prompt: str,
        writer_models: list[str],
        cfg: dict,
        review_history: list[ReviewReport],
    ) -> tuple[Article, ReviewReport | None]:
        current_article = article
        current_report = initial_report
        final_report = None
        max_rounds = max(1, int(cfg.get("review_max_revision_rounds", 2)))

        for revision_round in range(1, max_rounds + 1):
            revision_prompt = self._load_prompt(
                cfg.get("revision_user_prompt", "revision_template.md")
            ).format(
                sources_block=sources_block,
                draft_article=as_cdata(article_text(current_article)),
                review_report=as_cdata(
                    json.dumps(current_report, ensure_ascii=False, indent=2)
                ),
            )
            print(
                f"검수 의견을 반영해 수정본 생성 중... ({revision_round}/{max_rounds})"
            )
            generated = self._models.generate(
                system_prompt,
                revision_prompt,
                writer_models,
                purpose=f"수정본 생성 {revision_round}차",
            )
            revised_title, revised_body = extract_title(
                generated.content,
                current_article.title,
            )
            current_article = Article(
                title=revised_title,
                body=revised_body,
                model=generated.model,
                tags=article.tags,
                source_urls=article.source_urls,
            )

            if not cfg.get("review_recheck_revised", True):
                return current_article, None

            final_review_prompt = self._load_prompt(
                cfg.get("review_user_prompt", "review_template.md")
            ).format(
                sources_block=sources_block,
                draft_article=as_cdata(article_text(current_article)),
            )
            print(f"수정본 최종 검수 중... ({revision_round}/{max_rounds})")
            reviewed = self._models.review(
                review_system,
                final_review_prompt,
                independent_review_models(
                    cfg.get("review_model_fallback", []), current_article.model
                ),
                max_tokens=cfg.get("review_max_tokens", 4000),
                reasoning_tokens=cfg.get("review_reasoning_tokens", 1200),
            )
            final_report = dict(reviewed.report)
            final_report["reviewer_model"] = reviewed.model
            review_history.append(final_report)
            print_review(final_report, reviewed.model)
            if final_report["verdict"] == "pass":
                return current_article, final_report
            current_report = final_report

        save_review_artifacts(
            self._artifact_base_dir,
            topic_id,
            sources_block,
            article_text(article),
            initial_report,
            article_text(current_article),
            final_report,
            review_history,
        )
        raise ReviewRejectedError(
            "허용된 수정 횟수 안에 품질 기준을 통과하지 못해 발행하지 않습니다."
        )
