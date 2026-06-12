"""웹뷰용 순수 로직 — 상태 직렬화 + 귓속말 제출. (HTTP/스레드와 분리해 테스트 가능)

web.py(서버)는 이 함수들을 호출만 한다. 여기엔 소켓/스레드가 없어 결정론적으로 테스트된다.
"""

from __future__ import annotations

from .sim import World
from .whisper import RateLimited


def world_state_dict(world: World, viewer_id: str | None = None) -> dict:
    """현재 월드 상태를 브라우저가 그릴 JSON 친화 dict로.

    viewer_id: 입장 키로 인증된 보는 사람의 에이전트 id. None이면 관전 모드 —
    my_agent 없음, is_mine 강조 없음. '내 것'은 전역 플래그가 아니라 보는 사람 기준.
    """
    speaking_id = world.feed[-1].speaker_id if world.feed else None
    agents = [
        {
            "id": a.id,
            "name": a.name,
            "is_mine": a.id == viewer_id,
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
            "is_mine": turn.speaker_id == viewer_id,
            "text": turn.text,
            "emoji": turn.emotion.emoji,
            "decisive": turn.t in world.decisive_ticks,
        }
        for turn in world.feed[-30:]  # 최근 30줄만(가벼운 페이로드)
    ]
    mine = world._by_id.get(viewer_id) if viewer_id else None
    return {
        "t": world.t,
        "watching": world.watching,
        "agents": agents,
        "feed": feed,
        "cost": round(world.meter.session_cost(), 4),
        "my_agent": {"id": mine.id, "name": mine.name} if mine else None,
    }


def submit_whisper(world: World, text: str, viewer_id: str | None = None) -> dict:
    """브라우저가 보낸 귓속말을 보는 사람의 에이전트에게 큐잉. {ok, message} 반환."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "message": "Empty whisper"}
    if not viewer_id:
        return {"ok": False, "message": "Spectator mode — open your agent invite link to whisper"}
    mine = world._by_id.get(viewer_id)
    if mine is None:
        return {"ok": False, "message": "Your agent isn't in this place"}
    try:
        world.whisper(mine.id, text)
    except RateLimited as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "message": f"Whispered to {mine.name} (lands on their next turn)"}


# === Room 데이터 + 가구 편집 ===
from .room import room_dict_from_items, sanitize_items, town_dict
from .room_config import (
    find_room,
    load_room_config,
    room_items,
    room_owner,
    save_room_config,
)


def get_room_data(place: str) -> dict:
    """GET /room?place= 응답 — 방은 config 기반, town은 하드코딩."""
    if place == "town":
        return town_dict()
    config = load_room_config()
    items = room_items(config, place)
    if items is None:  # 모르는 장소 → 첫 방으로 폴백
        first = config["rooms"][0]
        return room_dict_from_items(first["id"], room_items(config, first["id"]))
    return room_dict_from_items(place, items)


def update_room_items(room_id: str, items: object, viewer_id: str | None = None) -> dict:
    """방 가구 저장. 방 주인만 편집 가능. {ok, message} 반환."""
    if not viewer_id:
        return {"ok": False, "message": "Spectator mode — open your invite link to edit"}
    config = load_room_config()
    target = find_room(config, room_id)
    if target is None:
        return {"ok": False, "message": f"Unknown room '{room_id}'"}
    if viewer_id != room_owner(config, room_id):
        return {"ok": False, "message": "Only the room owner can edit furniture"}

    ok, msg, cleaned = sanitize_items(items)
    if not ok:
        return {"ok": False, "message": msg}

    target["items"] = cleaned
    save_room_config(config)
    return {"ok": True, "message": "Room saved!"}
