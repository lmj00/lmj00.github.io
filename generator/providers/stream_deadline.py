"""첫 유효 출력 전까지만 적용하는 로컬 스트림 대기 제한.

읽기 스레드가 응답을 소유한다. deadline 만료 시 호출자는 즉시 다음 후보로 진행하며,
읽기 스레드는 다음 수신/소켓 타임아웃에 응답을 닫는다. 공급자 과금 취소를 보장하지 않는다.
"""

from __future__ import annotations

from queue import Empty, Full, Queue
from threading import Event, Thread


class FirstContentTimeout(ValueError):
    pass


def deadline_chunks(response, observation, seconds):
    """Heartbeat·공백·추론은 첫 출력이 아니다. 버퍼링 중이어도 대기는 만료된다."""
    queue = Queue(maxsize=8)
    stopped = Event()

    def send(kind, value):
        while not stopped.is_set():
            try:
                queue.put((kind, value), timeout=0.1)
                return
            except Full:
                pass

    def receive():
        try:
            # Small reads expose keepalives promptly; only local opt-in uses this.
            for chunk in response.iter_content(chunk_size=1):
                if stopped.is_set():
                    break
                if chunk:
                    send("chunk", chunk)
        except Exception as exc:
            send("error", exc)
        finally:
            try:
                response.close()
            except Exception as exc:
                send("error", exc)
            finally:
                send("done", None)

    worker = Thread(target=receive, name="local-design-stream", daemon=True)
    worker.start()
    try:
        while True:
            remaining = None
            if observation.state["first_content_seconds"] is None:
                remaining = seconds - observation.elapsed()
                if remaining <= 0:
                    raise FirstContentTimeout(f"첫 출력 대기 {seconds:g}초 초과")
            try:
                kind, value = queue.get(timeout=remaining)
            except Empty:
                raise FirstContentTimeout(f"첫 출력 대기 {seconds:g}초 초과") from None
            if kind == "done":
                return
            if kind == "error":
                raise value
            yield value
    finally:
        # Do not synchronously close a response being read: that can itself block.
        # The daemon owns cleanup; the bounded queue cannot accumulate a full answer.
        stopped.set()
