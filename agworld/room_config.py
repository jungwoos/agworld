"""Room Config 관리 — JSON 기반 Room 정의 로드/저장/검증.

Config 스키마:
{
  "room": {
    "id": "room",
    "title": "우리 방",
    "max_agents": 5,
    "agents": [
      {
        "id": "ruri",
        "name": "루리",
        "persona_prompt": "...",
        "is_mine": false,
        "canned_lines": [["text", "emotion"], ...]
      }
    ]
  }
}
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


def ensure_agent_secrets(config: dict[str, Any]) -> bool:
    """secret이 없는 에이전트에 새 키를 채운다. 변경이 있었으면 True."""
    changed = False
    for a in config.get("room", {}).get("agents", []):
        if not a.get("secret"):
            a["secret"] = _gen_secret()
            changed = True
    return changed


def get_agent_secrets(path: Path | str | None = None) -> dict[str, str]:
    """agent_id -> secret 맵.

    AGWORLD_KEY_SALT가 설정돼 있으면 키를 파생(파일에 안 씀).
    없으면(로컬 개발) 파일에 생성해 저장한다.
    """
    config = load_room_config(path)
    salt = os.environ.get(KEY_SALT_ENV)
    if salt:
        return {a["id"]: _derived_secret(a["id"], salt) for a in config["room"]["agents"]}
    if ensure_agent_secrets(config):
        save_room_config(config, path)
    return {a["id"]: a["secret"] for a in config["room"]["agents"]}


def strip_secrets(config: dict[str, Any]) -> dict[str, Any]:
    """클라이언트 응답용 — secret을 제거한 사본을 반환한다."""
    public = json.loads(json.dumps(config))
    for a in public.get("room", {}).get("agents", []):
        a.pop("secret", None)
    return public


def _default_room_config() -> dict[str, Any]:
    """기존 places.py의 ROOM_SPECS를 기반으로 한 기본 설정."""
    return {
        "room": {
            "id": "room",
            "title": "우리 방",
            "max_agents": 5,
            "agents": [
                {
                    "id": "ruri",
                    "name": "루리",
                    "persona_prompt": "감정 표현이 솔직하고 서운함을 잘 탄다.",
                    "is_mine": False,
                    "canned_lines": [
                        ["오늘 다들 좀 조용하네.", "neutral"],
                        ["단, 아까 그 말 진심이었어? 나 좀 서운했어.", "anger"],
                        ["...사과는 안 할 거야?", "sad"],
                    ],
                },
                {
                    "id": "dan",
                    "name": "단",
                    "persona_prompt": "무심한 척하지만 마음 약하고 사과를 잘 한다.",
                    "is_mine": False,
                    "canned_lines": [
                        ["아 오늘 좀 피곤하다.", "sad"],
                        ["그건 그냥 농담이었는데.", "surprise"],
                        ["미안, 진심이 아니었어. 내가 말을 잘못했네.", "affection"],
                    ],
                },
                {
                    "id": "sona",
                    "name": "소나",
                    "persona_prompt": "둘 사이를 중재하는 다정한 관찰자.",
                    "is_mine": True,
                    "canned_lines": [
                        ["무슨 일 있었어?", "thinking"],
                        ["둘 다 진정하고... 얘기 좀 해봐.", "thinking"],
                        ["거봐, 잘 풀렸네.", "joy"],
                    ],
                },
            ],
        }
    }


def load_room_config(path: Path | str | None = None) -> dict[str, Any]:
    """room_config.json을 로드. 파일이 없으면 기본 설정 반환."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return _default_room_config()

    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def save_room_config(config: dict[str, Any], path: Path | str | None = None) -> None:
    """room_config.json으로 저장."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def validate_room_config(config: dict[str, Any]) -> tuple[bool, str | None]:
    """Config 유효성 검사."""
    if "room" not in config:
        return False, "room 키가 없습니다."

    room = config["room"]
    agents = room.get("agents", [])

    if not agents:
        return False, "최소 1명의 에이전트가 필요합니다."

    mine_count = sum(1 for a in agents if a.get("is_mine"))
    if mine_count != 1:
        return False, f"is_mine=True인 에이전트는 정확히 1명이어야 합니다. (현재: {mine_count}명)"

    max_agents = room.get("max_agents", 5)
    if len(agents) > max_agents:
        return False, f"에이전트 수가 최대치({max_agents}명)를 초과했습니다."

    return True, None
