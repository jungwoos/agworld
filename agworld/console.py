"""관전 화면 렌더링 (콘솔 버전).

설계(plan-design-review): 무대엔 감정 이모지만, 말은 피드에서.
2.5D 뷰어 페이즈가 오기 전, 콘솔에서 같은 정보 구조를 텍스트로 구현한다.

순수 문자열 함수라 테스트 가능(렌더 결과를 assert).
"""

from __future__ import annotations

from .models import Emotion
from .sim import World

MINE_ACCENT = "★"  # 내 에이전트 표식 (색만이 아니라 형태로도 구분 → 색맹 안전)


def render_stage(world: World, speaking_id: str | None = None) -> str:
    """무대: 각 에이전트의 현재 감정 이모지 + 이름. 발화중 ◀, 내 에이전트 ★. 자면 💤."""
    lines = ["┌─ 무대 " + ("(자는 중 💤)" if not world.watching else f"· 틱 {world.t}") + " ─┐"]
    for a in world.agents:
        emo = (Emotion.NEUTRAL if not world.watching else world.emotion_by_agent[a.id])
        face = "💤" if not world.watching else emo.emoji
        mark = f" {MINE_ACCENT} 내 에이전트" if a.is_mine else ""
        speaking = "  ◀ 말하는 중" if a.id == speaking_id and world.watching else ""
        lines.append(f"   {face}  {a.name}{mark}{speaking}")
    lines.append("└" + "─" * 22 + "┘")
    return "\n".join(lines)


def render_feed(world: World, last_n: int = 8) -> str:
    """피드: 페이스드 트랜스크립트. 틱 단위 구분, 결정적 순간은 ⚡."""
    turns = world.feed[-last_n:]
    if not turns:
        return "💬 대화\n   (아직 조용하다...)"
    rows = ["💬 대화"]
    last_t = None
    for turn in turns:
        if turn.t != last_t:
            mark = " ⚡" if turn.t in world.decisive_ticks else ""
            rows.append(f"   — 틱 {turn.t}{mark} —")
            last_t = turn.t
        who = world._by_id.get(turn.speaker_id)
        name = who.name if who else turn.speaker_id
        star = MINE_ACCENT if who and who.is_mine else " "
        rows.append(f"   {star} {name}: {turn.text} {turn.emotion.emoji}")
    return "\n".join(rows)


def render(world: World, speaking_id: str | None = None) -> str:
    """무대 + 피드 한 화면."""
    return render_stage(world, speaking_id) + "\n\n" + render_feed(world)
