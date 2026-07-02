"""하루 1회 실행: 공식문서 기반 학습 노트 1편 생성 → _posts/ai-notes/ 에 작성.

수동 트리거 시 환경변수 FORCE_TOPIC_ID 로 특정 주제 강제 가능.
주제가 모두 소진되면 아무것도 생성하지 않고 정상 종료(exit 0).
"""
from __future__ import annotations

import json
import os
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
            topic = random.choice(undone)

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

    # 카탈로그 주제는 제목이 없으니 fetch한 본문에서 추출.
    title = topic.get("title_hint")
    if not title:
        first_text = next((f["text"] for f in fetched if f["ok"]), "")
        derived = catalog.derive_title(first_text, norm_sources[0]["fetch"])
        tags = topic.get("tags", [])
        prefix = tags[0].capitalize() if tags else ""
        # 제목이 제품명을 안 담고 있으면 태그를 앞에 붙여 맥락 부여
        if prefix and prefix.lower() not in derived.lower():
            title = f"{prefix}: {derived}"
        else:
            title = derived

    user_prompt = load_prompt("user_template.md").format(
        title_hint=title,
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
    print(f"  성공 모델: {model_used}  (본문 {len(body)}자)")

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
