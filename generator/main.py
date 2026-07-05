"""하루 1회 실행: 공식문서 기반 학습 노트 1편 생성 → _posts/ai-notes/ 에 작성.

수동 트리거 시 환경변수 FORCE_TOPIC_ID 로 특정 주제 강제 가능.
주제가 모두 소진되면 아무것도 생성하지 않고 정상 종료(exit 0).
"""
from __future__ import annotations

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
    for f in fetched:
        if not f["ok"]:
            print(f"  - 스킵 {f['fetch']} ({f['reason']})")
            continue
        cite_urls.append(f["cite"])
        blocks.append(f"### 출처: {f['cite']}\n{f['text']}")
    return "\n\n".join(blocks), cite_urls


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

    # 프롬프트에 줄 임시 제목(맥락용). 최종 제목은 LLM이 생성한다.
    hint = topic.get("title_hint")
    if not hint:
        first_text = next((f["text"] for f in fetched if f["ok"]), "")
        hint = catalog.derive_title(first_text, norm_sources[0]["fetch"])

    user_prompt = load_prompt("user_template.md").format(
        title_hint=hint,
        tags=", ".join(topic.get("tags", [])),
        sources_block=sources_block,
    )
    system_prompt = load_prompt(cfg.get("system_prompt", "system.md"))

    print("LLM 생성 중(fallback 체인)...")
    # 다이어그램 소프트 재시도: 없으면 몇 번 더 생성 시도(다이어그램 나올 기회를 줌).
    # 단, 시각적 주제(프로토콜·아키텍처·흐름 등)에서만 재시도 → 낭비 방지.
    # 단순 주제는 재시도 0(첫 결과 수용).
    retry_tags = set(cfg.get("diagram_retry_tags", []))
    topic_tags = set(topic.get("tags", []))
    diagram_worthy = bool(retry_tags & topic_tags)
    diagram_retries = cfg.get("diagram_retries", 2) if diagram_worthy else 0
    if not diagram_worthy:
        print("  (다이어그램 비대상 주제 — 재시도 없이 1회 생성)")
    path = None
    for attempt in range(diagram_retries + 1):
        try:
            body, model_used = llm.generate(system_prompt, user_prompt, models)
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

    dedup.mark_done(topic["id"])
    print(f"작성 완료: {path.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
