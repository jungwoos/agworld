"""장소(places) 구성 — Config 기반 다중 Room + Town.

- rooms: room_config.json으로 동적 관리 (사람마다 자기 방, Room Edit Mode 대상)
- town: 하드코딩 (고정 이웃 10인)
"""

from __future__ import annotations

from .models import Agent, Emotion
from .providers import FakeProvider
from .room_builder import build_world_from_room
from .room_config import load_room_config
from .sim import World


# === Town (하드코딩 유지) ===
TOWN_SPECS = [
    ("jungs", "Jungs", "Easygoing but sharp. Keeps an eye on the vibe.", [
        ("How's everyone doing today?", Emotion.JOY),
        ("Take your time, no rush.", Emotion.THINKING),
        ("This town's pretty great, honestly.", Emotion.AFFECTION),
    ], True),
    ("jayy", "Jayy", "Playful and blunt, secretly sentimental.", [
        ("Still a bit salty about yesterday.", Emotion.SAD),
        ("Whatever, not my problem.", Emotion.ANGER),
        ("Okay fine, this is nice.", Emotion.JOY),
    ], False),
    ("dan", "Dan", "Indifferent on the outside, warm on the inside.", [
        ("Anyone want coffee?", Emotion.NEUTRAL),
        ("I felt a little bad too, honestly.", Emotion.AFFECTION),
    ], False),
    ("mina", "Mina", "Chatty and loves gossip.", [
        ("Did you hear? About the house next door?", Emotion.SURPRISE),
        ("No really, it's true!", Emotion.JOY),
        ("It's a secret, but...", Emotion.THINKING),
    ], False),
    ("hodu", "Hodu", "Laid-back optimist.", [
        ("Great weather~ walk, anyone?", Emotion.JOY),
        ("It'll all work out.", Emotion.AFFECTION),
    ], False),
    ("jinwoo", "Jinwoo", "Serious and a bit of a worrier.", [
        ("Are we sure that's okay...?", Emotion.THINKING),
        ("I don't know, I'm nervous.", Emotion.SAD),
    ], False),
    ("byeol", "Byeol", "Quirky and cheerful.", [
        ("Whoa, look at that!", Emotion.SURPRISE),
        ("Hehe, this is fun.", Emotion.JOY),
    ], False),
    ("kkami", "Kkami", "Quiet and observant.", [
        ("...Everyone looks different today.", Emotion.THINKING),
        ("I prefer listening.", Emotion.NEUTRAL),
    ], False),
    ("yoon", "Yoon", "Polite and composed.", [
        ("Hello, hope you're at peace today.", Emotion.AFFECTION),
        ("It's okay to go slow.", Emotion.JOY),
    ], False),
    ("tori", "Tori", "Mischievous, loves to tease.", [
        ("Wait, you were serious?", Emotion.SURPRISE),
        ("Kidding, kidding.", Emotion.JOY),
        ("Aw, don't sulk. Sorry, sorry.", Emotion.AFFECTION),
    ], False),
]


def _build_town_world() -> World:
    agents = [Agent(i, n, p, is_mine=mine) for (i, n, p, _lines, mine) in TOWN_SPECS]
    scripts = {i: lines for (i, _n, _p, lines, _mine) in TOWN_SPECS}
    return World(agents, FakeProvider(scripts))


def build_places() -> dict:
    """장소 id -> {title, world} 반환.

    rooms는 room_config.json 기반(사람마다 자기 방), town은 하드코딩.
    """
    config = load_room_config()
    places = {}
    for room in config["rooms"]:
        places[room["id"]] = {"title": room["title"], "world": build_world_from_room(room)}
    places["town"] = {"title": "Town", "world": _build_town_world()}
    return places


def places_meta(places: dict) -> list[dict]:
    """클라이언트 탭용 목록: [{id, title, agents}]."""
    return [
        {"id": pid, "title": p["title"], "agents": len(p["world"].agents)}
        for pid, p in places.items()
    ]
