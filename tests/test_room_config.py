"""Room Config 관련 테스트."""

import unittest
import tempfile
from pathlib import Path

from agworld.room_config import (
    ensure_agent_secrets,
    get_agent_secrets,
    load_room_config,
    save_room_config,
    strip_secrets,
    validate_room_config,
    _default_room_config,
)


class TestRoomConfig(unittest.TestCase):
    def test_default_config_valid(self):
        config = _default_room_config()
        ok, msg = validate_room_config(config)
        self.assertTrue(ok, msg)

    def test_save_and_load_roundtrip(self):
        config = _default_room_config()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_config.json"
            save_room_config(config, path)
            loaded = load_room_config(path)
            self.assertEqual(loaded["room"]["title"], config["room"]["title"])
            self.assertEqual(len(loaded["room"]["agents"]), 3)

    def test_validate_requires_exactly_one_mine(self):
        config = _default_room_config()
        config["room"]["agents"][2]["is_mine"] = False  # sona를 false로
        ok, msg = validate_room_config(config)
        self.assertFalse(ok)
        self.assertIn("is_mine", msg)

    def test_validate_max_agents(self):
        config = _default_room_config()
        config["room"]["max_agents"] = 2
        ok, msg = validate_room_config(config)
        self.assertFalse(ok)
        self.assertIn("초과", msg)


class TestAgentSecrets(unittest.TestCase):
    def test_ensure_fills_missing_only(self):
        config = _default_room_config()
        config["room"]["agents"][0]["secret"] = "fixed-key"
        changed = ensure_agent_secrets(config)
        self.assertTrue(changed)
        self.assertEqual(config["room"]["agents"][0]["secret"], "fixed-key")  # 기존 키 보존
        self.assertTrue(all(a.get("secret") for a in config["room"]["agents"]))
        self.assertFalse(ensure_agent_secrets(config))  # 모두 채워지면 변경 없음

    def test_get_agent_secrets_generates_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_room_config(_default_room_config(), path)
            secrets1 = get_agent_secrets(path)
            self.assertEqual(set(secrets1), {"ruri", "dan", "sona"})
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
            self.assertEqual(set(s1), {"ruri", "dan", "sona"})
            # 파일에는 secret이 안 써졌어야 함
            loaded = load_room_config(path)
            self.assertFalse(any("secret" in a for a in loaded["room"]["agents"]))
            with mock.patch.dict(os.environ, {"AGWORLD_KEY_SALT": "other-salt"}):
                s3 = get_agent_secrets(path)
            self.assertNotEqual(s1, s3)  # 다른 salt → 다른 키

    def test_strip_secrets_removes_keys_without_mutating(self):
        config = _default_room_config()
        ensure_agent_secrets(config)
        public = strip_secrets(config)
        self.assertFalse(any("secret" in a for a in public["room"]["agents"]))
        self.assertTrue(all("secret" in a for a in config["room"]["agents"]))  # 원본 유지


if __name__ == "__main__":
    unittest.main()
