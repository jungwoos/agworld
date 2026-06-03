"""핵심 데이터 모델 — Emotion enum, Agent, Turn, Utterance, Tick.

데이터 관계:

    Agent (성격/관계/기억)
      │  relationships: {other_id -> sentiment(-1.0..1.0)}
      │  memory: [Turn, ...]   <- 롤링 윈도우로 잘림
      ▼
    한 틱(World.step) 동안 발화자로 뽑히면
      │
      ▼
    Utterance (이 틱의 발화: 누가/뭐라고/감정/대상/티어)
      │  여러 Utterance가 모여
      ▼
    Tick (t, speaker_ids, utterances, emotion_by_agent, whisper?, model_tier)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Emotion(str, Enum):
    """무대 위 이모지로 표현되는 고정 7-enum (plan-design-review 결정).

    모델(FakeProvider 포함)은 반드시 이 중 하나를 고른다. 일관된 아트 + 결정론적 테스트.
    """

    JOY = "joy"
    ANGER = "anger"
    SAD = "sad"
    SURPRISE = "surprise"
    AFFECTION = "affection"
    THINKING = "thinking"
    NEUTRAL = "neutral"

    @property
    def emoji(self) -> str:
        return _EMOJI[self]

    @classmethod
    def coerce(cls, value: object) -> "Emotion":
        """모델/스냅샷에서 온 값을 enum으로 강제. 모르는 값은 NEUTRAL로 폴백."""
        if isinstance(value, Emotion):
            return value
        if isinstance(value, str):
            try:
                return cls(value.strip().lower())
            except ValueError:
                return cls.NEUTRAL
        return cls.NEUTRAL


_EMOJI = {
    Emotion.JOY: "😊",
    Emotion.ANGER: "😠",
    Emotion.SAD: "😢",
    Emotion.SURPRISE: "😮",
    Emotion.AFFECTION: "❤️",
    Emotion.THINKING: "💭",
    Emotion.NEUTRAL: "🙂",
}


# 모델 티어 — 잡담은 싼 모델, 결정적 순간만 비싼 모델.
TIER_AMBIENT = "ambient"
TIER_DECISIVE = "decisive"


@dataclass
class Turn:
    """기억/피드에 남는 한 줄. memory와 트랜스크립트가 공유하는 단위."""

    t: int
    speaker_id: str
    text: str
    emotion: Emotion = Emotion.NEUTRAL
    addressee_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "t": self.t,
            "speaker_id": self.speaker_id,
            "text": self.text,
            "emotion": self.emotion.value,
            "addressee_id": self.addressee_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Turn":
        return cls(
            t=int(d["t"]),
            speaker_id=str(d["speaker_id"]),
            text=str(d["text"]),
            emotion=Emotion.coerce(d.get("emotion")),
            addressee_id=d.get("addressee_id"),
        )


@dataclass
class Utterance:
    """한 틱에서 한 에이전트가 한 발화."""

    speaker_id: str
    text: str
    emotion: Emotion
    addressee_id: str | None = None
    tier: str = TIER_AMBIENT


@dataclass
class Agent:
    """에이전트 상태. 슬립 시 스냅샷으로 저장되고 깨어날 때 복원된다."""

    id: str
    name: str
    persona_prompt: str
    is_mine: bool = False
    relationships: dict[str, float] = field(default_factory=dict)
    memory: list[Turn] = field(default_factory=list)

    def sentiment_toward(self, other_id: str) -> float:
        return self.relationships.get(other_id, 0.0)

    def adjust_sentiment(self, other_id: str, delta: float) -> None:
        """관계 점수를 -1.0..1.0 범위로 클램프하며 조정."""
        new = self.relationships.get(other_id, 0.0) + delta
        self.relationships[other_id] = max(-1.0, min(1.0, new))

    def remember(self, turn: Turn) -> None:
        self.memory.append(turn)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "persona_prompt": self.persona_prompt,
            "is_mine": self.is_mine,
            "relationships": dict(self.relationships),
            "memory": [t.to_dict() for t in self.memory],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Agent":
        return cls(
            id=str(d["id"]),
            name=str(d["name"]),
            persona_prompt=str(d["persona_prompt"]),
            is_mine=bool(d.get("is_mine", False)),
            relationships={k: float(v) for k, v in d.get("relationships", {}).items()},
            memory=[Turn.from_dict(t) for t in d.get("memory", [])],
        )


@dataclass
class Tick:
    """한 틱의 결과. 발화·감정·귓속말·사용된 티어를 담는다."""

    t: int
    speaker_ids: list[str]
    utterances: list[Utterance]
    emotion_by_agent: dict[str, Emotion]
    whisper: str | None = None
    model_tier: str = TIER_AMBIENT
