"""틱 스케줄러 + 발화자 선택.

TickScheduler 상태 머신 (슬립 온 디스커넥트):

        set_watching(True)
    ┌───────────────────────┐
    │                       ▼
 [SLEEPING]            [WATCHING]
    ▲   │  advance()->None     │  advance()-> t+1
    │   └──────────────────────┘
    └────── set_watching(False)

관전자가 볼 때만(WATCHING) 틱이 진행된다. 안 보면(SLEEPING) advance()가 None을 반환하고
t가 안 늘어난다 → 자는 동안 아무 일도 안 일어남 → 비용 캡이 정의상 완벽.
"""

from __future__ import annotations


class TickScheduler:
    def __init__(self, watching: bool = True, start_t: int = 0):
        self._watching = watching
        self._t = start_t

    @property
    def t(self) -> int:
        return self._t

    @property
    def watching(self) -> bool:
        return self._watching

    def set_watching(self, watching: bool) -> None:
        self._watching = watching

    def advance(self) -> int | None:
        """관전 중이면 t를 1 올려 반환. 자는 중이면 None(틱 진행 안 함)."""
        if not self._watching:
            return None
        self._t += 1
        return self._t


class SpeakerSelector:
    """라운드로빈 발화자 선택. 귓속말 받은 에이전트는 다음 틱 우선."""

    def __init__(self):
        self._cursor = 0

    def next_speaker(self, agent_ids: list[str], priority_id: str | None = None) -> str:
        if not agent_ids:
            raise ValueError("발화자 후보가 없음")
        if priority_id is not None and priority_id in agent_ids:
            # 귓속말 우선 — 라운드로빈 커서는 건드리지 않아 이후 회전이 공정하게 이어짐.
            return priority_id
        speaker = agent_ids[self._cursor % len(agent_ids)]
        self._cursor += 1
        return speaker
