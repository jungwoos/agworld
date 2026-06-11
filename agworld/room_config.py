"""Room Config 관리 — JSON 기반 다중 Room 정의 로드/저장/검증.

Config 스키마 (v2 — 사람마다 자기 방):
{
  "rooms": [
    {
      "id": "jungs",                 # place id이자 방 주인 에이전트 id와 동일하게 둔다
      "title": "Jungs' Room",
      "max_agents": 5,
      "agents": [
        {
          "id": "jungs",
          "name": "Jungs",
          "persona_prompt": "...",
          "is_mine": true,           # 방 주인 표시(레거시/콘솔용). 웹 정체성은 입장 키 기준.
          "canned_lines": [["text", "emotion"], ...],
          "secret": "..."            # 입장 키(로컬 폴백). salt 모드에선 무시됨.
        }
      ]
    }
  ]
}

이전 v1 스키마({"room": {...}})를 만나면 기본값으로 대체한다.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import secrets as _secrets
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "room_config.json"

# 입장 키 파생용 salt. 설정돼 있으면 키를 여기서 파생(저장소/디스크에 비밀 없음).
# Render처럼 디스크가 휘발성인 환경에서도 재배포 간 키가 안 바뀐다.
KEY_SALT_ENV = "AGWORLD_KEY_SALT"


def _gen_secret() -> str:
    """에이전트 입장 키 생성 (URL-safe, 8자)."""
    return _secrets.token_urlsafe(6)


def _derived_secret(agent_id: str, salt: str) -> str:
    """salt + agent_id에서 결정론적으로 입장 키 파생 (URL-safe, 8자)."""
    digest = _hmac.new(salt.encode(), agent_id.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest)[:8].decode()


def _default_room_config() -> dict[str, Any]:
    """기본 설정 — jungs와 jayy가 각자 자기 방을 가진다."""
    return {
        "rooms": [
            {
                "id": "jungs",
                "title": "Jungs' Room",
                "max_agents": 5,
                "agents": [
                    {
                        "id": "jungs",
                        "name": "Jungs",
                        "persona_prompt": "Easygoing but sharp host. Likes things tidy.",
                        "is_mine": True,
                        "canned_lines": [
                            ["Finally home. Today was a lot.", "neutral"],
                            ["Dan, did you eat my snacks again?", "surprise"],
                            ["Eh, whatever. Wanna watch something?", "joy"],
                        ],
                    },
                    {
                        "id": "dan",
                        "name": "Dan",
                        "persona_prompt": "Acts indifferent but soft-hearted, quick to apologize.",
                        "is_mine": False,
                        "canned_lines": [
                            ["...Maybe. They were just sitting there.", "neutral"],
                            ["My bad — I'll buy you new ones.", "affection"],
                            ["So what are we watching?", "thinking"],
                        ],
                    },
                ],
            },
            {
                "id": "jayy",
                "title": "Jayy's Room",
                "max_agents": 5,
                "agents": [
                    {
                        "id": "jayy",
                        "name": "Jayy",
                        "persona_prompt": "Playful and blunt, secretly sentimental.",
                        "is_mine": True,
                        "canned_lines": [
                            ["My room, my rules.", "joy"],
                            ["Mina, quit moving my stuff around.", "anger"],
                            ["...Fine, you can stay.", "affection"],
                        ],
                    },
                    {
                        "id": "mina",
                        "name": "Mina",
                        "persona_prompt": "Chatty neighbor who loves gossip.",
                        "is_mine": False,
                        "canned_lines": [
                            ["Your room is basically my room.", "joy"],
                            ["Did you hear about the neighbors?", "surprise"],
                            ["Okay okay, I'll sit still.", "neutral"],
                        ],
                    },
                ],
            },
        ]
    }


def load_room_config(path: Path | str | None = None) -> dict[str, Any]:
    """room_config.json을 로드. 파일이 없거나 구버전 스키마면 기본 설정 반환."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return _default_room_config()

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    if "rooms" not in config:  # v1({"room": ...}) → 기본값으로 대체
        return _default_room_config()
    return config


def save_room_config(config: dict[str, Any], path: Path | str | None = None) -> None:
    """room_config.json으로 저장."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _iter_agents(config: dict[str, Any]):
    for room in config.get("rooms", []):
        yield from room.get("agents", [])


def ensure_agent_secrets(config: dict[str, Any]) -> bool:
    """secret이 없는 에이전트에 새 키를 채운다. 변경이 있었으면 True."""
    changed = False
    for a in _iter_agents(config):
        if not a.get("secret"):
            a["secret"] = _gen_secret()
            changed = True
    return changed


def get_agent_secrets(path: Path | str | None = None) -> dict[str, str]:
    """agent_id -> secret 맵 (모든 방의 에이전트 합집합).

    AGWORLD_KEY_SALT가 설정돼 있으면 키를 파생(파일에 안 씀).
    없으면(로컬 개발) 파일에 생성해 저장한다.
    """
    config = load_room_config(path)
    salt = os.environ.get(KEY_SALT_ENV)
    if salt:
        return {a["id"]: _derived_secret(a["id"], salt) for a in _iter_agents(config)}
    if ensure_agent_secrets(config):
        save_room_config(config, path)
    return {a["id"]: a["secret"] for a in _iter_agents(config)}


def strip_secrets(config: dict[str, Any]) -> dict[str, Any]:
    """클라이언트 응답용 — secret을 제거한 사본을 반환한다."""
    public = json.loads(json.dumps(config))
    for a in _iter_agents(public):
        a.pop("secret", None)
    return public


def find_room(config: dict[str, Any], room_id: str) -> dict[str, Any] | None:
    """config에서 room_id에 해당하는 방 엔트리를 찾는다."""
    for room in config.get("rooms", []):
        if room.get("id") == room_id:
            return room
    return None


def validate_room_config(config: dict[str, Any]) -> tuple[bool, str | None]:
    """Config 유효성 검사 (모든 방)."""
    rooms = config.get("rooms")
    if not rooms:
        return False, "Missing 'rooms'."

    for room in rooms:
        agents = room.get("agents", [])
        rid = room.get("id", "?")

        if not agents:
            return False, f"Room '{rid}' needs at least one agent."

        mine_count = sum(1 for a in agents if a.get("is_mine"))
        if mine_count != 1:
            return False, f"Room '{rid}' must have exactly one owner (is_mine). Found {mine_count}."

        max_agents = room.get("max_agents", 5)
        if len(agents) > max_agents:
            return False, f"Room '{rid}' exceeds the agent limit ({max_agents})."

    return True, None
