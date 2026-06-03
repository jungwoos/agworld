import unittest

from agworld.console import render, render_feed, render_stage
from agworld.models import Agent, Emotion
from agworld.providers import FakeProvider
from agworld.sim import World


def make_world():
    agents = [
        Agent("ruri", "루리", "솔직함"),
        Agent("sona", "소나", "다정함", is_mine=True),
    ]
    scripts = {"ruri": [("안녕", Emotion.JOY)], "sona": [("반가워", Emotion.AFFECTION)]}
    return World(agents, FakeProvider(scripts))


class TestRenderStage(unittest.TestCase):
    def test_shows_emoji_and_names(self):
        w = make_world()
        w.step()  # 루리 발화(JOY)
        out = render_stage(w, speaking_id="ruri")
        self.assertIn("루리", out)
        self.assertIn(Emotion.JOY.emoji, out)
        self.assertIn("말하는 중", out)

    def test_mine_marked(self):
        w = make_world()
        out = render_stage(w)
        self.assertIn("내 에이전트", out)

    def test_sleeping_shows_zzz(self):
        w = make_world()
        w.step()
        w.set_watching(False)
        out = render_stage(w)
        self.assertIn("💤", out)
        self.assertIn("자는 중", out)


class TestRenderFeed(unittest.TestCase):
    def test_empty_feed_message(self):
        w = make_world()
        self.assertIn("아직 조용하다", render_feed(w))

    def test_feed_lists_lines_with_tick_markers(self):
        w = make_world()
        w.step()
        out = render_feed(w)
        self.assertIn("틱 1", out)
        self.assertIn("안녕", out)

    def test_decisive_tick_marked(self):
        w = make_world()
        w.decisive_ticks.add(1)
        w.step()
        self.assertIn("⚡", render_feed(w))


class TestRenderCombined(unittest.TestCase):
    def test_render_has_stage_and_feed(self):
        w = make_world()
        w.step()
        out = render(w, speaking_id="ruri")
        self.assertIn("무대", out)
        self.assertIn("대화", out)


if __name__ == "__main__":
    unittest.main()
