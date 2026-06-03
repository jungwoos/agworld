import unittest

from agworld.cost import CostMeter
from agworld.models import TIER_AMBIENT, TIER_DECISIVE, Emotion
from agworld.providers import FakeProvider


class TestCostMeter(unittest.TestCase):
    def test_per_tier_accumulation(self):
        p = FakeProvider({"x": [("hello", Emotion.JOY)]})
        m = CostMeter(p)
        m.respond("a" * 40, "x", TIER_AMBIENT)
        m.respond("a" * 40, "x", TIER_DECISIVE)
        self.assertEqual(m.stats[TIER_AMBIENT].calls, 1)
        self.assertEqual(m.stats[TIER_DECISIVE].calls, 1)
        self.assertEqual(m.total_calls(), 2)

    def test_session_cost_aggregates(self):
        p = FakeProvider({"x": [("hello world this is text", Emotion.JOY)]})
        m = CostMeter(p)
        m.respond("a" * 4000, "x", TIER_DECISIVE)
        self.assertGreater(m.session_cost(), 0.0)

    def test_zero_price_tier_is_free(self):
        # 로컬 앰비언트 시나리오: 가격 0 → 비용 0
        p = FakeProvider({"x": [("free local chatter", Emotion.NEUTRAL)]})
        m = CostMeter(p, prices={TIER_AMBIENT: (0.0, 0.0)})
        m.respond("a" * 4000, "x", TIER_AMBIENT)
        self.assertEqual(m.tier_cost(TIER_AMBIENT), 0.0)

    def test_summary_renders(self):
        p = FakeProvider({"x": [("hi", Emotion.JOY)]})
        m = CostMeter(p)
        m.respond("prompt", "x", TIER_AMBIENT)
        self.assertIn("TOTAL", m.summary())


if __name__ == "__main__":
    unittest.main()
