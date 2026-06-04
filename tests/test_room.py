import unittest

from agworld.room import CATALOG, LAYOUTS, ROOM_LAYOUT, TOWN_LAYOUT, room_dict


class TestRoom(unittest.TestCase):
    def test_room_serializes(self):
        d = room_dict("room")
        self.assertEqual(d["place"], "room")
        self.assertEqual(d["room_size"], 8)
        self.assertTrue(len(d["items"]) >= 5)

    def test_town_is_bigger(self):
        d = room_dict("town")
        self.assertEqual(d["room_size"], 12)
        self.assertTrue(len(d["items"]) >= len(room_dict("room")["items"]))

    def test_unknown_place_falls_back_to_room(self):
        d = room_dict("atlantis")
        self.assertEqual(d["room_size"], 8)

    def test_all_layout_items_in_catalog(self):
        for layout in (ROOM_LAYOUT, TOWN_LAYOUT):
            for it in layout:
                self.assertIn(it["item"], CATALOG)

    def test_unknown_items_filtered(self):
        LAYOUTS["_test"] = (8, [{"item": "rug", "x": 0, "z": 0}, {"item": "ufo", "x": 1, "z": 1}])
        try:
            names = [it["item"] for it in room_dict("_test")["items"]]
            self.assertIn("rug", names)
            self.assertNotIn("ufo", names)
        finally:
            del LAYOUTS["_test"]

    def test_items_within_room_bounds(self):
        for place, (size, layout) in LAYOUTS.items():
            half = size / 2
            for it in layout:
                self.assertLessEqual(abs(it["x"]), half, f"{place}:{it['item']} x out of bounds")
                self.assertLessEqual(abs(it["z"]), half, f"{place}:{it['item']} z out of bounds")

    def test_returns_copies_not_refs(self):
        room_dict("room")["items"][0]["x"] = 999
        self.assertNotEqual(ROOM_LAYOUT[0]["x"], 999)


if __name__ == "__main__":
    unittest.main()
