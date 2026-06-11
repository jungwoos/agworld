"""Config로부터 World를 빌드하는 빌더."""

from __future__ import annotations

from .models import Agent, Emotion
from .providers import FakeProvider
from .sim import World


def _emotion_from_str(value: str) -> Emotion:
    return Emotion.coerce(value)


def build_agents_from_room(room: dict) -> list[Agent]:
    """방 엔트리의 agents 섹션으로 Agent 리스트 생성."""
    agents = []
    for data in room.get("agents", []):
        agent = Agent(
            id=str(data["id"]),
            name=str(data["name"]),
            persona_prompt=str(data["persona_prompt"]),
            is_mine=bool(data.get("is_mine", False)),
        )
        agents.append(agent)
    return agents


def build_canned_scripts(room: dict) -> dict[str, list[tuple[str, Emotion]]]:
    """방 엔트리에서 canned_lines를 FakeProvider용 스크립트로 변환."""
    scripts: dict[str, list[tuple[str, Emotion]]] = {}
    for data in room.get("agents", []):
        lines = data.get("canned_lines", [])
        scripts[data["id"]] = [
            (text, _emotion_from_str(emotion)) for text, emotion in lines
        ]
    return scripts


def build_world_from_room(room: dict) -> World:
    """방 엔트리(config["rooms"]의 원소)로부터 World를 생성."""
    agents = build_agents_from_room(room)
    scripts = build_canned_scripts(room)
    return World(agents, FakeProvider(scripts))
