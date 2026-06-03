"""결정적 순간 판정 — 어느 틱에 비싼 모델을 쓸지 규칙 기반으로 결정.

v1은 규칙 기반(추가 LLM 콜 0). 모델 기반 1차 판정은 비용 때문에 후순위(TODOS 참고).

규칙: 아래 중 하나라도 참이면 '결정적'(비싼 티어), 아니면 '앰비언트'(싼 티어).
    (a) 이번 틱에 귓속말이 있다
    (b) 발화자-대상 관계 점수의 절댓값이 임계 이상(긴장/애정 고조)
    (c) 키워드 트리거(갈등/고백/이별 등 드라마 신호)
"""

from __future__ import annotations

from .models import TIER_AMBIENT, TIER_DECISIVE, Agent

RELATIONSHIP_THRESHOLD = 0.5

# 드라마 신호 키워드. 의도적으로 작게 시작 — 실측하며 튜닝.
DECISIVE_KEYWORDS = (
    "사과", "미안", "진심", "서운", "헤어", "고백", "좋아해", "싫어",
    "화났", "약속", "배신", "비밀",
)


class MomentClassifier:
    def __init__(self, keywords: tuple[str, ...] = DECISIVE_KEYWORDS,
                 relationship_threshold: float = RELATIONSHIP_THRESHOLD):
        self._keywords = keywords
        self._threshold = relationship_threshold

    def classify(
        self,
        speaker: Agent,
        addressee_id: str | None,
        recent_text: str,
        has_whisper: bool,
    ) -> str:
        if has_whisper:
            return TIER_DECISIVE
        if addressee_id is not None:
            if abs(speaker.sentiment_toward(addressee_id)) >= self._threshold:
                return TIER_DECISIVE
        if recent_text and any(k in recent_text for k in self._keywords):
            return TIER_DECISIVE
        return TIER_AMBIENT
