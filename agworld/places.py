"""장소(places) 구성 — Config 기반 Room + 기존 Town 지원.

- room: room_config.json으로 동적 관리 (Room Edit Mode 대상)
- town: 기존 하드코딩 (추후 Config 확장 가능)
"""

from __future__ import annotations

from .models import Agent, Emotion
from .providers import FakeProvider
from .room_builder import build_world_from_config
from .room_config import load_room_config
from .sim import World


# === Town (기존 하드코딩 유지) ===
TOWN_SPECS = [
    ("sona", "소나", "동네의 다정한 중재자. 분위기를 살핀다.", [
        ("다들 오늘 기분 어때?", Emotion.JOY),
        ("천천히 얘기해도 돼.", Emotion.THINKING),
        ("우리 동네 사람들 다 좋아.", Emotion.AFFECTION),
    ], True),
    ("ruri", "루리", "솔직하고 감정 기복이 있다.", [
        ("어제 일 아직 좀 서운해.", Emotion.SAD),
        ("아 몰라, 신경 안 쓸래.", Emotion.ANGER),
        ("그래도 같이 있으면 좋네.", Emotion.JOY),
    ], False),
    ("dan", "단", "무심하지만 정 많은 이웃.", [
        ("커피 마실 사람?", Emotion.NEUTRAL),
        ("나도 사실 좀 미안했어.", Emotion.AFFECTION),
    ], False),
    ("mina", "미나", "수다스럽고 소문을 좋아한다.", [
        ("그거 들었어? 옆집 얘기.", Emotion.SURPRISE),
        ("에이 진짜야 진짜.", Emotion.JOY),
        ("비밀인데 말이야...", Emotion.THINKING),
    ], False),
    ("hodu", "호두", "느긋하고 낙천적.", [
        ("날씨 좋다~ 산책 갈까.", Emotion.JOY),
        ("뭐든 다 잘 될 거야.", Emotion.AFFECTION),
    ], False),
    ("jinwoo", "진우", "진지하고 걱정이 많다.", [
        ("그게 정말 괜찮을까...", Emotion.THINKING),
        ("난 좀 불안한데.", Emotion.SAD),
    ], False),
    ("byeol", "별이", "엉뚱하고 명랑하다.", [
        ("우와 저것 봐!", Emotion.SURPRISE),
        ("헤헤 재밌다.", Emotion.JOY),
    ], False),
    ("kkami", "까미", "조용하고 관찰력이 좋다.", [
        ("...다들 표정이 다르네.", Emotion.THINKING),
        ("난 듣는 게 좋아.", Emotion.NEUTRAL),
    ], False),
    ("yoon", "윤", "예의 바르고 차분하다.", [
        ("안녕하세요, 오늘도 평안하길.", Emotion.AFFECTION),
        ("천천히 가도 괜찮아요.", Emotion.JOY),
    ], False),
    ("tori", "토리", "장난기 많고 시비를 잘 건다.", [
        ("야 너 그거 진심이야?", Emotion.SURPRISE),
        ("에이 농담이야 농담.", Emotion.JOY),
        ("삐졌어? 미안미안.", Emotion.AFFECTION),
    ], False),
]


def _build_town_world() -> World:
    agents = [Agent(i, n, p, is_mine=mine) for (i, n, p, _lines, mine) in TOWN_SPECS]
    scripts = {i: lines for (i, _n, _p, lines, _mine) in TOWN_SPECS}
    return World(agents, FakeProvider(scripts))


def build_places() -> dict:
    """장소 id -> {title, world} 반환.
    
    room은 room_config.json 기반, town은 기존 하드코딩.
    """
    config = load_room_config()
    room_world = build_world_from_config(config)
    room_title = config["room"]["title"]

    return {
        "room": {"title": room_title, "world": room_world},
        "town": {"title": "우리 동네", "world": _build_town_world()},
    }


def places_meta(places: dict) -> list[dict]:
    """클라이언트 탭용 목록: [{id, title, agents}]."""
    return [
        {"id": pid, "title": p["title"], "agents": len(p["world"].agents)}
        for pid, p in places.items()
    ]
