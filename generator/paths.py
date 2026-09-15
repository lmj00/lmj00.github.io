"""패키지 위치와 무관하게 유지되는 저장소 경로. import는 파일을 만들지 않는다."""

from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GENERATOR_DIR.parent
PROMPTS_DIR = GENERATOR_DIR / "prompts"
STATE_DIR = GENERATOR_DIR / "state"
ASSETS_DIR = PROJECT_ROOT / "assets"
