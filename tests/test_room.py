import unittest

from agworld.room import CATALOG, LAYOUTS, ROOM_LAYOUT, TOWN_LAYOUT, room_dict


class TestRoom(unittest.TestCase):
    def test_room_indoor(self):
        d = room_dict("room")
        self.assertEqual(d["place"], "room")
        self.assertEqual(d["room_size"], 8)
        self.assertEqual(d["scene"], "indoor")

    def test_town_outdoor_and_bigger(self):
        d = room_dict("town")
        self.assertEqual(d["room_size"], 14)
        self.assertEqual(d["scene"], "outdoor")
        self.assertTrue(len(d["items"]) >= 5)

    def test_town_has_landmark_and_townhall(self):
        items = [it["item"] for it in room_dict("town")["items"]]
        self.assertIn("townhall", items)
        self.assertIn("fountain", items)   # 랜드마크
        self.assertIn("tree", items)

    def test_unknown_place_falls_back(self):
        self.assertEqual(room_dict("atlantis")["room_size"], 8)

    def test_all_layout_items_in_catalog(self):
        for layout in (ROOM_LAYOUT, TOWN_LAYOUT):
            for it in layout:
                self.assertIn(it["item"], CATALOG)

    def test_unknown_items_filtered(self):
        LAYOUTS["_t"] = (8, "indoor", [{"item": "rug", "x": 0, "z": 0}, {"item": "ufo", "x": 1, "z": 1}])
        try:
            names = [it["item"] for it in room_dict("_t")["items"]]
            self.assertIn("rug", names)
            self.assertNotIn("ufo", names)
        finally:
            del LAYOUTS["_t"]

    def test_items_within_bounds(self):
        for place, (size, _scene, layout) in LAYOUTS.items():
            half = size / 2
            for it in layout:
                self.assertLessEqual(abs(it["x"]), half, f"{place}:{it['item']} x")
                self.assertLessEqual(abs(it["z"]), half, f"{place}:{it['item']} z")

    def test_returns_copies(self):
        room_dict("room")["items"][0]["x"] = 999
        self.assertNotEqual(ROOM_LAYOUT[0]["x"], 999)


if __name__ == "__main__":
    unittest.main()
