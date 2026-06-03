import unittest

from agworld.models import Emotion
from agworld.providers import (
    FAULT_EMPTY,
    FAULT_MALFORMED,
    FAULT_TIMEOUT,
    FakeProvider,
    ProviderTimeout,
    count_tokens,
)


class TestCountTokens(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(count_tokens(""), 0)

    def test_nonempty_at_least_one(self):
        self.assertEqual(count_tokens("a"), 1)
        self.assertEqual(count_tokens("a" * 8), 2)


class TestFakeProvider(unittest.TestCase):
    def test_deterministic_cycle(self):
        p = FakeProvider({"x": [("일", Emotion.JOY), ("이", Emotion.SAD)]})
        r1 = p.respond("prompt", "x")
        r2 = p.respond("prompt", "x")
        r3 = p.respond("prompt", "x")
        self.assertEqual([r1.text, r2.text, r3.text], ["일", "이", "일"])
        self.assertIs(r1.emotion, Emotion.JOY)

    def test_no_script_falls_back(self):
        p = FakeProvider()
        r = p.respond("prompt", "unknown")
        self.assertEqual(r.text, "...")
        self.assertIs(r.emotion, Emotion.NEUTRAL)

    def test_counts_prompt_tokens(self):
        p = FakeProvider({"x": [("hi", Emotion.JOY)]})
        r = p.respond("a" * 40, "x")
        self.assertEqual(r.prompt_tokens, 10)

    def test_fault_timeout_raises(self):
        p = FakeProvider({"x": [("hi", Emotion.JOY)]})
        p.fault_mode = FAULT_TIMEOUT
        with self.assertRaises(ProviderTimeout):
            p.respond("prompt", "x")

    def test_fault_timeout_then_recovers(self):
        p = FakeProvider({"x": [("hi", Emotion.JOY)]})
        p.fault_mode = FAULT_TIMEOUT
        p.fault_calls_remaining = 1  # 첫 1콜만 실패
        with self.assertRaises(ProviderTimeout):
            p.respond("prompt", "x")
        r = p.respond("prompt", "x")  # 두 번째는 성공
        self.assertEqual(r.text, "hi")

    def test_fault_empty(self):
        p = FakeProvider({"x": [("hi", Emotion.JOY)]})
        p.fault_mode = FAULT_EMPTY
        r = p.respond("prompt", "x")
        self.assertEqual(r.text, "")

    def test_fault_malformed_coerces_neutral(self):
        p = FakeProvider({"x": [("hi", Emotion.JOY)]})
        p.fault_mode = FAULT_MALFORMED
        r = p.respond("prompt", "x")
        self.assertIs(r.emotion, Emotion.NEUTRAL)


if __name__ == "__main__":
    unittest.main()
