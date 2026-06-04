"""장소(places) 구성 — 여러 World를 만들고 메타데이터와 함께 보관.

- "room" (우리 방): 에이전트 3인. 작고 친밀한 공간.
- "town" (우리 동네): 고정 이웃 10인(소나 포함). PRD의 A안. 틱당 발화자는 1명이라 10인이어도
  per-tick LLM 비용은 동일 — 10인 제한은 '사회 공간 크기' 통제이자 비용 통제 장치.

각 장소는 독립 World(자체 피드·관계·스케줄러). 같은 이름의 에이전트라도 장소별로 별개 인스턴스.
"""

from __future__ import annotations

from .models import Agent, Emotion
from .providers import FakeProvider
from .sim import World

# (id, 이름, 페르소나, 대사[(text, emotion)...], 내것?)
ROOM_SPECS = [
    ("ruri", "루리", "감정 표현이 솔직하고 서운함을 잘 탄다.", [
        ("오늘 다들 좀 조용하네.", Emotion.NEUTRAL),
        ("단, 아까 그 말 진심이었어? 나 좀 서운했어.", Emotion.ANGER),
        ("...사과는 안 할 거야?", Emotion.SAD),
    ], False),
    ("dan", "단", "무심한 척하지만 마음 약하고 사과를 잘 한다.", [
        ("아 오늘 좀 피곤하다.", Emotion.SAD),
        ("그건 그냥 농담이었는데.", Emotion.SURPRISE),
        ("미안, 진심이 아니었어. 내가 말을 잘못했네.", Emotion.AFFECTION),
    ], False),
    ("sona", "소나", "둘 사이를 중재하는 다정한 관찰자.", [
        ("무슨 일 있었어?", Emotion.THINKING),
        ("둘 다 진정하고... 얘기 좀 해봐.", Emotion.THINKING),
        ("거봐, 잘 풀렸네.", Emotion.JOY),
    ], True),
]

TOWN_SPECS = [
    ("sona", "소나", "동네의 다정한 중재자. 분위기를 살핀다.", [
        ("다들 오늘 기분 어때?", Emotion.JOY),
        ("천천히 얘기해도 돼.", Emotion.THINKING),
        ("우리 동네 사람들 다 좋아.", Emotion.AFFECTION),
    ], True),
    ("ruri", "루리", "솔직하고 감정 기복이 있다.", [
        ("어제 일 아직 좀 서운해.", Emotion.SAD),
        ("아 몰라, 신경 안 쓸래.", Emotion.ANGER),
        ("그래도 같이 있으면 좋네.", Emotion.JOY),
    ], False),
    ("dan", "단", "무심하지만 정 많은 이웃.", [
        ("커피 마실 사람?", Emotion.NEUTRAL),
        ("나도 사실 좀 미안했어.", Emotion.AFFECTION),
    ], False),
    ("mina", "미나", "수다스럽고 소문을 좋아한다.", [
        ("그거 들었어? 옆집 얘기.", Emotion.SURPRISE),
        ("에이 진짜야 진짜.", Emotion.JOY),
        ("비밀인데 말이야...", Emotion.THINKING),
    ], False),
    ("hodu", "호두", "느긋하고 낙천적.", [
        ("날씨 좋다~ 산책 갈까.", Emotion.JOY),
        ("뭐든 다 잘 될 거야.", Emotion.AFFECTION),
    ], False),
    ("jinwoo", "진우", "진지하고 걱정이 많다.", [
        ("그게 정말 괜찮을까...", Emotion.THINKING),
        ("난 좀 불안한데.", Emotion.SAD),
    ], False),
    ("byeol", "별이", "엉뚱하고 명랑하다.", [
        ("우와 저것 봐!", Emotion.SURPRISE),
        ("헤헤 재밌다.", Emotion.JOY),
    ], False),
    ("kkami", "까미", "조용하고 관찰력이 좋다.", [
        ("...다들 표정이 다르네.", Emotion.THINKING),
        ("난 듣는 게 좋아.", Emotion.NEUTRAL),
    ], False),
    ("yoon", "윤", "예의 바르고 차분하다.", [
        ("안녕하세요, 오늘도 평안하길.", Emotion.AFFECTION),
        ("천천히 가도 괜찮아요.", Emotion.JOY),
    ], False),
    ("tori", "토리", "장난기 많고 시비를 잘 건다.", [
        ("야 너 그거 진심이야?", Emotion.SURPRISE),
        ("에이 농담이야 농담.", Emotion.JOY),
        ("삐졌어? 미안미안.", Emotion.AFFECTION),
    ], False),
]


def _build_world(specs) -> World:
    agents = [Agent(i, n, p, is_mine=mine) for (i, n, p, _lines, mine) in specs]
    scripts = {i: lines for (i, _n, _p, lines, _mine) in specs}
    return World(agents, FakeProvider(scripts))


def build_places() -> dict:
    """장소 id -> {title, world}. 순서 유지(dict는 3.7+ 삽입순)."""
    return {
        "room": {"title": "우리 방", "world": _build_world(ROOM_SPECS)},
        "town": {"title": "우리 동네", "world": _build_world(TOWN_SPECS)},
    }


def places_meta(places: dict) -> list[dict]:
    """클라이언트 탭용 목록: [{id, title, agents}]."""
    return [{"id": pid, "title": p["title"], "agents": len(p["world"].agents)}
            for pid, p in places.items()]
