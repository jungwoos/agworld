"""실시간 관전 루프의 순수 로직 — I/O와 분리해 테스트 가능하게.

설계: 틱은 실시간 간격(기본 10초)으로 진행되고, 유저는 보면서 아무 때나 귓속말한다.
귓속말은 항상 '내 에이전트'(is_mine) 귀에만 — 신의 속삭임은 내 캐릭터한테만(office-hours 결정).

cli.run_live가 select로 stdin을 폴링하며 이 함수들을 호출한다. 여기 함수들은 시간/입력에
의존하지 않아 결정론적으로 테스트된다.
"""

from __future__ import annotations

from .models import Agent
from .sim import World
from .whisper import RateLimited

QUIT = "quit"
WHISPER = "whisper"
SKIP = "skip"


def find_my_agent(world: World) -> Agent | None:
    """is_mine 에이전트를 찾는다. 귓속말 기본 대상."""
    for a in world.agents:
        if a.is_mine:
            return a
    return None


def parse_input(raw: str) -> tuple[str, str]:
    """입력 한 줄 → (종류, 페이로드).

    - 빈 줄          → (SKIP, "")
    - q / quit / 종료 → (QUIT, "")
    - 그 외          → (WHISPER, 정리된 텍스트)
    """
    text = (raw or "").strip()
    if not text:
        return (SKIP, "")
    if text.lower() in ("q", "quit", "종료"):
        return (QUIT, "")
    return (WHISPER, text)


def apply_command(world: World, raw: str) -> tuple[str, str]:
    """입력을 처리한다. (종류, 유저에게 보일 상태 메시지) 반환.

    WHISPER는 내 에이전트에게 큐잉. 레이트 리밋이면 안내 메시지.
    """
    kind, payload = parse_input(raw)
    if kind == QUIT:
        return (QUIT, "관전을 끕니다. 캐릭터들도 잠듭니다 💤")
    if kind == SKIP:
        return (SKIP, "")
    mine = find_my_agent(world)
    if mine is None:
        return (SKIP, "내 에이전트가 없어 귓속말할 대상이 없습니다.")
    try:
        world.whisper(mine.id, payload)
    except RateLimited as e:
        return (WHISPER, f"⏳ {e}")
    return (WHISPER, f"🤫 {mine.name}에게 속삭임 전달됨 (다음 차례에 반영)")
