"""콘솔 데모 엔트리포인트.

    python -m agworld                 # 8틱 자동 재생
    python -m agworld --ticks 12      # 틱 수 지정
    python -m agworld --interactive   # 매 틱마다 소나에게 귓속말 입력
    python -m agworld --snapshot path # 슬립/웨이크 스냅샷 파일

마법 게이트: 시나리오를 '짜지 않아도'(여기선 FakeProvider 스크립트) 에이전트들 사이에서
드라마가 읽히는지, 귓속말을 넣으면 반영되는지 눈으로 확인하는 용도.
"""

from __future__ import annotations

import argparse
import os
import select
import sys
import time

from .console import render
from .live import QUIT, apply_command, find_my_agent
from .models import Agent, Emotion
from .providers import FakeProvider
from .sim import World
from .whisper import RateLimited

# 시나리오를 '직접' 짜지 않는다 — 에이전트별 성향 대사만 주고, 누가 언제 말할지는 엔진이 정한다.
# 키워드(서운/진심/사과)가 결정적 순간 ⚡을 트리거한다.
_SCRIPTS = {
    "ruri": [
        ("오늘 다들 좀 조용하네.", Emotion.NEUTRAL),
        ("단, 아까 그 말 진심이었어? 나 좀 서운했어.", Emotion.ANGER),
        ("...사과는 안 할 거야?", Emotion.SAD),
        ("뭐, 됐어. 신경 쓰지 마.", Emotion.NEUTRAL),
    ],
    "dan": [
        ("아 오늘 좀 피곤하다.", Emotion.SAD),
        ("그건 그냥 농담이었는데.", Emotion.SURPRISE),
        ("미안, 진심이 아니었어. 내가 말을 잘못했네.", Emotion.AFFECTION),
        ("우리 풀자, 응?", Emotion.JOY),
    ],
    "sona": [
        ("무슨 일 있었어?", Emotion.THINKING),
        ("둘 다 진정하고... 얘기 좀 해봐.", Emotion.THINKING),
        ("루리도 단도 서로 좋아하잖아.", Emotion.AFFECTION),
        ("거봐, 잘 풀렸네.", Emotion.JOY),
    ],
}


def build_demo_world(provider: FakeProvider | None = None) -> World:
    agents = [
        Agent("ruri", "루리", "감정 표현이 솔직하고 서운함을 잘 탄다."),
        Agent("dan", "단", "무심한 척하지만 마음 약하고 사과를 잘 한다."),
        Agent("sona", "소나", "둘 사이를 중재하는 다정한 관찰자.", is_mine=True),
    ]
    return World(agents, provider or FakeProvider(_SCRIPTS))


def _show_frame(world: World, tick) -> None:
    """한 틱 결과를 화면에 그린다(무대+피드). 자동(--ticks) 모드용."""
    speaking = tick.speaker_ids[0] if tick.speaker_ids else None
    print("\033[2J\033[H", end="")
    print(render(world, speaking_id=speaking))
    if tick.whisper:
        print(f"\n   🤫 (속삭임 반영됨: \"{tick.whisper}\")")


def _frame_text(world: World, tick) -> str:
    speaking = tick.speaker_ids[0] if tick.speaker_ids else None
    text = "\033[2J\033[H" + render(world, speaking_id=speaking)
    if tick.whisper:
        text += f"\n\n   🤫 (속삭임 반영됨: \"{tick.whisper}\")"
    return text


class TerminalIO:
    """실시간 루프의 실제 I/O — select/sys/time 래퍼. 테스트는 ScriptedIO로 대체."""

    def isatty(self) -> bool:
        return sys.stdin.isatty()

    def now(self) -> float:
        return time.monotonic()

    def wait(self, timeout: float) -> bool:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        return bool(ready)

    def readline(self) -> str:
        return sys.stdin.readline()

    def emit(self, text: str) -> None:
        print(text)


def run_live(world: World, interval: float, snapshot: str | None, io=None) -> int:
    """실시간 관전 루프 — 틱은 interval 초마다, 귓속말은 아무 때나.

    io는 now()/wait(timeout)/readline()/emit()/isatty()를 제공(기본 TerminalIO).
    wait(timeout): 입력 준비되면 True, 타임아웃이면 False. 입력 오면 귓속말 처리(틱 안 밀림),
    타임아웃이면 한 틱 진행. 스레드 없음. io 주입 덕에 가짜 시계로 결정론적 테스트 가능.
    """
    io = io or TerminalIO()
    if not io.isatty():
        io.emit("(라이브 모드는 터미널이 필요합니다. --ticks 자동 모드를 쓰세요.)")
        return 1

    mine = find_my_agent(world)
    target = mine.name if mine else "(없음)"
    io.emit(f"실시간 관전 시작 — {interval:.0f}초마다 틱. 아무 때나 {target}에게 속삭이세요. (엔터=건너뜀, q=종료)")

    next_tick = io.now()  # 첫 틱 즉시
    running = True
    while running:
        now = io.now()
        if now >= next_tick:
            tick = world.step()
            if tick is not None:
                io.emit(_frame_text(world, tick))
            next_tick = now + interval

        timeout = max(0.0, next_tick - io.now())
        if io.wait(timeout):
            raw = io.readline()
            if raw == "":  # EOF (Ctrl-D) 또는 입력 소진
                break
            kind, status = apply_command(world, raw)
            if status:
                io.emit(status)
            if kind == QUIT:
                running = False

    if snapshot:
        world.sleep(snapshot)
        io.emit(f"(잠듦 — 상태를 {snapshot}에 저장)")
    else:
        world.set_watching(False)
    io.emit("\n세션 비용:\n" + world.meter.summary())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agworld", description="AG-World 콘솔 관전 데모")
    parser.add_argument("--ticks", type=int, default=8, help="자동 재생할 틱 수")
    parser.add_argument("--interactive", action="store_true", help="매 틱 소나에게 귓속말")
    parser.add_argument("--live", action="store_true", help="실시간 관전(틱 타이머 + 자유 귓속말)")
    parser.add_argument("--web", action="store_true", help="브라우저 웹뷰 서버 실행")
    # 호스팅(예: Render)은 $PORT를 주입한다. 없으면 8765.
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)), help="웹뷰 포트($PORT 환경변수 우선)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="바인딩 호스트(배포 시 0.0.0.0)")
    parser.add_argument("--interval", type=float, default=10.0, help="라이브/웹 틱 간격(초)")
    parser.add_argument("--snapshot", type=str, default=None, help="슬립/웨이크 스냅샷 경로")
    args = parser.parse_args(argv)

    provider = FakeProvider(_SCRIPTS)
    world = None
    if args.snapshot:
        world = World.wake(args.snapshot, provider)
        if world is not None:
            print(f"(스냅샷에서 깨어남 — 틱 {world.t}부터 이어감)\n")
    if world is None:
        world = build_demo_world(provider)

    if args.web:
        from .web import serve
        serve(host=args.host, port=args.port, interval=args.interval)  # serve가 장소(방/동네) 구성
        return 0

    if args.live:
        return run_live(world, args.interval, args.snapshot)

    for _ in range(args.ticks):
        tick = world.step()
        if tick is None:
            print("(자는 중 — 관전을 켜야 깨어납니다)")
            break
        _show_frame(world, tick)

        if args.interactive:
            try:
                raw = input("\n🤫 소나에게 속삭이기 (엔터=건너뜀, q=종료): ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if raw.lower() == "q":
                break
            if raw:
                try:
                    world.whisper("sona", raw)
                except RateLimited as e:
                    print(f"   ⏳ {e}")

    print("\n" + "─" * 30)
    print("세션 비용:")
    print(world.meter.summary())

    if args.snapshot:
        world.sleep(args.snapshot)
        print(f"\n(잠듦 — 상태를 {args.snapshot}에 저장)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
