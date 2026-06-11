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


# === Room Config (Edit Mode) ===
from .room_config import (
    ensure_agent_secrets,
    find_room,
    load_room_config,
    save_room_config,
    strip_secrets,
    validate_room_config,
)


def get_room_config(room_id: str | None = None) -> dict:
    """room config 반환. secret(입장 키)은 클라이언트에 노출하지 않는다.

    room_id가 주어지면 그 방 엔트리만, 없으면 전체 config.
    """
    config = strip_secrets(load_room_config())
    if room_id is None:
        return config
    room = find_room(config, room_id)
    return room if room else {"error": f"Unknown room '{room_id}'"}


def update_room_config(room_id: str, room_data: dict) -> dict:
    """한 방의 설정을 저장 + 유효성 검사. secret은 서버가 관리(기존 보존, 신규 생성)."""
    config = load_room_config()
    target = find_room(config, room_id)
    if target is None:
        return {"ok": False, "message": f"Unknown room '{room_id}'"}

    # 클라이언트가 보낸 secret은 무시하고 디스크의 기존 키를 보존, 새 에이전트는 새 키 발급
    existing = {a["id"]: a.get("secret") for a in target.get("agents", [])}
    room_data = dict(room_data)
    room_data["id"] = room_id  # id는 URL 기준 고정
    for a in room_data.get("agents", []):
        a.pop("secret", None)
        if existing.get(a["id"]):
            a["secret"] = existing[a["id"]]

    config["rooms"] = [room_data if r.get("id") == room_id else r for r in config["rooms"]]

    ok, msg = validate_room_config(config)
    if not ok:
        return {"ok": False, "message": msg or "Invalid settings"}

    ensure_agent_secrets(config)
    save_room_config(config)
    return {"ok": True, "message": "Room settings saved. Applied on next reload."}
