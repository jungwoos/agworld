"""귓속말 큐 — 유저 힌트를 대상 에이전트의 다음 가용 틱까지 보류.

귓속말은 즉시 반영되지 않는다. 큐잉됐다가, 대상이 다음에 발화할 차례가 오면 그 틱의
프롬프트에 주입된다. 발화 안 하는 에이전트에게 넣어도 차례가 올 때까지 안전하게 대기.

레이트 리밋: 한 윈도우(틱 수 기준) 안에서 N회로 제한. 어뷰즈/스팸 방지.
"""

from __future__ import annotations

from collections import deque

from .context import sanitize_whisper

DEFAULT_RATE_LIMIT = 3          # 윈도우당 최대 귓속말 수
DEFAULT_RATE_WINDOW_TICKS = 5   # 윈도우 크기(틱)


class RateLimited(Exception):
    """레이트 리밋 초과. 유저에게 잠시 후 다시 시도하라고 안내."""


class WhisperQueue:
    def __init__(
        self,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        rate_window_ticks: int = DEFAULT_RATE_WINDOW_TICKS,
    ):
        # 대상별 보류 큐: agent_id -> deque[str]
        self._pending: dict[str, deque[str]] = {}
        self._rate_limit = rate_limit
        self._rate_window = rate_window_ticks
        # 레이트 리밋은 대상별 — 각자 자기 에이전트에게 속삭이므로 유저별 분리 효과
        self._recent_tick_stamps: dict[str, deque[int]] = {}

    def enqueue(self, target_id: str, raw_text: str, current_tick: int) -> None:
        """귓속말을 대상 큐에 넣는다. 레이트 리밋 초과 시 RateLimited."""
        stamps = self._recent_tick_stamps.setdefault(target_id, deque())
        self._evict_old(stamps, current_tick)
        if len(stamps) >= self._rate_limit:
            raise RateLimited(
                f"Limit is {self._rate_limit} whispers per window — try again in a moment."
            )
        clean = sanitize_whisper(raw_text)
        if not clean:
            return  # 빈 귓속말은 조용히 무시(레이트 카운트도 안 함)
        self._pending.setdefault(target_id, deque()).append(clean)
        stamps.append(current_tick)

    def pop_for(self, agent_id: str) -> str | None:
        """대상의 다음 보류 귓속말을 꺼낸다(FIFO). 없으면 None."""
        q = self._pending.get(agent_id)
        if not q:
            return None
        text = q.popleft()
        if not q:
            del self._pending[agent_id]
        return text

    def has_pending(self, agent_id: str | None = None) -> bool:
        if agent_id is None:
            return any(self._pending.values())
        q = self._pending.get(agent_id)
        return bool(q)

    def _evict_old(self, stamps: deque[int], current_tick: int) -> None:
        cutoff = current_tick - self._rate_window
        while stamps and stamps[0] <= cutoff:
            stamps.popleft()
