import unittest

from agworld.whisper import RateLimited, WhisperQueue


class TestWhisperQueue(unittest.TestCase):
    def test_enqueue_then_pop(self):
        q = WhisperQueue()
        q.enqueue("sona", "사과해보라고 해", current_tick=1)
        self.assertEqual(q.pop_for("sona"), "사과해보라고 해")
        self.assertIsNone(q.pop_for("sona"))

    def test_pop_for_non_target_is_none(self):
        q = WhisperQueue()
        q.enqueue("sona", "hi", current_tick=1)
        self.assertIsNone(q.pop_for("dan"))  # 다른 에이전트 차례엔 안 나옴
        self.assertEqual(q.pop_for("sona"), "hi")  # 대상 차례엔 대기 중이던 게 나옴

    def test_multiple_whispers_fifo(self):
        q = WhisperQueue()
        q.enqueue("sona", "첫째", 1)
        q.enqueue("sona", "둘째", 1)
        self.assertEqual(q.pop_for("sona"), "첫째")
        self.assertEqual(q.pop_for("sona"), "둘째")

    def test_rate_limit_blocks(self):
        q = WhisperQueue(rate_limit=2, rate_window_ticks=5)
        q.enqueue("sona", "1", 1)
        q.enqueue("sona", "2", 1)
        with self.assertRaises(RateLimited):
            q.enqueue("sona", "3", 1)

    def test_rate_limit_window_resets(self):
        q = WhisperQueue(rate_limit=2, rate_window_ticks=5)
        q.enqueue("sona", "1", 1)
        q.enqueue("sona", "2", 1)
        # 윈도우 밖(틱 7)으로 가면 다시 허용
        q.enqueue("sona", "3", current_tick=7)
        self.assertTrue(q.has_pending("sona"))

    def test_empty_whisper_ignored_no_rate_cost(self):
        q = WhisperQueue(rate_limit=1)
        q.enqueue("sona", "   ", 1)  # 공백뿐 → 무시, 레이트 카운트 안 함
        self.assertFalse(q.has_pending("sona"))
        q.enqueue("sona", "진짜 귓속말", 1)  # 여전히 가능
        self.assertTrue(q.has_pending("sona"))

    def test_has_pending_global(self):
        q = WhisperQueue()
        self.assertFalse(q.has_pending())
        q.enqueue("dan", "x", 1)
        self.assertTrue(q.has_pending())


if __name__ == "__main__":
    unittest.main()
