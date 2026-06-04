import unittest

from agworld.live import find_my_agent
from agworld.places import build_places, places_meta


class TestPlaces(unittest.TestCase):
    def setUp(self):
        self.places = build_places()

    def test_has_room_and_town(self):
        self.assertIn("room", self.places)
        self.assertIn("town", self.places)

    def test_town_has_ten_agents(self):
        self.assertEqual(len(self.places["town"]["world"].agents), 10)

    def test_each_place_has_exactly_one_mine(self):
        for pid, p in self.places.items():
            mine = [a for a in p["world"].agents if a.is_mine]
            self.assertEqual(len(mine), 1, f"{pid} should have one mine agent")
            self.assertIsNotNone(find_my_agent(p["world"]))

    def test_places_are_independent_worlds(self):
        # 같은 이름(소나)이라도 장소별 별개 인스턴스
        self.assertIsNot(self.places["room"]["world"], self.places["town"]["world"])
        room_sona = find_my_agent(self.places["room"]["world"])
        town_sona = find_my_agent(self.places["town"]["world"])
        self.assertIsNot(room_sona, town_sona)

    def test_town_world_steps(self):
        w = self.places["town"]["world"]
        for _ in range(12):
            self.assertIsNotNone(w.step())
        self.assertEqual(w.t, 12)
        # 10인 라운드로빈이 모두 한 번씩은 말함
        speakers = {turn.speaker_id for turn in w.feed}
        self.assertEqual(len(speakers), 10)

    def test_places_meta(self):
        meta = places_meta(self.places)
        ids = [m["id"] for m in meta]
        self.assertEqual(ids, ["room", "town"])
        town = next(m for m in meta if m["id"] == "town")
        self.assertEqual(town["agents"], 10)
        self.assertEqual(town["title"], "우리 동네")


if __name__ == "__main__":
    unittest.main()
