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
        s = world_state_dict(w, viewer_id="sona")
        self.assertEqual(s["t"], 0)
        self.assertEqual(len(s["agents"]), 2)
        self.assertEqual(s["feed"], [])
        self.assertEqual(s["my_agent"]["id"], "sona")

    def test_spectator_has_no_my_agent(self):
        w = make_world()
        s = world_state_dict(w)  # viewer_id 없음 → 관전 모드
        self.assertIsNone(s["my_agent"])
        self.assertFalse(any(a["is_mine"] for a in s["agents"]))

    def test_viewer_identity_is_per_viewer(self):
        w = make_world()
        s_sona = world_state_dict(w, viewer_id="sona")
        s_ruri = world_state_dict(w, viewer_id="ruri")
        self.assertEqual(s_sona["my_agent"]["id"], "sona")
        self.assertEqual(s_ruri["my_agent"]["id"], "ruri")
        self.assertTrue(next(a for a in s_ruri["agents"] if a["id"] == "ruri")["is_mine"])
        self.assertFalse(next(a for a in s_ruri["agents"] if a["id"] == "sona")["is_mine"])

    def test_unknown_viewer_is_spectator(self):
        w = make_world()
        s = world_state_dict(w, viewer_id="ghost")
        self.assertIsNone(s["my_agent"])

    def test_agent_emotion_and_mine_flag(self):
        w = make_world()
        w.step()  # 루리(ANGER) 발화
        s = world_state_dict(w, viewer_id="sona")
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
    def test_queues_to_viewer_agent(self):
        w = make_world()
        r = submit_whisper(w, "사과해보라고 해", viewer_id="sona")
        self.assertTrue(r["ok"])
        self.assertTrue(w.whispers.has_pending("sona"))

    def test_two_viewers_queue_to_own_agents(self):
        w = make_world()
        self.assertTrue(submit_whisper(w, "화 풀어", viewer_id="ruri")["ok"])
        self.assertTrue(submit_whisper(w, "중재해줘", viewer_id="sona")["ok"])
        self.assertTrue(w.whispers.has_pending("ruri"))
        self.assertTrue(w.whispers.has_pending("sona"))

    def test_empty_rejected(self):
        w = make_world()
        r = submit_whisper(w, "   ", viewer_id="sona")
        self.assertFalse(r["ok"])

    def test_spectator_rejected(self):
        w = make_world()
        r = submit_whisper(w, "hi")  # viewer_id 없음 → 관전 모드
        self.assertFalse(r["ok"])
        self.assertIn("관전", r["message"])

    def test_viewer_agent_not_in_world(self):
        w = World([Agent("a", "A", "p")], FakeProvider())
        r = submit_whisper(w, "hi", viewer_id="ghost")
        self.assertFalse(r["ok"])
        self.assertIn("내 에이전트", r["message"])

    def test_rate_limit_message(self):
        from agworld.whisper import WhisperQueue
        w = World([Agent("sona", "소나", "p", is_mine=True)], FakeProvider(),
                  whisper_queue=WhisperQueue(rate_limit=1))
        self.assertTrue(submit_whisper(w, "하나", viewer_id="sona")["ok"])
        r = submit_whisper(w, "둘", viewer_id="sona")
        self.assertFalse(r["ok"])

    def test_rate_limit_is_per_viewer(self):
        from agworld.whisper import WhisperQueue
        w = World(
            [Agent("sona", "소나", "p", is_mine=True), Agent("ruri", "루리", "p")],
            FakeProvider(), whisper_queue=WhisperQueue(rate_limit=1),
        )
        self.assertTrue(submit_whisper(w, "하나", viewer_id="sona")["ok"])
        self.assertFalse(submit_whisper(w, "둘", viewer_id="sona")["ok"])   # 소나 주인은 리밋
        self.assertTrue(submit_whisper(w, "나는 따로", viewer_id="ruri")["ok"])  # 루리 주인은 영향 없음


if __name__ == "__main__":
    unittest.main()
