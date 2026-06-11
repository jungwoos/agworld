"""Room Config 관련 테스트."""

import unittest
import tempfile
from pathlib import Path

from agworld.room_config import (
    load_room_config,
    save_room_config,
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


if __name__ == "__main__":
    unittest.main()
