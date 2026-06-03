import unittest

from agworld.live import (
    QUIT,
    SKIP,
    WHISPER,
    apply_command,
    find_my_agent,
    parse_input,
)
from agworld.models import Agent, Emotion
from agworld.providers import FakeProvider
from agworld.sim import World
from agworld.whisper import WhisperQueue


def make_world(whisper_queue=None):
    agents = [
        Agent("ruri", "루리", "솔직함"),
        Agent("sona", "소나", "다정함", is_mine=True),
    ]
    scripts = {"ruri": [("안녕", Emotion.JOY)], "sona": [("응", Emotion.JOY)]}
    return World(agents, FakeProvider(scripts), whisper_queue=whisper_queue)


class TestParseInput(unittest.TestCase):
    def test_empty_is_skip(self):
        self.assertEqual(parse_input(""), (SKIP, ""))
        self.assertEqual(parse_input("   "), (SKIP, ""))

    def test_quit_variants(self):
        for q in ("q", "Q", "quit", "종료"):
            self.assertEqual(parse_input(q)[0], QUIT)

    def test_whisper_text(self):
        kind, payload = parse_input("  루리한테 사과해  ")
        self.assertEqual(kind, WHISPER)
        self.assertEqual(payload, "루리한테 사과해")


class TestFindMyAgent(unittest.TestCase):
    def test_finds_mine(self):
        w = make_world()
        self.assertEqual(find_my_agent(w).id, "sona")

    def test_none_when_no_mine(self):
        agents = [Agent("a", "A", "p"), Agent("b", "B", "p")]
        w = World(agents, FakeProvider())
        self.assertIsNone(find_my_agent(w))


class TestApplyCommand(unittest.TestCase):
    def test_quit_returns_quit(self):
        w = make_world()
        kind, msg = apply_command(w, "q")
        self.assertEqual(kind, QUIT)
        self.assertIn("잠듭니다", msg)

    def test_skip_on_empty(self):
        w = make_world()
        self.assertEqual(apply_command(w, "")[0], SKIP)

    def test_whisper_queued_to_my_agent(self):
        w = make_world()
        kind, msg = apply_command(w, "루리한테 먼저 말 걸어봐")
        self.assertEqual(kind, WHISPER)
        self.assertTrue(w.whispers.has_pending("sona"))  # 내 에이전트에게 큐잉
        self.assertIn("소나", msg)

    def test_rate_limit_message(self):
        q = WhisperQueue(rate_limit=1)
        w = make_world(whisper_queue=q)
        apply_command(w, "첫 속삭임")
        kind, msg = apply_command(w, "둘째 속삭임")  # 리밋 초과
        self.assertEqual(kind, WHISPER)
        self.assertIn("⏳", msg)

    def test_no_mine_agent_safe(self):
        agents = [Agent("a", "A", "p"), Agent("b", "B", "p")]
        w = World(agents, FakeProvider())
        kind, msg = apply_command(w, "속삭임")
        self.assertEqual(kind, SKIP)
        self.assertIn("대상이 없", msg)


if __name__ == "__main__":
    unittest.main()
