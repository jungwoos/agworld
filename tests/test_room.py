import unittest

from agworld.room import CATALOG, DEFAULT_ROOM, room_dict


class TestRoom(unittest.TestCase):
    def test_default_room_serializes(self):
        d = room_dict()
        self.assertEqual(d["room_size"], 8)
        self.assertTrue(len(d["items"]) >= 5)

    def test_all_default_items_in_catalog(self):
        for it in DEFAULT_ROOM:
            self.assertIn(it["item"], CATALOG)

    def test_unknown_items_filtered(self):
        layout = [{"item": "rug", "x": 0, "z": 0}, {"item": "spaceship", "x": 1, "z": 1}]
        items = room_dict(layout)["items"]
        names = [it["item"] for it in items]
        self.assertIn("rug", names)
        self.assertNotIn("spaceship", names)

    def test_items_within_room_bounds(self):
        # 가구가 방(8x8, ±4) 안에 있어야 함
        for it in DEFAULT_ROOM:
            self.assertLessEqual(abs(it["x"]), 4.0)
            self.assertLessEqual(abs(it["z"]), 4.0)

    def test_returns_copies_not_refs(self):
        d = room_dict()
        d["items"][0]["x"] = 999
        self.assertNotEqual(DEFAULT_ROOM[0]["x"], 999)  # 원본 불변


if __name__ == "__main__":
    unittest.main()
