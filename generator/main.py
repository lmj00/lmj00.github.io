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


def pick_balanced(undone: list[dict], cfg: dict) -> dict:
    """분야(group) 가중치로 먼저 분야를 고르고, 그 안에서 랜덤 선택.

    catalog 개수 불균형과 무관하게 분야별로 골고루 나오게 한다.
    groups/group_weights 설정이 없으면 그냥 전체 랜덤.
    """
    groups = cfg.get("groups")
    weights = cfg.get("group_weights")
    if not groups or not weights:
        return random.choice(undone)

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
    return random.choice(buckets[chosen])


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
    try:
        body, model_used = llm.generate(system_prompt, user_prompt, models)
    except llm.LLMError as e:
        print(f"[실패] {e}", file=sys.stderr)
        return 1

    # LLM 출력 첫 줄의 '제목:' 을 최종 제목으로 사용(없으면 hint 폴백)
    title, body = extract_title(body, hint)
    print(f"  성공 모델: {model_used}  (제목: {title} / 본문 {len(body)}자)")

    path = post_writer.write_post(
        title=title,
        body=body,
        model=model_used,
        tags=topic.get("tags", []),
        source_urls=ok_urls,
    )
    dedup.mark_done(topic["id"])
    print(f"작성 완료: {path.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
