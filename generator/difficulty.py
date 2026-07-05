"""주제 난이도 레벨링(1~5).

분야 안에서 '레벨 낮은(기초)' 주제부터 생성해 학습 순서(기초→심화)를 만든다.
- 미채점 주제만 LLM으로 1회 채점 → state/difficulty.json 에 캐시(이후 호출 0)
- 채점 실패(모델 죽음/파싱 깨짐) 시 키워드 휴리스틱으로 폴백(절대 안 멈춤)
"""
from __future__ import annotations

import json
import os
import re
import requests
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE_FILE = HERE / "state" / "difficulty.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_LEVEL = 3          # 캐시에 없을 때 안전 기본값
CHUNK = 30                 # 한 번에 채점할 주제 수(너무 많으면 모델이 흘림)

# 휴리스틱 폴백용 키워드. 라벨/id에 있으면 해당 레벨로.
_BASIC = [
    "overview", "intro", "introduction", "getting-started",
    "basic", "what-is", "quickstart", "glossary",
    "개요", "소개", "기본", "시작",
]
_ADVANCED = [
    "internal", "internals", "tuning", "optimization", "advanced", "consistency",
    "replication", "mvcc", "lock", "locking", "deadlock", "quorum", "partition",
    "sharding", "isolation", "wal", "vacuum", "recovery", "failover", "clustering",
    "성능", "최적화", "복제", "내부", "튜닝",
]


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def label_of(topic: dict) -> str:
    """채점/휴리스틱에 쓸 사람이 읽을 라벨. title_hint 우선, 없으면 id 슬러그."""
    if topic.get("title_hint"):
        return str(topic["title_hint"]).strip()
    tail = topic["id"].split("::", 1)[-1]
    tail = re.sub(r"\.(md|html?)$", "", tail)
    tail = tail.replace("/", " / ").replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", tail).strip() or topic["id"]


def heuristic_level(topic: dict) -> int:
    """모델 없이 단어 규칙으로 난이도 어림(폴백)."""
    text = (label_of(topic) + " " + topic["id"]).lower()
    if any(k in text for k in _BASIC):
        return 2
    if any(k in text for k in _ADVANCED):
        return 4
    depth = topic["id"].split("::", 1)[-1].count("/")  # URL 깊이 = 약한 심화 신호
    return 3 if depth < 3 else 4


def _score_chunk_with_llm(topics: list[dict], models: list[str], api_key: str) -> dict:
    """미채점 주제 묶음을 LLM으로 레벨링. {id: level} 반환. 전부 실패 시 예외."""
    labels = {t["id"]: label_of(t) for t in topics}
    rev: dict[str, str] = {}
    for tid, lab in labels.items():
        rev.setdefault(lab.strip().lower(), tid)

    listing = "\n".join(f'- "{lab}"' for lab in labels.values())
    system = (
        "You assign a learning-difficulty level (1-5) to each technical documentation "
        "topic, to build a study path for a backend developer.\n"
        "1 = foundational (overview/intro/basic concept a beginner learns first).\n"
        "2 = core mechanism.\n"
        "3 = general practical concept.\n"
        "4 = advanced (internals/tuning).\n"
        "5 = expert (consistency/replication/optimization/edge cases).\n"
        "Consider prerequisites: what must be understood first gets a lower level. "
        "Output ONLY a JSON object mapping each topic string (verbatim) to its integer "
        "level. Include every topic exactly once, no extra text."
    )
    user = "주제 목록:\n" + listing + '\n\n각 주제에 1~5 레벨을 매겨 JSON {"주제": 레벨} 형태로만 출력.'

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://lmj00.github.io",
        "X-Title": "lmj00-blog-generator",
    }
    last_err = "?"
    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=(10, 120))
        except requests.RequestException as e:
            last_err = f"{model}: request_error {e}"
            continue
        if resp.status_code != 200:
            last_err = f"{model}: http_{resp.status_code} {resp.text[:80]}"
            continue
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError) as e:
            last_err = f"{model}: parse_error {e}"
            continue
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if not m:
            last_err = f"{model}: no-json"
            continue
        try:
            raw = json.loads(m.group(0))
        except ValueError as e:
            last_err = f"{model}: bad-json {e}"
            continue
        out: dict[str, int] = {}
        for k, v in raw.items():
            tid = rev.get(str(k).strip().lower())
            if tid is None:
                continue
            try:
                lvl = int(v)
            except (ValueError, TypeError):
                continue
            out[tid] = min(5, max(1, lvl))
        if out:
            return out
        last_err = f"{model}: empty-map"
    raise RuntimeError(f"채점 모델 전부 실패: {last_err}")


def score(topics: list[dict], cfg: dict) -> dict:
    """요청 주제들의 레벨을 반환({id: level}). 미채점 주제만 채점 후 캐시 저장."""
    cache = load_cache()
    todo = [t for t in topics if t["id"] not in cache]
    if todo:
        models = cfg.get("difficulty_model_fallback") or cfg.get("model_fallback", [])
        api_key = os.environ.get("OPENROUTER_API_KEY")
        scored: dict[str, int] = {}
        if api_key and models:
            for i in range(0, len(todo), CHUNK):
                chunk = todo[i:i + CHUNK]
                try:
                    scored.update(_score_chunk_with_llm(chunk, models, api_key))
                except Exception as e:  # noqa: BLE001 — 어떤 실패든 휴리스틱으로 살린다
                    print(f"  [채점] LLM 실패({e}) → 휴리스틱 폴백")
                    for t in chunk:
                        scored[t["id"]] = heuristic_level(t)
        else:
            for t in todo:
                scored[t["id"]] = heuristic_level(t)
        # 혹시 응답에서 빠진 주제는 휴리스틱으로 마저 채움
        for t in todo:
            scored.setdefault(t["id"], heuristic_level(t))
        cache.update(scored)
        _save_cache(cache)
        print(f"  [채점] 신규 {len(todo)}개 레벨링 완료 → difficulty.json 캐시")
    return {t["id"]: cache.get(t["id"], DEFAULT_LEVEL) for t in topics}
