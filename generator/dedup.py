"""중복 방지: 이미 생성한 주제 기록 + 기존 글 제목 스캔."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state" / "topics_done.json"
POSTS_DIR = HERE.parent / "_posts"


def load_done() -> list[str]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except ValueError:
            return []
    return []


_load_done = load_done  # 하위호환 별칭


def _save_done(done: list[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")


def existing_post_titles() -> set[str]:
    """기존 글들의 title frontmatter를 소문자로 모은다(느슨한 중복 방지)."""
    titles: set[str] = set()
    if not POSTS_DIR.exists():
        return titles
    for md in POSTS_DIR.rglob("*.md"):
        try:
            head = md.read_text(encoding="utf-8")[:500]
        except OSError:
            continue
        m = re.search(r'title:\s*"?([^"\n]+)"?', head)
        if m:
            titles.add(m.group(1).strip().lower())
    return titles


def pick_next_topic(topics: list[dict], forced_id: str | None = None) -> dict | None:
    """아직 안 쓴 주제 하나 선택. forced_id가 있으면 그걸 우선(수동 트리거)."""
    done = set(_load_done())
    titles = existing_post_titles()

    if forced_id:
        for t in topics:
            if t["id"] == forced_id:
                return t
        return None

    for t in topics:
        if t["id"] in done:
            continue
        if t["title_hint"].strip().lower() in titles:
            continue
        return t
    return None  # 모두 소진 → 호출부에서 스킵


def mark_done(topic_id: str) -> None:
    done = _load_done()
    if topic_id not in done:
        done.append(topic_id)
        _save_done(done)
