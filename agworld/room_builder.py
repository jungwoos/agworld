"""Config로부터 World를 빌드하는 빌더."""

from __future__ import annotations

from .models import Agent, Emotion
from .providers import FakeProvider
from .room_config import load_room_config
from .sim import World


def _emotion_from_str(value: str) -> Emotion:
    return Emotion.coerce(value)


def build_agents_from_config(config: dict) -> list[Agent]:
    """Config의 agents 섹션으로 Agent 리스트 생성."""
    room = config.get("room", {})
    agents_data = room.get("agents", [])

    agents = []
    for data in agents_data:
        agent = Agent(
            id=str(data["id"]),
            name=str(data["name"]),
            persona_prompt=str(data["persona_prompt"]),
            is_mine=bool(data.get("is_mine", False)),
        )
        agents.append(agent)
    return agents


def build_canned_scripts(config: dict) -> dict[str, list[tuple[str, Emotion]]]:
    """Config에서 canned_lines를 FakeProvider용 스크립트로 변환."""
    room = config.get("room", {})
    agents_data = room.get("agents", [])

    scripts: dict[str, list[tuple[str, Emotion]]] = {}
    for data in agents_data:
        agent_id = data["id"]
        lines = data.get("canned_lines", [])
        scripts[agent_id] = [
            (text, _emotion_from_str(emotion)) for text, emotion in lines
        ]
    return scripts


def build_world_from_config(config: dict | None = None) -> World:
    """room_config로부터 World를 생성."""
    if config is None:
        config = load_room_config()

    agents = build_agents_from_config(config)
    scripts = build_canned_scripts(config)
    provider = FakeProvider(scripts)

    return World(agents, provider)


def build_places_from_config() -> dict:
    """Config 기반으로 places dict 생성 (room + town은 나중에 확장)."""
    world = build_world_from_config()
    return {
        "room": {
            "title": load_room_config()["room"]["title"],
            "world": world,
        }
    }
