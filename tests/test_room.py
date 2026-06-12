import unittest

from agworld.room import (
    CATALOG,
    DEFAULT_ROOM_ITEMS,
    INDOOR_CATALOG,
    MAX_ITEMS,
    ROOM_SIZE,
    TOWN_ITEMS,
    TOWN_SIZE,
    room_dict_from_items,
    sanitize_items,
    town_dict,
)


class TestTown(unittest.TestCase):
    def test_town_outdoor_and_bigger(self):
        d = town_dict()
        self.assertEqual(d["room_size"], TOWN_SIZE)
        self.assertEqual(d["room_size"], 28)   # 2배 확장(기존 14)
        self.assertEqual(d["scene"], "outdoor")
        self.assertTrue(len(d["items"]) >= 5)

    def test_town_has_landmark_and_townhall(self):
        items = [it["item"] for it in town_dict()["items"]]
        self.assertIn("townhall", items)
        self.assertIn("fountain", items)   # 랜드마크
        self.assertIn("tree", items)

    def test_town_has_two_houses_linking_to_rooms(self):
        houses = [it for it in town_dict()["items"] if it["item"] == "house"]
        self.assertEqual(len(houses), 2)
        self.assertEqual({h["place"] for h in houses}, {"jungs", "jayy"})
        for h in houses:
            self.assertTrue(h.get("label"))

    def test_town_returns_copies(self):
        town_dict()["items"][0]["x"] = 999
        self.assertNotEqual(TOWN_ITEMS[0]["x"], 999)

    def test_town_items_within_bounds(self):
        half = TOWN_SIZE / 2
        for it in TOWN_ITEMS:
            self.assertLessEqual(abs(it["x"]), half, it["item"])
            self.assertLessEqual(abs(it["z"]), half, it["item"])


class TestRoomDict(unittest.TestCase):
    def test_default_rooms_indoor(self):
        for pid, items in DEFAULT_ROOM_ITEMS.items():
            d = room_dict_from_items(pid, items)
            self.assertEqual(d["place"], pid)
            self.assertEqual(d["room_size"], ROOM_SIZE)
            self.assertEqual(d["scene"], "indoor")
            self.assertEqual(len(d["items"]), len(items))

    def test_unknown_items_filtered(self):
        d = room_dict_from_items("jungs", [{"item": "rug", "x": 0, "z": 0}, {"item": "ufo", "x": 1, "z": 1}])
        names = [it["item"] for it in d["items"]]
        self.assertIn("rug", names)
        self.assertNotIn("ufo", names)

    def test_defaults_in_catalog_and_bounds(self):
        half = ROOM_SIZE / 2
        for items in DEFAULT_ROOM_ITEMS.values():
            for it in items:
                self.assertIn(it["item"], CATALOG)
                self.assertIn(it["item"], INDOOR_CATALOG)   # 방 기본 가구는 편집기에서도 추가 가능해야
                self.assertLessEqual(abs(it["x"]), half)
                self.assertLessEqual(abs(it["z"]), half)


class TestSanitizeItems(unittest.TestCase):
    def test_valid_items_pass(self):
        ok, msg, cleaned = sanitize_items([{"item": "sofa", "x": 1, "z": -2, "ry": 90, "scale": 1.5, "color": "#abc"}])
        self.assertTrue(ok, msg)
        self.assertEqual(cleaned[0]["item"], "sofa")
        self.assertEqual(cleaned[0]["ry"], 90)

    def test_rejects_non_list(self):
        ok, msg, _ = sanitize_items({"item": "sofa"})
        self.assertFalse(ok)

    def test_rejects_unknown_furniture(self):
        ok, msg, _ = sanitize_items([{"item": "house", "x": 0, "z": 0}])   # 집은 실내 카탈로그에 없음
        self.assertFalse(ok)
        self.assertIn("house", msg)

    def test_rejects_too_many(self):
        ok, msg, _ = sanitize_items([{"item": "rug", "x": 0, "z": 0}] * (MAX_ITEMS + 1))
        self.assertFalse(ok)

    def test_clamps_position_and_scale(self):
        ok, _, cleaned = sanitize_items([{"item": "plant", "x": 999, "z": -999, "scale": 99}])
        self.assertTrue(ok)
        self.assertEqual(cleaned[0]["x"], ROOM_SIZE / 2)
        self.assertEqual(cleaned[0]["z"], -ROOM_SIZE / 2)
        self.assertEqual(cleaned[0]["scale"], 3.0)

    def test_rejects_non_numeric(self):
        ok, _, _ = sanitize_items([{"item": "rug", "x": "abc", "z": 0}])
        self.assertFalse(ok)

    def test_strips_unknown_fields(self):
        ok, _, cleaned = sanitize_items([{"item": "rug", "x": 0, "z": 0, "place": "jungs", "evil": True}])
        self.assertTrue(ok)
        self.assertNotIn("place", cleaned[0])   # 내비게이션 필드 주입 방지
        self.assertNotIn("evil", cleaned[0])


if __name__ == "__main__":
    unittest.main()
