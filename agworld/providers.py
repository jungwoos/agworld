"""ModelProvider 포트 — 시뮬 엔진은 LLM을 직접 모른다.

    ┌──────────────── Simulation Engine ────────────────┐
    │  (틱루프 · 발화자선택 · 컨텍스트 · 순간판정 · 비용)   │
    └───────────────────────┬───────────────────────────┘
                            │ ModelProvider.respond(prompt, agent_id)
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
        FakeProvider   LocalProvider   CloudProvider
        (v1, 캐닝)      (EXAONE, 나중)  (Haiku급, 나중)

v1은 FakeProvider만 구현. 실제 LLM은 같은 인터페이스로 나중에 끼운다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import Emotion


def count_tokens(text: str) -> int:
    """결정론적 근사 토크나이저 (~4자/토큰). 실제 모델 토크나이저의 자리표시자.

    CostMeter가 이걸로 비용을 추정한다. 결정론적이라 테스트가 안정적.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class ModelResponse:
    text: str
    emotion: Emotion
    prompt_tokens: int
    completion_tokens: int


class ProviderTimeout(Exception):
    """provider가 응답하지 못함 (타임아웃/행). World가 재시도→폴백 처리."""


class ModelProvider(ABC):
    """모든 백엔드가 구현하는 포트."""

    name: str = "abstract"

    @abstractmethod
    def respond(self, prompt: str, agent_id: str) -> ModelResponse:
        """프롬프트를 받아 한 에이전트의 발화를 생성. (text, emotion, 토큰수)."""
        raise NotImplementedError


# 페이크 응답이 받는 fault 모드 (실패경로 테스트용)
FAULT_TIMEOUT = "timeout"      # ProviderTimeout 발생
FAULT_EMPTY = "empty"          # 빈 텍스트
FAULT_MALFORMED = "malformed"  # 감정 없는/깨진 응답


class FakeProvider(ModelProvider):
    """결정론적 캐닝 provider. 엔진을 LLM 없이 100% 테스트하기 위한 v1 백엔드.

    scripts: {agent_id: [(text, Emotion), ...]}  — 에이전트별로 순환 재생.
    스크립트가 없거나 소진되면 중립 한 줄로 폴백.

    실패 주입(테스트용):
        provider.fault_mode = FAULT_TIMEOUT          # 무한 실패 (fault_calls_remaining=None)
        provider.fault_calls_remaining = 1           # 다음 1콜만 실패 → 재시도 검증
    """

    name = "fake"

    def __init__(self, scripts: dict[str, list[tuple[str, Emotion]]] | None = None):
        self._scripts = scripts or {}
        self._cursor: dict[str, int] = {}
        self.calls = 0
        # 실패 주입 상태. fault_calls_remaining: None=무한, 정수=그 횟수만 실패.
        self.fault_mode: str | None = None
        self.fault_calls_remaining: int | None = None

    def _maybe_fault(self) -> str | None:
        if not self.fault_mode:
            return None
        if self.fault_calls_remaining is None:
            return self.fault_mode  # 무한
        if self.fault_calls_remaining <= 0:
            return None             # 소진 → 정상 응답
        self.fault_calls_remaining -= 1
        return self.fault_mode

    def respond(self, prompt: str, agent_id: str) -> ModelResponse:
        self.calls += 1
        prompt_tokens = count_tokens(prompt)

        fault = self._maybe_fault()
        if fault == FAULT_TIMEOUT:
            raise ProviderTimeout(f"fake timeout for {agent_id}")
        if fault == FAULT_EMPTY:
            return ModelResponse("", Emotion.NEUTRAL, prompt_tokens, 0)
        if fault == FAULT_MALFORMED:
            # 감정 자리에 깨진 값 → Emotion.coerce가 NEUTRAL로 흡수해야 함
            return ModelResponse("???", Emotion.coerce("not-an-emotion"), prompt_tokens, 1)

        text, emotion = self._next_line(agent_id)
        return ModelResponse(text, emotion, prompt_tokens, count_tokens(text))

    def _next_line(self, agent_id: str) -> tuple[str, Emotion]:
        lines = self._scripts.get(agent_id)
        if not lines:
            return ("...", Emotion.NEUTRAL)
        i = self._cursor.get(agent_id, 0)
        text, emotion = lines[i % len(lines)]
        self._cursor[agent_id] = i + 1
        return (text, Emotion.coerce(emotion))
