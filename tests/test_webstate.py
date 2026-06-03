import unittest

from agworld.models import Agent, Emotion
from agworld.providers import FakeProvider
from agworld.sim import World
from agworld.webstate import submit_whisper, world_state_dict


def make_world():
    agents = [
        Agent("ruri", "루리", "솔직함"),
        Agent("sona", "소나", "다정함", is_mine=True),
    ]
    scripts = {"ruri": [("안녕", Emotion.ANGER)], "sona": [("응", Emotion.AFFECTION)]}
    return World(agents, FakeProvider(scripts))


class TestWorldStateDict(unittest.TestCase):
    def test_initial_state(self):
        w = make_world()
        s = world_state_dict(w)
        self.assertEqual(s["t"], 0)
        self.assertEqual(len(s["agents"]), 2)
        self.assertEqual(s["feed"], [])
        self.assertEqual(s["my_agent"]["id"], "sona")

    def test_agent_emotion_and_mine_flag(self):
        w = make_world()
        w.step()  # 루리(ANGER) 발화
        s = world_state_dict(w)
        ruri = next(a for a in s["agents"] if a["id"] == "ruri")
        self.assertEqual(ruri["emotion"], "anger")
        self.assertEqual(ruri["emoji"], Emotion.ANGER.emoji)
        sona = next(a for a in s["agents"] if a["id"] == "sona")
        self.assertTrue(sona["is_mine"])

    def test_speaking_flag_on_last_speaker(self):
        w = make_world()
        w.step()
        s = world_state_dict(w)
        speaking = [a["id"] for a in s["agents"] if a["speaking"]]
        self.assertEqual(speaking, ["ruri"])

    def test_feed_has_names_and_decisive(self):
        w = make_world()
        w.decisive_ticks.add(1)
        w.step()
        s = world_state_dict(w)
        self.assertEqual(s["feed"][0]["name"], "루리")
        self.assertTrue(s["feed"][0]["decisive"])

    def test_feed_capped_at_30(self):
        provider = FakeProvider({"ruri": [("x", Emotion.NEUTRAL)], "sona": [("y", Emotion.NEUTRAL)]})
        w = World([Agent("ruri", "루리", "p"), Agent("sona", "소나", "p", is_mine=True)], provider)
        for _ in range(40):
            w.step()
        s = world_state_dict(w)
        self.assertEqual(len(s["feed"]), 30)


class TestSubmitWhisper(unittest.TestCase):
    def test_queues_to_my_agent(self):
        w = make_world()
        r = submit_whisper(w, "사과해보라고 해")
        self.assertTrue(r["ok"])
        self.assertTrue(w.whispers.has_pending("sona"))

    def test_empty_rejected(self):
        w = make_world()
        r = submit_whisper(w, "   ")
        self.assertFalse(r["ok"])

    def test_no_mine_agent(self):
        w = World([Agent("a", "A", "p")], FakeProvider())
        r = submit_whisper(w, "hi")
        self.assertFalse(r["ok"])
        self.assertIn("내 에이전트", r["message"])

    def test_rate_limit_message(self):
        from agworld.whisper import WhisperQueue
        w = World([Agent("sona", "소나", "p", is_mine=True)], FakeProvider(),
                  whisper_queue=WhisperQueue(rate_limit=1))
        self.assertTrue(submit_whisper(w, "하나")["ok"])
        r = submit_whisper(w, "둘")
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
