"""명시적으로 선택한 로컬 실험에만 적용하는 설정. 예약 실행 설정은 변경하지 않는다."""

from __future__ import annotations

from copy import deepcopy


def add_local_options(parser):
    parser.add_argument(
        "--local-fast",
        action="store_true",
        help="로컬 디자인 생성은 Qwen 우선, 첫 출력 대기 120초 (검수 유지)",
    )
    parser.add_argument(
        "--preview-design-model",
        help="이번 로컬 실행에서 우선할 디자인 모델 (설정된 후보 중 선택)",
    )
    parser.add_argument(
        "--first-content-timeout",
        type=int,
        metavar="SECONDS",
        help="로컬 구조화 API의 첫 출력 대기 시간 (양의 초, 출력 길이 제한 아님)",
    )


def local_settings(
    cfg: dict, *, fast=False, model=None, timeout=None
) -> tuple[dict, int | None]:
    cfg = deepcopy(cfg)
    if timeout is not None and (type(timeout) is not int or timeout <= 0):
        raise ValueError("첫 출력 대기 시간은 양의 정수여야 합니다.")
    chain = cfg.get("design_model_fallback", [])
    preferred = model or ("qwen/qwen3.8-flash" if fast else None)
    if preferred:
        if preferred not in chain:
            raise ValueError(
                "우선 모델은 design_model_fallback에 설정된 후보여야 합니다."
            )
        cfg["design_model_fallback"] = [
            preferred,
            *(item for item in chain if item != preferred),
        ]
    return cfg, timeout if timeout is not None else 120 if fast else None
