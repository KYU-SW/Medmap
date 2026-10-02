"""기기 간 인계 코드(Phase A S1): 환자 휴대폰에서 만든 세션을 진료실 PC 가 8자리 번호로 한 번 가져간다.

계약: docs/superpowers/specs/2026-10-01-medmap-illness-episode-phase-a.md rev2 §0-A
- **메모리 전용**: 디스크·DB·로그 0. 서버가 재시작되면 대기 중인 인계는 사라진다(의도).
- 1회용(가져가면 즉시 삭제) · 15분 만료 · 대기 상한 · 잘못됨/만료/사용됨을 구분하지 않는다(추측 방지).
- 서버 전체 기준 실패 20회(5분 창) → 5분 잠금. 잠금 중에는 맞는 번호도 거부한다.
- 기기(접속 주소)별 실패 5회(5분 창) → 그 기기만 5분 잠금. 잠긴 기기의 시도는 전체 실패에 세지 않는다
  → 한 기기가 두드려도 전체 인계가 막히지 않고(서비스 방해 완화), 전체 상한 20회/5분은 그대로(추측 방어 불변).
  주소는 메모리에만, 로그 없음. 역방향 프록시 뒤에서는 모두 같은 주소로 보이므로 기기별 잠금이 전체 잠금(5회)처럼 동작한다.
  서버는 --no-proxy-headers 로 띄운다(uvicorn 기본은 루프백 접속의 X-Forwarded-For 로 주소를 바꿔 위조 가능).
- 내용은 지금 같은 브라우저 인계와 같다(medmap-session-v1 + 확인된 cache). 원문·전사문 없음.
"""
from __future__ import annotations

import copy
import secrets
import threading
import time

CODE_DIGITS = 8
TTL_S = 15 * 60
CAPACITY = 50
FAIL_LIMIT = 20
FAIL_WINDOW_S = 5 * 60
LOCK_S = 5 * 60
CLIENT_FAIL_LIMIT = 5


class HandoffInvalid(Exception):
    """번호가 없음·만료·이미 사용됨 — 이유를 구분하지 않는다."""

    def __init__(self):
        super().__init__("HANDOFF_CODE_INVALID")


class HandoffLocked(Exception):
    def __init__(self):
        super().__init__("HANDOFF_LOCKED")


class HandoffCapacity(Exception):
    def __init__(self):
        super().__init__("HANDOFF_CAPACITY")


class HandoffStore:
    def __init__(self, *, ttl_s: float = TTL_S, capacity: int = CAPACITY, clock=time.monotonic):
        self.ttl_s = ttl_s
        self.capacity = capacity
        self._clock = clock
        self._items: dict[str, tuple[float, dict]] = {}      # code → (expires_at, payload)
        self._failures: list[float] = []                      # 최근 실패 시각(FAIL_WINDOW_S 안)
        self._locked_until = 0.0
        self._client_failures: dict[str, list[float]] = {}   # 기기 → 최근 실패 시각(FAIL_WINDOW_S 안)
        self._client_locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        for code in [c for c, (exp, _) in self._items.items() if exp <= now]:
            del self._items[code]
        self._failures = [t for t in self._failures if now - t < FAIL_WINDOW_S]
        for client in list(self._client_failures):
            recent = [t for t in self._client_failures[client] if now - t < FAIL_WINDOW_S]
            if recent:
                self._client_failures[client] = recent
            else:
                del self._client_failures[client]
        for client in [c for c, until in self._client_locked_until.items() if until <= now]:
            del self._client_locked_until[client]

    def create(self, payload: dict) -> str:
        with self._lock:
            now = self._clock()
            self._purge(now)
            if len(self._items) >= self.capacity:
                raise HandoffCapacity()
            while True:
                code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
                if code not in self._items:
                    break
            self._items[code] = (now + self.ttl_s, copy.deepcopy(payload))
            return code

    def claim(self, code: str, client: str | None = None) -> dict:
        """client = 접속 주소(기기별 잠금). None 이면 전체 잠금만 적용한다."""
        with self._lock:
            now = self._clock()
            self._purge(now)
            if client is not None and client in self._client_locked_until:
                raise HandoffLocked()                     # 잠긴 기기: 전체 실패에 세지 않는다
            if now < self._locked_until:
                raise HandoffLocked()
            item = self._items.pop(code, None) if isinstance(code, str) else None
            if item is None:
                self._failures.append(now)
                if len(self._failures) >= FAIL_LIMIT:
                    self._locked_until = now + LOCK_S
                    self._failures = []
                if client is not None:
                    mine = self._client_failures.setdefault(client, [])
                    mine.append(now)
                    if len(mine) >= CLIENT_FAIL_LIMIT:
                        self._client_locked_until[client] = now + LOCK_S
                        del self._client_failures[client]
                raise HandoffInvalid()
            return item[1]

    def tracked_clients(self) -> int:
        """메모리에 남은 기기 기록 수(테스트·상한 확인용, 주소는 내보내지 않는다)."""
        with self._lock:
            self._purge(self._clock())
            return len(set(self._client_failures) | set(self._client_locked_until))

    def pending(self) -> int:
        with self._lock:
            self._purge(self._clock())
            return len(self._items)
