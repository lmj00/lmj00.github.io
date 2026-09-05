"""하루 1회 실행: 공식문서 기반 학습 노트 1편 생성 → _posts/ai-notes/ 에 작성.

수동 트리거 시 환경변수 FORCE_TOPIC_ID 로 특정 주제 강제 가능.
주제가 모두 소진되면 아무것도 생성하지 않고 정상 종료(exit 0).
"""
from __future__ import annotations

import datetime as dt
import difflib
import html
import json
import os
import re
import sys
from pathlib import Path

import random

import fetcher
import llm
import dedup
import post_writer
import catalog
import difficulty

HERE = Path(__file__).resolve().parent


def load_dotenv() -> None:
    """generator/.env 가 있으면 환경변수로 로드(로컬 실행용). 커밋 안 됨."""
    env_path = HERE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def load_config() -> dict:
    return json.loads((HERE / "sources.json").read_text(encoding="utf-8"))


def load_prompt(name: str) -> str:
    return (HERE / "prompts" / name).read_text(encoding="utf-8")


def normalize_sources(sources: list) -> list[dict]:
    """source 항목을 {'fetch', 'cite'} 형태로 정규화(문자열도 허용)."""
    out = []
    for s in sources:
        if isinstance(s, str):
            out.append({"fetch": s, "cite": s})
        else:
            out.append({"fetch": s["fetch"], "cite": s.get("cite", s["fetch"])})
    return out


def _pick_lowest_level(bucket: list[dict], cfg: dict) -> dict:
    """후보 묶음에서 난이도 레벨이 가장 낮은(기초) 주제 선택. 동레벨이면 랜덤.

    캐시에 없는 주제만 이 시점에 채점(lazy)되고, 이후엔 캐시만 읽는다.
    """
    levels = difficulty.score(bucket, cfg)
    min_lvl = min(levels[t["id"]] for t in bucket)
    finalists = [t for t in bucket if levels[t["id"]] == min_lvl]
    print(f"  난이도 레벨 {min_lvl}(기초 우선) 후보 {len(finalists)}개 중 선택")
    return random.choice(finalists)


def pick_balanced(undone: list[dict], cfg: dict) -> dict:
    """분야(group) 가중치로 먼저 분야를 고르고, 그 안에서 난이도 최저(기초)부터 선택.

    catalog 개수 불균형과 무관하게 분야별로 골고루 나오게 하되,
    각 분야 '안'에서는 기초→심화 순서가 되도록 레벨 낮은 주제를 먼저 뽑는다.
    groups/group_weights 설정이 없으면 전체에서 레벨 최저 선택.
    """
    groups = cfg.get("groups")
    weights = cfg.get("group_weights")
    if not groups or not weights:
        return _pick_lowest_level(undone, cfg)

    # catalog id -> group 이름
    id2group = {}
    for gname, cat_ids in groups.items():
        for cid in cat_ids:
            id2group[cid] = gname

    # 미생성 후보를 분야별로 묶기
    buckets: dict[str, list] = {}
    for c in undone:
        cat_id = c["id"].split("::")[0]
        g = id2group.get(cat_id, "기타")
        buckets.setdefault(g, []).append(c)

    # 후보가 있는 분야만 대상으로 가중 선택
    avail = [(g, weights.get(g, 1)) for g in buckets]
    chosen = random.choices([g for g, _ in avail], weights=[w for _, w in avail])[0]
    print(f"  분야 선택: {chosen} ({len(buckets[chosen])}개 중)")
    return _pick_lowest_level(buckets[chosen], cfg)


def extract_title(body: str, fallback: str) -> tuple[str, str]:
    """LLM 출력 첫 줄의 '제목: ...' 을 추출하고, 그 줄은 본문에서 제거."""
    stripped = body.lstrip()
    first, _, rest = stripped.partition("\n")
    m = re.match(r"^\s*(?:#+\s*)?제목\s*[:：]\s*(.+)$", first.strip())
    if m:
        title = m.group(1).strip().strip('"').strip("'").strip("#").strip()
        if title:
            return title, rest.lstrip("\n")
    return fallback, body


def _remove_post(path: Path) -> None:
    """재시도 위해 방금 쓴 글 파일 + 그 글의 다이어그램 SVG 제거."""
    path.unlink(missing_ok=True)
    diagrams = HERE.parent / "assets" / "diagrams"
    if diagrams.exists():
        for svg in diagrams.glob(f"{path.stem}-*.svg"):
            svg.unlink(missing_ok=True)


def build_sources_block(fetched: list[dict]) -> tuple[str, list[str]]:
    blocks = []
    cite_urls = []
    for index, f in enumerate(fetched, 1):
        if not f["ok"]:
            print(f"  - 스킵 {f['fetch']} ({f['reason']})")
            continue
        cite_urls.append(f["cite"])
        # 원문에 XML 모양의 코드가 있어도 문서 경계를 깨지 않도록 CDATA로 감싼다.
        content = f["text"].replace("]]>", "]]]]><![CDATA[>")
        blocks.append(
            f'<document index="{index}">\n'
            f'  <source_url>{html.escape(f["cite"], quote=True)}</source_url>\n'
            f'  <document_content><![CDATA[\n{content}\n]]></document_content>\n'
            f'</document>'
        )
    return "\n\n".join(blocks), cite_urls


def source_quality(fetched: list[dict], min_total_chars: int,
                   min_substantive_chars: int) -> tuple[bool, str]:
    """출처가 설명형 글을 뒷받침할 만큼 충분한지 보수적으로 판정한다.

    전체 길이뿐 아니라 긴 문장·문단의 양도 본다. 링크 제목과 메뉴만 긴
    색인 페이지가 단순 길이 기준을 통과하는 일을 줄이기 위해서다.
    """
    texts = [str(item.get("text", "")).strip()
             for item in fetched if item.get("ok")]
    total_chars = sum(len(text) for text in texts)
    substantive_chars = sum(
        len(line)
        for text in texts
        for raw_line in text.splitlines()
        if len(line := raw_line.strip()) >= 50
    )
    if total_chars < min_total_chars:
        return False, f"전체 근거 {total_chars}자 < {min_total_chars}자"
    if substantive_chars < min_substantive_chars:
        return False, (
            f"설명형 근거 {substantive_chars}자 < "
            f"{min_substantive_chars}자(색인·목차형 문서 가능성)"
        )
    return True, (
        f"전체 근거 {total_chars}자 / 설명형 근거 {substantive_chars}자"
    )


def _as_cdata(text: str) -> str:
    """CDATA 종료 문자열이 들어 있는 텍스트도 안전하게 XML 안에 넣는다."""
    return text.replace("]]>", "]]]]><![CDATA[>")


def _article_text(title: str, body: str) -> str:
    return f"제목: {title}\n\n{body.strip()}"


def _print_review(report: dict, reviewer_model: str) -> None:
    scores = report["scores"]
    score_text = ", ".join(f"{key}={value}" for key, value in scores.items())
    print(f"  검수 모델: {reviewer_model} / 판정: {report['verdict']} / {score_text}")
    for issue in report["issues"]:
        print(
            f"  [{issue['severity']}] {issue['category']}: "
            f"{issue['description']} → {issue['suggestion']}"
        )


def _independent_review_models(models: list[str], writer_model: str) -> list[str]:
    """가능하면 방금 글을 쓴 모델을 검수 후보에서 제외한다."""
    independent = [model for model in models if model != writer_model]
    return independent or models


def _save_review_artifacts(topic_id: str, sources_block: str, draft: str,
                           report: dict, final: str,
                           final_report: dict | None = None,
                           review_history: list[dict] | None = None) -> None:
    """로컬 비교 요청 시 동일 초안의 검수 전·후 자료를 저장한다."""
    configured = os.environ.get("REVIEW_ARTIFACT_DIR")
    if not configured:
        return
    root = Path(configured)
    if not root.is_absolute():
        root = HERE / root
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


def main() -> int:
    load_dotenv()
    cfg = load_config()
    ua = cfg["user_agent"]
    max_chars = cfg.get("max_chars_per_source", 16000)

    # 다이어그램(D2) 스타일 적용
    d2_flags = [f"--theme={cfg.get('d2_theme', 3)}"]
    if cfg.get("d2_sketch", True):
        d2_flags.append("--sketch")
    d2_flags.append("--pad=40")
    post_writer.D2_FLAGS = d2_flags

    # 무료모델 fallback 체인: auto면 OpenRouter에서 실시간 조회
    if cfg.get("model_selection") == "auto":
        models = llm.build_fallback_chain(
            cfg.get("model_prefer", []),
            cfg.get("model_exclude", []),
            seed=cfg.get("model_seed", []),
        )
        print(f"무료모델 실시간 조회: {len(models)}개 (상위: {', '.join(models[:3])})")
    else:
        models = cfg.get("model_fallback", [])

    forced = os.environ.get("FORCE_TOPIC_ID") or None

    # 1순위: 손으로 적은 curated 주제(있으면). 2순위: 카탈로그 자동 발굴 풀.
    topic = dedup.pick_next_topic(cfg.get("topics", []), forced_id=forced)
    if topic is None and not forced:
        print("카탈로그에서 주제 자동 발굴 중...")
        pool = catalog.build_pool(cfg.get("catalogs", []))
        done = set(dedup.load_done())
        undone = [c for c in pool if c["id"] not in done]
        print(f"  전체 후보 {len(pool)}개 / 미생성 {len(undone)}개")
        if undone:
            topic = pick_balanced(undone, cfg)

    if topic is None:
        print("생성할 새 주제가 없습니다(모두 소진 또는 잘못된 FORCE_TOPIC_ID). 종료.")
        return 0

    print(f"선택된 주제: {topic['id']} - {topic.get('title_hint') or '(fetch 후 제목 추출)'}")

    print("공식문서 fetch 중...")
    # curated 주제는 'sources' 리스트, 카탈로그 주제는 단일 fetch/cite.
    if "sources" in topic:
        norm_sources = normalize_sources(topic["sources"])
    else:
        norm_sources = [{"fetch": topic["fetch"], "cite": topic["cite"]}]
    fetched = fetcher.fetch_topic_sources(norm_sources, ua, max_chars)
    sources_block, ok_urls = build_sources_block(fetched)
    if not ok_urls:
        print("사용 가능한 출처가 없습니다(robots 차단/오류). 이 주제는 건너뜁니다.")
        return 0

    enough, source_reason = source_quality(
        fetched,
        cfg.get("min_total_source_chars", 0),
        cfg.get("min_substantive_source_chars", 0),
    )
    if not enough:
        print(f"출처 품질 부족({source_reason}) — 억지로 글을 만들지 않습니다.")
        # 다음 자동 실행에서 같은 얕은 문서만 반복 선택하지 않도록 처리 완료로 기록한다.
        dedup.mark_done(topic["id"])
        return 0
    print(f"  출처 품질: {source_reason}")

    # 프롬프트에 줄 임시 제목(맥락용). 최종 제목은 LLM이 생성한다.
    hint = topic.get("title_hint")
    if not hint:
        first_text = next((f["text"] for f in fetched if f["ok"]), "")
        hint = catalog.derive_title(first_text, norm_sources[0]["fetch"])

    user_prompt = load_prompt("user_template.md").format(
        title_hint=html.escape(hint, quote=True),
        tags=html.escape(", ".join(topic.get("tags", [])), quote=True),
        sources_block=sources_block,
    )
    system_prompt = load_prompt(cfg.get("system_prompt", "system.md"))

    print("LLM 생성 중(fallback 체인)...")
    # 다이어그램은 선택 사항이다. 재시도를 켠 경우에만 대상 태그를 적용한다.
    retry_tags = set(cfg.get("diagram_retry_tags", []))
    topic_tags = set(topic.get("tags", []))
    diagram_worthy = bool(retry_tags & topic_tags)
    diagram_retries = cfg.get("diagram_retries", 0) if diagram_worthy else 0
    if diagram_retries == 0:
        print("  (다이어그램은 선택 사항 — 재시도 없이 1회 생성)")
    path = None
    for attempt in range(diagram_retries + 1):
        try:
            body, model_used = llm.generate(
                system_prompt, user_prompt, models, purpose="초안 생성"
            )
        except llm.LLMError as e:
            print(f"[실패] {e}", file=sys.stderr)
            return 1
        title, body = extract_title(body, hint)
        p = post_writer.write_post(
            title=title, body=body, model=model_used,
            tags=topic.get("tags", []), source_urls=ok_urls,
        )
        has_diagram = "assets/diagrams" in p.read_text(encoding="utf-8")
        if has_diagram or attempt == diagram_retries:
            mark = "O" if has_diagram else "X(수용)"
            print(f"  성공 모델: {model_used}  (제목: {title} / {len(body)}자 / 다이어그램 {mark})")
            path = p
            break
        print(f"  다이어그램 없음(시도 {attempt + 1}/{diagram_retries + 1}) → 재생성")
        _remove_post(p)

    if path is None:
        print("[실패] 생성 결과 파일을 찾을 수 없습니다.", file=sys.stderr)
        return 1

    if cfg.get("review_enabled", False):
        draft_article = _article_text(title, body)
        review_prompt = load_prompt(
            cfg.get("review_user_prompt", "review_template.md")
        ).format(
            sources_block=sources_block,
            draft_article=_as_cdata(draft_article),
        )
        review_system = load_prompt(
            cfg.get("review_system_prompt", "reviewer.md")
        )
        print("독립 품질 검수 중...")
        try:
            review_report, reviewer_model = llm.review(
                review_system,
                review_prompt,
                _independent_review_models(
                    cfg.get("review_model_fallback", []), model_used
                ),
                max_tokens=cfg.get("review_max_tokens", 4000),
                reasoning_tokens=cfg.get("review_reasoning_tokens", 1200),
            )
        except llm.LLMError as e:
            _remove_post(path)
            print(f"[실패] {e}", file=sys.stderr)
            return 1
        review_report["reviewer_model"] = reviewer_model
        _print_review(review_report, reviewer_model)
        review_history = [review_report]
        final_review_report = None

        if review_report["verdict"] == "revise":
            current_article = draft_article
            current_report = review_report
            max_revision_rounds = max(
                1, int(cfg.get("review_max_revision_rounds", 2))
            )

            for revision_round in range(1, max_revision_rounds + 1):
                feedback = json.dumps(
                    current_report, ensure_ascii=False, indent=2
                )
                revision_prompt = load_prompt(
                    cfg.get("revision_user_prompt", "revision_template.md")
                ).format(
                    sources_block=sources_block,
                    draft_article=_as_cdata(current_article),
                    review_report=_as_cdata(feedback),
                )
                print(
                    f"검수 의견을 반영해 수정본 생성 중... "
                    f"({revision_round}/{max_revision_rounds})"
                )
                try:
                    revised, revision_model = llm.generate(
                        system_prompt,
                        revision_prompt,
                        models,
                        purpose=f"수정본 생성 {revision_round}차",
                    )
                except llm.LLMError as e:
                    _remove_post(path)
                    print(f"[실패] {e}", file=sys.stderr)
                    return 1
                revised_title, revised_body = extract_title(revised, title)
                revised_article = _article_text(revised_title, revised_body)

                if not cfg.get("review_recheck_revised", True):
                    break

                final_review_prompt = load_prompt(
                    cfg.get("review_user_prompt", "review_template.md")
                ).format(
                    sources_block=sources_block,
                    draft_article=_as_cdata(revised_article),
                )
                print(
                    f"수정본 최종 검수 중... "
                    f"({revision_round}/{max_revision_rounds})"
                )
                try:
                    final_review_report, final_reviewer_model = llm.review(
                        review_system,
                        final_review_prompt,
                        _independent_review_models(
                            cfg.get("review_model_fallback", []), revision_model
                        ),
                        max_tokens=cfg.get("review_max_tokens", 4000),
                        reasoning_tokens=cfg.get("review_reasoning_tokens", 1200),
                    )
                except llm.LLMError as e:
                    _remove_post(path)
                    print(
                        f"[실패] 수정본을 검수하지 못했습니다: {e}",
                        file=sys.stderr,
                    )
                    return 1
                final_review_report["reviewer_model"] = final_reviewer_model
                review_history.append(final_review_report)
                _print_review(final_review_report, final_reviewer_model)
                if final_review_report["verdict"] == "pass":
                    break

                current_article = revised_article
                current_report = final_review_report
                if revision_round == max_revision_rounds:
                    _save_review_artifacts(
                        topic["id"], sources_block, draft_article,
                        review_report, revised_article, final_review_report,
                        review_history,
                    )
                    _remove_post(path)
                    print(
                        "[실패] 허용된 수정 횟수 안에 품질 기준을 통과하지 "
                        "못해 발행하지 않습니다.",
                        file=sys.stderr,
                    )
                    return 1

            _remove_post(path)
            path = post_writer.write_post(
                title=revised_title,
                body=revised_body,
                model=revision_model,
                tags=topic.get("tags", []),
                source_urls=ok_urls,
            )
            title, body, model_used = (
                revised_title, revised_body, revision_model
            )
            print(
                f"  수정 완료: {title} / {len(body)}자 / 모델 {model_used}"
            )

        _save_review_artifacts(
            topic["id"],
            sources_block,
            draft_article,
            review_report,
            _article_text(title, body),
            final_review_report,
            review_history,
        )

    dedup.mark_done(topic["id"])
    print(f"작성 완료: {path.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
