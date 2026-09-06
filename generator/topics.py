"""미생성 주제 풀에서 다음 주제를 고르는 정책."""

from __future__ import annotations

import random

import catalog
import dedup
import difficulty


def _pick_lowest_level(bucket: list[dict], cfg: dict) -> dict:
    """후보 묶음에서 가장 기초인 레벨을 고르고 동레벨이면 무작위 선택."""
    levels = difficulty.score(bucket, cfg)
    min_level = min(levels[topic["id"]] for topic in bucket)
    finalists = [topic for topic in bucket if levels[topic["id"]] == min_level]
    print(f"  난이도 레벨 {min_level}(기초 우선) 후보 {len(finalists)}개 중 선택")
    return random.choice(finalists)


def pick_balanced(undone: list[dict], cfg: dict) -> dict:
    """분야 가중치를 적용한 뒤 해당 분야의 기초 주제를 선택한다."""
    groups = cfg.get("groups")
    weights = cfg.get("group_weights")
    if not groups or not weights:
        return _pick_lowest_level(undone, cfg)

    id_to_group = {}
    for group_name, catalog_ids in groups.items():
        for catalog_id in catalog_ids:
            id_to_group[catalog_id] = group_name

    buckets: dict[str, list] = {}
    for candidate in undone:
        catalog_id = candidate["id"].split("::")[0]
        group = id_to_group.get(catalog_id, "기타")
        buckets.setdefault(group, []).append(candidate)

    available = [(group, weights.get(group, 1)) for group in buckets]
    chosen = random.choices(
        [group for group, _ in available],
        weights=[weight for _, weight in available],
    )[0]
    print(f"  분야 선택: {chosen} ({len(buckets[chosen])}개 중)")
    return _pick_lowest_level(buckets[chosen], cfg)


def select_topic(cfg: dict, forced_id: str | None = None) -> dict | None:
    """수동 주제를 우선하고, 없으면 공식문서 카탈로그에서 선택한다."""
    topic = dedup.pick_next_topic(
        cfg.get("topics", []),
        forced_id=forced_id,
    )
    if topic is not None or forced_id:
        return topic

    print("카탈로그에서 주제 자동 발굴 중...")
    pool = catalog.build_pool(cfg.get("catalogs", []))
    done = set(dedup.load_done())
    undone = [candidate for candidate in pool if candidate["id"] not in done]
    print(f"  전체 후보 {len(pool)}개 / 미생성 {len(undone)}개")
    return pick_balanced(undone, cfg) if undone else None


class CatalogTopicRepository:
    """수동 주제와 공식문서 카탈로그를 사용하는 현재 주제 저장소."""

    def select(self, cfg: dict, forced_id: str | None = None) -> dict | None:
        return select_topic(cfg, forced_id)

    def mark_done(self, topic_id: str) -> None:
        dedup.mark_done(topic_id)
