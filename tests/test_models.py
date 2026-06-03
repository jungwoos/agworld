import unittest

from agworld.models import Agent, Emotion, Turn


class TestEmotion(unittest.TestCase):
    def test_all_seven_have_emoji(self):
        self.assertEqual(len(list(Emotion)), 7)
        for e in Emotion:
            self.assertTrue(e.emoji)

    def test_coerce_valid_string(self):
        self.assertIs(Emotion.coerce("anger"), Emotion.ANGER)
        self.assertIs(Emotion.coerce(" JOY "), Emotion.JOY)

    def test_coerce_unknown_falls_back_neutral(self):
        self.assertIs(Emotion.coerce("not-an-emotion"), Emotion.NEUTRAL)
        self.assertIs(Emotion.coerce(None), Emotion.NEUTRAL)
        self.assertIs(Emotion.coerce(42), Emotion.NEUTRAL)

    def test_coerce_passthrough_enum(self):
        self.assertIs(Emotion.coerce(Emotion.SAD), Emotion.SAD)


class TestAgent(unittest.TestCase):
    def test_sentiment_clamped(self):
        a = Agent("x", "X", "p")
        a.adjust_sentiment("y", 0.8)
        a.adjust_sentiment("y", 0.8)
        self.assertEqual(a.sentiment_toward("y"), 1.0)  # 클램프 상한
        a.adjust_sentiment("y", -5.0)
        self.assertEqual(a.sentiment_toward("y"), -1.0)  # 클램프 하한

    def test_unknown_sentiment_is_zero(self):
        self.assertEqual(Agent("x", "X", "p").sentiment_toward("z"), 0.0)

    def test_roundtrip_dict(self):
        a = Agent("sona", "소나", "다정함", is_mine=True)
        a.adjust_sentiment("dan", 0.3)
        a.remember(Turn(1, "dan", "안녕", Emotion.JOY, "sona"))
        back = Agent.from_dict(a.to_dict())
        self.assertEqual(back.id, "sona")
        self.assertTrue(back.is_mine)
        self.assertAlmostEqual(back.sentiment_toward("dan"), 0.3)
        self.assertEqual(back.memory[0].text, "안녕")
        self.assertIs(back.memory[0].emotion, Emotion.JOY)


class TestTurn(unittest.TestCase):
    def test_roundtrip_with_bad_emotion(self):
        d = {"t": 2, "speaker_id": "x", "text": "hi", "emotion": "garbage"}
        turn = Turn.from_dict(d)
        self.assertIs(turn.emotion, Emotion.NEUTRAL)


if __name__ == "__main__":
    unittest.main()
