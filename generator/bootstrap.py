"""CLI와 로컬 도구가 공유하는 설정 로딩. import 시 API 호출이나 환경 변경 없음."""

import json
import os

from generator.paths import GENERATOR_DIR, PROMPTS_DIR


def load_dotenv() -> None:
    """generator/.env가 있으면 기존 환경 변수를 보존하며 로컬 설정을 추가한다."""
    env_path = GENERATOR_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> dict:
    return json.loads((GENERATOR_DIR / "sources.json").read_text(encoding="utf-8"))


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")
