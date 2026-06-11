"""Room Config 관련 테스트."""

import unittest
import tempfile
from pathlib import Path

from agworld.room_config import (
    ensure_agent_secrets,
    find_room,
    get_agent_secrets,
    load_room_config,
    save_room_config,
    strip_secrets,
    validate_room_config,
    _default_room_config,
)

ALL_AGENT_IDS = {"jungs", "dan", "jayy", "mina"}


def _agents(config):
    return [a for room in config["rooms"] for a in room["agents"]]


class TestRoomConfig(unittest.TestCase):
    def test_default_config_valid(self):
        config = _default_room_config()
        ok, msg = validate_room_config(config)
        self.assertTrue(ok, msg)

    def test_default_has_two_rooms(self):
        config = _default_room_config()
        self.assertEqual([r["id"] for r in config["rooms"]], ["jungs", "jayy"])

    def test_save_and_load_roundtrip(self):
        config = _default_room_config()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_config.json"
            save_room_config(config, path)
            loaded = load_room_config(path)
            self.assertEqual(loaded["rooms"][0]["title"], config["rooms"][0]["title"])
            self.assertEqual(len(_agents(loaded)), 4)

    def test_v1_schema_replaced_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.json"
            save_room_config({"room": {"id": "room", "agents": []}}, path)
            loaded = load_room_config(path)
            self.assertIn("rooms", loaded)

    def test_find_room(self):
        config = _default_room_config()
        self.assertEqual(find_room(config, "jayy")["title"], "Jayy's Room")
        self.assertIsNone(find_room(config, "nope"))

    def test_validate_requires_exactly_one_owner_per_room(self):
        config = _default_room_config()
        config["rooms"][0]["agents"][0]["is_mine"] = False  # jungs 방에 주인 없음
        ok, msg = validate_room_config(config)
        self.assertFalse(ok)
        self.assertIn("owner", msg)

    def test_validate_max_agents(self):
        config = _default_room_config()
        config["rooms"][1]["max_agents"] = 1
        ok, msg = validate_room_config(config)
        self.assertFalse(ok)
        self.assertIn("exceeds", msg)


class TestAgentSecrets(unittest.TestCase):
    def test_ensure_fills_missing_only(self):
        config = _default_room_config()
        _agents(config)[0]["secret"] = "fixed-key"
        changed = ensure_agent_secrets(config)
        self.assertTrue(changed)
        self.assertEqual(_agents(config)[0]["secret"], "fixed-key")  # 기존 키 보존
        self.assertTrue(all(a.get("secret") for a in _agents(config)))
        self.assertFalse(ensure_agent_secrets(config))  # 모두 채워지면 변경 없음

    def test_get_agent_secrets_generates_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_room_config(_default_room_config(), path)
            secrets1 = get_agent_secrets(path)
            self.assertEqual(set(secrets1), ALL_AGENT_IDS)
            secrets2 = get_agent_secrets(path)  # 재호출 시 같은 키(저장됐으므로)
            self.assertEqual(secrets1, secrets2)

    def test_salt_derives_stable_secrets_without_disk_write(self):
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_room_config(_default_room_config(), path)
            with mock.patch.dict(os.environ, {"AGWORLD_KEY_SALT": "test-salt"}):
                s1 = get_agent_secrets(path)
                s2 = get_agent_secrets(path)
            self.assertEqual(s1, s2)  # 같은 salt → 같은 키
            self.assertEqual(set(s1), ALL_AGENT_IDS)
            # 파일에는 secret이 안 써졌어야 함
            loaded = load_room_config(path)
            self.assertFalse(any("secret" in a for a in _agents(loaded)))
            with mock.patch.dict(os.environ, {"AGWORLD_KEY_SALT": "other-salt"}):
                s3 = get_agent_secrets(path)
            self.assertNotEqual(s1, s3)  # 다른 salt → 다른 키

    def test_strip_secrets_removes_keys_without_mutating(self):
        config = _default_room_config()
        ensure_agent_secrets(config)
        public = strip_secrets(config)
        self.assertFalse(any("secret" in a for a in _agents(public)))
        self.assertTrue(all("secret" in a for a in _agents(config)))  # 원본 유지


if __name__ == "__main__":
    unittest.main()
