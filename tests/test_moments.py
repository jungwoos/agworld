import unittest

from agworld.models import TIER_AMBIENT, TIER_DECISIVE, Agent
from agworld.moments import MomentClassifier


class TestMomentClassifier(unittest.TestCase):
    def setUp(self):
        self.c = MomentClassifier()
        self.speaker = Agent("ruri", "루리", "솔직함")

    def test_whisper_forces_decisive(self):
        tier = self.c.classify(self.speaker, "dan", "평범한 말", has_whisper=True)
        self.assertEqual(tier, TIER_DECISIVE)

    def test_relationship_delta_decisive(self):
        self.speaker.adjust_sentiment("dan", -0.6)  # 임계 0.5 초과
        tier = self.c.classify(self.speaker, "dan", "평범한 말", has_whisper=False)
        self.assertEqual(tier, TIER_DECISIVE)

    def test_keyword_decisive(self):
        tier = self.c.classify(self.speaker, "dan", "나 좀 서운했어", has_whisper=False)
        self.assertEqual(tier, TIER_DECISIVE)

    def test_plain_tick_is_ambient(self):
        tier = self.c.classify(self.speaker, "dan", "오늘 날씨 좋다", has_whisper=False)
        self.assertEqual(tier, TIER_AMBIENT)

    def test_no_addressee_no_relationship_check(self):
        self.speaker.adjust_sentiment("dan", 0.9)
        tier = self.c.classify(self.speaker, None, "그냥 혼잣말", has_whisper=False)
        self.assertEqual(tier, TIER_AMBIENT)


if __name__ == "__main__":
    unittest.main()
