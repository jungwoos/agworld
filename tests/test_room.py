import unittest

from agworld.room import CATALOG, JAYY_LAYOUT, JUNGS_LAYOUT, LAYOUTS, TOWN_LAYOUT, room_dict


class TestRoom(unittest.TestCase):
    def test_rooms_indoor(self):
        for pid in ("jungs", "jayy"):
            d = room_dict(pid)
            self.assertEqual(d["place"], pid)
            self.assertEqual(d["room_size"], 8)
            self.assertEqual(d["scene"], "indoor")

    def test_town_outdoor_and_bigger(self):
        d = room_dict("town")
        self.assertEqual(d["room_size"], 28)   # 2배 확장(기존 14)
        self.assertEqual(d["scene"], "outdoor")
        self.assertTrue(len(d["items"]) >= 5)

    def test_town_has_landmark_and_townhall(self):
        items = [it["item"] for it in room_dict("town")["items"]]
        self.assertIn("townhall", items)
        self.assertIn("fountain", items)   # 랜드마크
        self.assertIn("tree", items)

    def test_town_has_two_houses_linking_to_rooms(self):
        houses = [it for it in room_dict("town")["items"] if it["item"] == "house"]
        self.assertEqual(len(houses), 2)
        self.assertEqual({h["place"] for h in houses}, {"jungs", "jayy"})
        for h in houses:
            self.assertTrue(h.get("label"))

    def test_unknown_place_falls_back(self):
        self.assertEqual(room_dict("atlantis")["room_size"], 8)

    def test_all_layout_items_in_catalog(self):
        for layout in (JUNGS_LAYOUT, JAYY_LAYOUT, TOWN_LAYOUT):
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
        room_dict("jungs")["items"][0]["x"] = 999
        self.assertNotEqual(JUNGS_LAYOUT[0]["x"], 999)


if __name__ == "__main__":
    unittest.main()
