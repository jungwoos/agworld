import unittest

from agworld.scheduler import SpeakerSelector, TickScheduler


class TestTickScheduler(unittest.TestCase):
    def test_advance_when_watching(self):
        s = TickScheduler(watching=True)
        self.assertEqual(s.advance(), 1)
        self.assertEqual(s.advance(), 2)
        self.assertEqual(s.t, 2)

    def test_sleep_on_disconnect_no_advance(self):
        # 핵심: 안 보면 틱이 0으로 멈춘다 (비용 캡의 정의적 방어선)
        s = TickScheduler(watching=True)
        s.advance()
        s.set_watching(False)
        self.assertIsNone(s.advance())
        self.assertIsNone(s.advance())
        self.assertEqual(s.t, 1)  # 자는 동안 t 안 늘어남

    def test_wake_resumes_from_t(self):
        s = TickScheduler(watching=False, start_t=5)
        self.assertIsNone(s.advance())
        s.set_watching(True)
        self.assertEqual(s.advance(), 6)  # 직전 t에서 이어감


class TestSpeakerSelector(unittest.TestCase):
    def test_round_robin(self):
        sel = SpeakerSelector()
        ids = ["a", "b", "c"]
        seq = [sel.next_speaker(ids) for _ in range(4)]
        self.assertEqual(seq, ["a", "b", "c", "a"])

    def test_whisper_priority(self):
        sel = SpeakerSelector()
        ids = ["a", "b", "c"]
        self.assertEqual(sel.next_speaker(ids, priority_id="c"), "c")
        # 우선 발화 후에도 라운드로빈 커서는 공정하게 a부터
        self.assertEqual(sel.next_speaker(ids), "a")

    def test_priority_not_in_list_ignored(self):
        sel = SpeakerSelector()
        self.assertEqual(sel.next_speaker(["a", "b"], priority_id="zzz"), "a")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            SpeakerSelector().next_speaker([])


if __name__ == "__main__":
    unittest.main()
