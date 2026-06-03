import os
import tempfile
import unittest

from agworld.models import TIER_DECISIVE, Agent, Emotion
from agworld.providers import FAULT_EMPTY, FAULT_TIMEOUT, FakeProvider
from agworld.sim import World


def make_world(provider=None):
    agents = [
        Agent("ruri", "루리", "솔직함"),
        Agent("dan", "단", "무심함"),
        Agent("sona", "소나", "다정함", is_mine=True),
    ]
    scripts = {
        "ruri": [("안녕", Emotion.JOY)],
        "dan": [("어", Emotion.NEUTRAL)],
        "sona": [("반가워", Emotion.AFFECTION)],
    }
    return World(agents, provider or FakeProvider(scripts))


class TestStep(unittest.TestCase):
    def test_step_produces_tick_and_advances(self):
        w = make_world()
        tick = w.step()
        self.assertIsNotNone(tick)
        self.assertEqual(tick.t, 1)
        self.assertEqual(len(tick.speaker_ids), 1)
        self.assertEqual(len(w.feed), 1)

    def test_emotion_recorded_on_stage(self):
        w = make_world()
        tick = w.step()
        sid = tick.speaker_ids[0]
        self.assertIs(w.emotion_by_agent[sid], tick.utterances[0].emotion)

    def test_round_robin_across_ticks(self):
        w = make_world()
        order = [w.step().speaker_ids[0] for _ in range(3)]
        self.assertEqual(order, ["ruri", "dan", "sona"])


class TestSleep(unittest.TestCase):
    def test_step_returns_none_when_sleeping(self):
        w = make_world()
        w.set_watching(False)
        self.assertIsNone(w.step())
        self.assertEqual(w.t, 0)  # 자는 동안 진행 0

    def test_sleep_then_wake_resumes(self):
        provider = FakeProvider({"ruri": [("hi", Emotion.JOY)],
                                 "dan": [("yo", Emotion.NEUTRAL)],
                                 "sona": [("hey", Emotion.JOY)]})
        w = make_world(provider)
        w.step()
        w.step()
        d = tempfile.mkdtemp()
        path = os.path.join(d, "snap.json")
        w.sleep(path)
        self.assertFalse(w.watching)

        woken = World.wake(path, provider)
        self.assertIsNotNone(woken)
        self.assertEqual(woken.t, 2)            # 직전 t 복원
        self.assertTrue(woken.watching)
        nxt = woken.step()
        self.assertEqual(nxt.t, 3)              # 이어서 진행

    def test_wake_missing_snapshot_is_none(self):
        self.assertIsNone(World.wake("/nonexistent/snap.json", FakeProvider()))


class TestWhisper(unittest.TestCase):
    def test_whisper_prioritizes_and_injects(self):
        w = make_world()
        w.whisper("sona", "루리한테 먼저 말 걸어봐")
        tick = w.step()
        # 귓속말 받은 소나가 우선 발화하고, whisper가 틱에 실린다
        self.assertEqual(tick.speaker_ids[0], "sona")
        self.assertIsNotNone(tick.whisper)
        self.assertEqual(tick.model_tier, TIER_DECISIVE)  # 귓속말 → 결정적

    def test_unknown_target_raises(self):
        w = make_world()
        with self.assertRaises(KeyError):
            w.whisper("nobody", "hi")


class TestFailurePaths(unittest.TestCase):
    def test_timeout_falls_back_without_crash(self):
        provider = FakeProvider({"ruri": [("hi", Emotion.JOY)]})
        provider.fault_mode = FAULT_TIMEOUT  # 영구 타임아웃
        w = make_world(provider)
        tick = w.step()  # 재시도 2회 모두 실패 → 폴백
        self.assertEqual(tick.utterances[0].text, "...")
        self.assertIs(tick.utterances[0].emotion, Emotion.NEUTRAL)

    def test_timeout_then_retry_succeeds(self):
        provider = FakeProvider({"ruri": [("진짜 대사", Emotion.JOY)]})
        provider.fault_mode = FAULT_TIMEOUT
        provider.fault_calls_remaining = 1  # 첫 콜만 실패
        w = make_world(provider)
        tick = w.step()
        self.assertEqual(tick.utterances[0].text, "진짜 대사")  # 재시도 성공

    def test_empty_response_falls_back(self):
        provider = FakeProvider({"ruri": [("hi", Emotion.JOY)]})
        provider.fault_mode = FAULT_EMPTY
        w = make_world(provider)
        tick = w.step()
        self.assertEqual(tick.utterances[0].text, "...")


class TestRelationshipAndMoments(unittest.TestCase):
    def test_anger_lowers_sentiment(self):
        provider = FakeProvider({"ruri": [("화났어", Emotion.ANGER)],
                                 "dan": [("어", Emotion.NEUTRAL)],
                                 "sona": [("음", Emotion.NEUTRAL)]})
        w = make_world(provider)
        w.step()  # 루리가 (다음 발화자에게) 화냄... addressee는 첫 발화라 id순 다음(dan)
        self.assertLess(w._by_id["ruri"].sentiment_toward("dan"), 0.0)

    def test_keyword_marks_decisive_tick(self):
        # 티어는 발화 '생성 전에' 정해지므로, 키워드 판정은 직전 대사(반응 대상)를 본다.
        # 틱1: 루리가 키워드 대사 → (직전 없어서) ambient. 틱2: 단이 그 대사에 반응 → decisive.
        provider = FakeProvider({"ruri": [("나 좀 서운했어", Emotion.SAD)],
                                 "dan": [("어...", Emotion.SURPRISE)],
                                 "sona": [("음", Emotion.NEUTRAL)]})
        w = make_world(provider)
        w.step()  # 틱1: 루리 (ambient — 직전 대사 없음)
        w.step()  # 틱2: 단이 "서운했어"에 반응 → decisive
        self.assertNotIn(1, w.decisive_ticks)
        self.assertIn(2, w.decisive_ticks)

    def test_empty_agents_rejected(self):
        with self.assertRaises(ValueError):
            World([], FakeProvider())


if __name__ == "__main__":
    unittest.main()
