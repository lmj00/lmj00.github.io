"""동기 API 요청의 대기 로그. 요청·재시도·시간 제한 정책은 변경하지 않는다."""

from __future__ import annotations

from contextlib import contextmanager
from threading import Event, Thread
from time import monotonic
from typing import Iterator


@contextmanager
def request_progress(model: str, purpose: str, *, detail=None) -> Iterator[None]:
    """30초마다 경과 시간만 표시한다. 서버의 생성 진행률을 의미하지 않는다.

    HTTP 호출은 호출자 스레드에서 수행한다. 보조 스레드는 로그만 출력하므로
    대기 로그 때문에 API 요청이 늘거나 Ctrl+C 이후 백그라운드 요청이 남지 않는다.
    프롬프트, 인증 헤더, 응답 원문은 받지도 출력하지도 않는다.
    """
    started = monotonic()
    stopped = Event()

    def report_wait() -> None:
        while not stopped.wait(30):
            elapsed = int(monotonic() - started)
            print(
                f"  [응답 대기] {purpose} / {model}: "
                f"{elapsed // 60}분 {elapsed % 60:02d}초 경과 "
                + (detail() if detail is not None else "(생성 진행률은 알 수 없음)"),
                flush=True,
            )

    print(f"  [요청 시작] {purpose} / {model}", flush=True)
    reporter = Thread(target=report_wait, name="llm-request-progress", daemon=True)
    reporter.start()
    outcome = "응답 수신 완료"
    try:
        yield
    except KeyboardInterrupt:
        outcome = "로컬 실행 중단"
        raise
    except BaseException as exc:
        # 예외 원문에는 요청 정보가 포함될 수 있어 종류만 출력한다.
        outcome = f"요청 실패 ({type(exc).__name__})"
        raise
    finally:
        stopped.set()
        reporter.join()
        elapsed = monotonic() - started
        print(
            f"  [요청 종료] {purpose} / {model}: {outcome}, {elapsed:.1f}초 "
            "(출력 품질 판정과 별도)",
            flush=True,
        )
