"""run_live 실시간 루프의 결정론적 통합 테스트.

ScriptedIO가 가짜 시계 + 가짜 입력을 주입한다. TTY 없이도 틱 타이머·귓속말 주입·종료·
슬립을 검증한다. (실제 select/시간 대신 스크립트된 이벤트 타임라인으로 구동)
"""

import os
import tempfile
import unittest
from collections import deque

from agworld.cli import run_live
from agworld.models import Agent, Emotion
from agworld.providers import FakeProvider
from agworld.sim import World


class ScriptedIO:
    """events: [("timeout",) | ("input", text), ...] 순서대로 소비.

    wait(timeout): 'timeout' 이벤트면 시계를 timeout만큼 진행하고 False,
                   'input' 이벤트면 텍스트를 큐에 넣고 True. 소진되면 EOF("")로 종료 유도.
    """

    def __init__(self, events, tty=True):
        self._events = deque(events)
        self._inputs = deque()
        self._clock = 0.0
        self._tty = tty
        self.output = []

    def isatty(self):
        return self._tty

    def now(self):
        return self._clock

    def wait(self, timeout):
        if not self._events:
            self._inputs.append("")  # EOF → 루프 종료
            return True
        kind, *rest = self._events.popleft()
        if kind == "input":
            self._inputs.append(rest[0])
            return True
        self._clock += timeout  # timeout 이벤트: 시간 흐름
        return False

    def readline(self):
        return self._inputs.popleft() if self._inputs else ""

    def emit(self, text):
        self.output.append(text)


def make_world():
    agents = [
        Agent("ruri", "루리", "솔직함"),
        Agent("sona", "소나", "다정함", is_mine=True),
    ]
    scripts = {"ruri": [("안녕", Emotion.JOY)], "sona": [("응 알겠어", Emotion.AFFECTION)]}
    return World(agents, FakeProvider(scripts))


class TestRunLive(unittest.TestCase):
    def test_ticks_advance_on_timeout(self):
        w = make_world()
        io = ScriptedIO([("timeout",), ("input", "q")])
        rc = run_live(w, interval=10.0, snapshot=None, io=io)
        self.assertEqual(rc, 0)
        self.assertEqual(w.t, 2)        # 즉시 1틱 + 타임아웃 1틱
        self.assertFalse(w.watching)    # 종료 시 슬립

    def test_clock_advances_by_interval(self):
        w = make_world()
        io = ScriptedIO([("timeout",), ("timeout",), ("input", "q")])
        run_live(w, interval=10.0, snapshot=None, io=io)
        self.assertEqual(io.now(), 20.0)  # 타임아웃 2회 × 10초

    def test_whisper_injected_into_a_tick(self):
        w = make_world()
        # 입력(귓속말)→타임아웃→타임아웃→q : 귓속말 받은 소나가 다음 틱에 우선 발화
        io = ScriptedIO([
            ("input", "루리한테 먼저 말 걸어봐"),
            ("timeout",),
            ("timeout",),
            ("input", "q"),
        ])
        run_live(w, interval=10.0, snapshot=None, io=io)
        joined = "\n".join(io.output)
        self.assertIn("속삭임 반영됨", joined)  # 어떤 틱에 whisper가 실렸다
        self.assertIn("소나에게 속삭임 전달됨", joined)  # 큐잉 확인 메시지

    def test_quit_triggers_sleep_snapshot(self):
        w = make_world()
        d = tempfile.mkdtemp()
        path = os.path.join(d, "snap.json")
        io = ScriptedIO([("input", "q")])
        run_live(w, interval=10.0, snapshot=path, io=io)
        self.assertTrue(os.path.exists(path))  # 슬립 시 스냅샷 저장
        self.assertFalse(w.watching)

    def test_eof_breaks_loop(self):
        w = make_world()
        io = ScriptedIO([])  # 이벤트 없음 → 즉시 EOF
        rc = run_live(w, interval=10.0, snapshot=None, io=io)
        self.assertEqual(rc, 0)

    def test_non_tty_returns_one(self):
        w = make_world()
        io = ScriptedIO([], tty=False)
        rc = run_live(w, interval=10.0, snapshot=None, io=io)
        self.assertEqual(rc, 1)
        self.assertTrue(any("터미널이 필요" in o for o in io.output))

    def test_rate_limit_surfaced_in_output(self):
        w = make_world()
        # 같은 시각에 4번 귓속말 → 기본 리밋(3) 초과가 출력에 보여야
        io = ScriptedIO([
            ("input", "하나"), ("input", "둘"), ("input", "셋"),
            ("input", "넷"), ("input", "q"),
        ])
        run_live(w, interval=10.0, snapshot=None, io=io)
        self.assertTrue(any("⏳" in o for o in io.output))


if __name__ == "__main__":
    unittest.main()
