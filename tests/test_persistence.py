import json
import os
import tempfile
import unittest

from agworld.models import Agent, Emotion, Turn
from agworld.persistence import load_snapshot, save_snapshot


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "snap.json")

    def _agents(self):
        a = Agent("sona", "소나", "다정", is_mine=True)
        a.adjust_sentiment("dan", 0.4)
        a.remember(Turn(3, "dan", "안녕", Emotion.JOY, "sona"))
        return [a]

    def test_save_load_roundtrip(self):
        save_snapshot(self._agents(), self.path, t=7)
        loaded = load_snapshot(self.path)
        self.assertIsNotNone(loaded)
        agents, t = loaded
        self.assertEqual(t, 7)
        self.assertEqual(agents[0].name, "소나")
        self.assertTrue(agents[0].is_mine)
        self.assertAlmostEqual(agents[0].sentiment_toward("dan"), 0.4)
        self.assertEqual(agents[0].memory[0].text, "안녕")

    def test_missing_file_returns_none(self):
        self.assertIsNone(load_snapshot(os.path.join(self.dir, "nope.json")))

    def test_corrupt_file_returns_none(self):
        with open(self.path, "w") as f:
            f.write("{ this is not valid json ")
        self.assertIsNone(load_snapshot(self.path))

    def test_atomic_save_creates_dir(self):
        nested = os.path.join(self.dir, "a", "b", "snap.json")
        save_snapshot(self._agents(), nested, t=1)
        self.assertTrue(os.path.exists(nested))
        # 임시파일이 남지 않아야 함
        leftovers = [f for f in os.listdir(os.path.dirname(nested)) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_written_json_is_utf8_readable(self):
        save_snapshot(self._agents(), self.path, t=1)
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["agents"][0]["name"], "소나")


if __name__ == "__main__":
    unittest.main()
