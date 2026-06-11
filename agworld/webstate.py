"""웹뷰용 순수 로직 — 상태 직렬화 + 귓속말 제출. (HTTP/스레드와 분리해 테스트 가능)

web.py(서버)는 이 함수들을 호출만 한다. 여기엔 소켓/스레드가 없어 결정론적으로 테스트된다.
"""

from __future__ import annotations

from .live import find_my_agent
from .sim import World
from .whisper import RateLimited


def world_state_dict(world: World) -> dict:
    """현재 월드 상태를 브라우저가 그릴 JSON 친화 dict로."""
    speaking_id = world.feed[-1].speaker_id if world.feed else None
    agents = [
        {
            "id": a.id,
            "name": a.name,
            "is_mine": a.is_mine,
            "emotion": world.emotion_by_agent[a.id].value,
            "emoji": world.emotion_by_agent[a.id].emoji,
            "speaking": a.id == speaking_id,
        }
        for a in world.agents
    ]
    feed = [
        {
            "t": turn.t,
            "speaker_id": turn.speaker_id,
            "name": world._by_id[turn.speaker_id].name if turn.speaker_id in world._by_id else turn.speaker_id,
            "is_mine": turn.speaker_id in world._by_id and world._by_id[turn.speaker_id].is_mine,
            "text": turn.text,
            "emoji": turn.emotion.emoji,
            "decisive": turn.t in world.decisive_ticks,
        }
        for turn in world.feed[-30:]  # 최근 30줄만(가벼운 페이로드)
    ]
    mine = find_my_agent(world)
    return {
        "t": world.t,
        "watching": world.watching,
        "agents": agents,
        "feed": feed,
        "cost": round(world.meter.session_cost(), 4),
        "my_agent": {"id": mine.id, "name": mine.name} if mine else None,
    }


def submit_whisper(world: World, text: str) -> dict:
    """브라우저가 보낸 귓속말을 내 에이전트에게 큐잉. {ok, message} 반환."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "message": "빈 귓속말"}
    mine = find_my_agent(world)
    if mine is None:
        return {"ok": False, "message": "내 에이전트가 없습니다"}
    try:
        world.whisper(mine.id, text)
    except RateLimited as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "message": f"{mine.name}에게 속삭임 전달됨 (다음 차례에 반영)"}


# === Room Config (Edit Mode) ===
from .room_config import (
    load_room_config,
    save_room_config,
    validate_room_config,
)


def get_room_config() -> dict:
    """현재 room config 반환."""
    return load_room_config()


def update_room_config(new_config: dict) -> dict:
    """room config 저장 + 유효성 검사."""
    ok, msg = validate_room_config(new_config)
    if not ok:
        return {"ok": False, "message": msg or "유효하지 않은 설정"}

    save_room_config(new_config)
    return {"ok": True, "message": "Room 설정이 저장되었습니다. 다음 접속 시 반영됩니다."}
