"""자동 실행 사이에 검수된 본문만 보존한다. 발행 검사는 매번 다시 수행한다."""

from __future__ import annotations

import json
from collections.abc import Callable, Collection
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from generator.contracts import Article


@dataclass(frozen=True)
class PendingPost:
    topic_id: str
    article: Article
    sources: str


class PendingPostStore:
    # 같은 글 때문에 매일 멈추지 않도록 최초 실행 뒤 두 번까지만 이어 처리한다.
    MAX_RESUMES = 2
    MAX_AGE = timedelta(days=7)

    def __init__(
        self,
        path: Path,
        *,
        completed_topics: Callable[[], Collection[str]] = lambda: (),
    ):
        self.path = path
        self._completed_topics = completed_topics
        self.excluded_ids: set[str] = set()
        self._record: dict | None = None

    def _write(self, pending: dict | None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"version": 1, "pending": pending}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        self._record = pending

    def clear(self) -> None:
        # 삭제 대신 빈 기록을 캐시해야 이전 실행의 미완료 글이 다시 복원되지 않는다.
        self._write(None)

    def resume(self) -> PendingPost | None:
        self.excluded_ids.clear()
        if not self.path.exists():
            return None
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value["version"] != 1:
                raise ValueError("지원하지 않는 저장 형식")
            record = value["pending"]
            if record is None:
                self._record = None
                return None
            topic_id, sources = record["topic_id"], record["sources"]
            if not all(
                isinstance(item, str) and item.strip() for item in (topic_id, sources)
            ):
                raise ValueError("주제 또는 출처 누락")
            data = record["article"]
            for key in ("title", "body", "model"):
                if not isinstance(data[key], str) or not data[key].strip():
                    raise ValueError("본문 기록 오류")
            for key in ("tags", "source_urls"):
                if not isinstance(data[key], list) or not all(
                    isinstance(item, str) for item in data[key]
                ):
                    raise ValueError("본문 메타데이터 오류")
            article = Article(
                data["title"],
                data["body"],
                data["model"],
                tuple(data["tags"]),
                tuple(data["source_urls"]),
            )
            created = datetime.fromisoformat(record["created_at"])
            resumes = record["resumes"]
            if created.tzinfo is None or type(resumes) is not int or resumes < 0:
                raise ValueError("이어 실행 기록 오류")
            age = datetime.now(timezone.utc) - created
            if topic_id in self._completed_topics():
                self.clear()
                return None
            if age < timedelta(0) or age > self.MAX_AGE or resumes >= self.MAX_RESUMES:
                print("보존 본문의 이어 실행 횟수/기간 소진 — 다른 주제를 선택합니다.")
                self.excluded_ids.add(topic_id)
                self.clear()
                return None
            record["resumes"] += 1
            self._write(record)
            print(
                f"보존 본문 이어 실행 ({record['resumes']}/{self.MAX_RESUMES}): {article.title}"
            )
            return PendingPost(topic_id, article, sources)
        except (ValueError, KeyError, TypeError, AttributeError):
            print("보존 본문 형식 오류 — 새 주제를 선택합니다.")
            self.clear()
            return None

    def save(self, topic_id: str, article: Article, sources: str) -> None:
        previous = (
            self._record
            if self._record and self._record["topic_id"] == topic_id
            else {}
        )
        data = asdict(article)
        data.pop("presentation", None)
        self._write(
            {
                "topic_id": topic_id,
                "article": data,
                "sources": sources,
                "created_at": previous.get(
                    "created_at", datetime.now(timezone.utc).isoformat()
                ),
                "resumes": previous.get("resumes", 0),
            }
        )
