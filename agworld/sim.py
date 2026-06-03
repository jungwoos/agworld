"""World — 한 틱을 조립하는 시뮬레이션 엔진.

step() 파이프라인:

   advance()────┐ (자는 중이면 None 반환, 여기서 끝)
                ▼
   발화자 선택 (라운드로빈, 귓속말 대상 우선)
                ▼
   귓속말 pop ──▶ 대상 결정 ──▶ 티어 판정(규칙기반)
                ▼
   컨텍스트 트리밍(롤링 8턴) ──▶ 프롬프트 빌드(귓속말=격리된 힌트)
                ▼
   provider.respond  (타임아웃/빈응답 → 1회 재시도 → 앰비언트 폴백)
                ▼
   메모리/관계/감정 갱신 ──▶ Tick 반환
"""

from __future__ import annotations

from .context import build_prompt, trim_context
from .cost import CostMeter
from .models import (
    TIER_DECISIVE,
    Agent,
    Emotion,
    Tick,
    Turn,
    Utterance,
)
from .moments import MomentClassifier
from .providers import ModelProvider, ModelResponse, ProviderTimeout
from .persistence import load_snapshot, save_snapshot
from .scheduler import SpeakerSelector, TickScheduler
from .whisper import WhisperQueue

# 감정별 관계 점수 변화량. 시간이 지나며 관계가 누적 → 결정적 순간 판정(b)을 살린다.
_SENTIMENT_DELTA = {
    Emotion.ANGER: -0.2,
    Emotion.SAD: -0.1,
    Emotion.AFFECTION: 0.2,
    Emotion.JOY: 0.1,
}


class World:
    def __init__(
        self,
        agents: list[Agent],
        provider: ModelProvider,
        *,
        scheduler: TickScheduler | None = None,
        selector: SpeakerSelector | None = None,
        classifier: MomentClassifier | None = None,
        whisper_queue: WhisperQueue | None = None,
        prices: dict | None = None,
    ):
        if not agents:
            raise ValueError("최소 1명의 에이전트가 필요")
        self.agents = agents
        self._by_id = {a.id: a for a in agents}
        self.meter = CostMeter(provider, prices=prices) if prices else CostMeter(provider)
        self.scheduler = scheduler or TickScheduler()
        self.selector = selector or SpeakerSelector()
        self.classifier = classifier or MomentClassifier()
        self.whispers = whisper_queue or WhisperQueue()
        # 무대 표시용 현재 감정 + 트랜스크립트 피드
        self.emotion_by_agent: dict[str, Emotion] = {a.id: Emotion.NEUTRAL for a in agents}
        self.feed: list[Turn] = []
        self.decisive_ticks: set[int] = set()  # ⚡ 결정적 순간으로 마킹된 틱들

    @property
    def t(self) -> int:
        return self.scheduler.t

    @property
    def watching(self) -> bool:
        return self.scheduler.watching

    def agent_ids(self) -> list[str]:
        return [a.id for a in self.agents]

    # ── 관전/슬립 ──────────────────────────────────────────────
    def set_watching(self, watching: bool) -> None:
        self.scheduler.set_watching(watching)

    def whisper(self, target_id: str, text: str) -> None:
        """유저 귓속말을 큐에 넣는다(대상의 다음 가용 틱에 주입). RateLimited 가능."""
        if target_id not in self._by_id:
            raise KeyError(f"알 수 없는 에이전트: {target_id}")
        self.whispers.enqueue(target_id, text, self.t)

    # ── 한 틱 ─────────────────────────────────────────────────
    def step(self) -> Tick | None:
        t = self.scheduler.advance()
        if t is None:
            return None  # 자는 중 — 아무 일도 안 일어남

        ids = self.agent_ids()
        priority = self._whisper_priority(ids)
        speaker_id = self.selector.next_speaker(ids, priority_id=priority)
        speaker = self._by_id[speaker_id]

        whisper_text = self.whispers.pop_for(speaker_id)
        addressee_id = self._pick_addressee(speaker_id)
        recent_text = self.feed[-1].text if self.feed else ""

        tier = self.classifier.classify(
            speaker, addressee_id, recent_text, has_whisper=whisper_text is not None
        )

        context = trim_context(speaker.memory)
        prompt = build_prompt(speaker, context, whisper=whisper_text)
        resp = self._respond_with_fallback(prompt, speaker_id, tier)

        utterance = Utterance(
            speaker_id=speaker_id,
            text=resp.text,
            emotion=resp.emotion,
            addressee_id=addressee_id,
            tier=tier,
        )
        self._apply(utterance, t)
        if tier == TIER_DECISIVE:
            self.decisive_ticks.add(t)

        return Tick(
            t=t,
            speaker_ids=[speaker_id],
            utterances=[utterance],
            emotion_by_agent=dict(self.emotion_by_agent),
            whisper=whisper_text,
            model_tier=tier,
        )

    def _respond_with_fallback(self, prompt: str, speaker_id: str, tier: str) -> ModelResponse:
        """타임아웃/빈응답 → 1회 재시도 → 앰비언트 폴백. 한 에이전트 실패가 세션을 멈추지 않게."""
        for _ in range(2):
            try:
                resp = self.meter.respond(prompt, speaker_id, tier)
            except ProviderTimeout:
                continue
            if resp.text.strip():
                return resp
        # 두 번 다 실패/빈응답 → 모델 콜 없는 조용한 폴백 한 줄
        return ModelResponse("...", Emotion.NEUTRAL, 0, 0)

    def _apply(self, u: Utterance, t: int) -> None:
        turn = Turn(t=t, speaker_id=u.speaker_id, text=u.text,
                    emotion=u.emotion, addressee_id=u.addressee_id)
        # 단일 방 — 모두가 듣는다. 각 에이전트 메모리에 기록.
        for a in self.agents:
            a.remember(turn)
        self.feed.append(turn)
        self.emotion_by_agent[u.speaker_id] = u.emotion
        # 관계 누적
        if u.addressee_id is not None:
            delta = _SENTIMENT_DELTA.get(u.emotion)
            if delta:
                self._by_id[u.speaker_id].adjust_sentiment(u.addressee_id, delta)

    def _whisper_priority(self, ids: list[str]) -> str | None:
        for aid in ids:
            if self.whispers.has_pending(aid):
                return aid
        return None

    def _pick_addressee(self, speaker_id: str) -> str | None:
        """가장 최근에 말한 '다른' 에이전트에게 응답하는 구조(자연스러운 핑퐁)."""
        for turn in reversed(self.feed):
            if turn.speaker_id != speaker_id:
                return turn.speaker_id
        # 피드가 비었거나 자기 말뿐 → id 순서상 다음 에이전트
        ids = self.agent_ids()
        others = [i for i in ids if i != speaker_id]
        return others[0] if others else None

    # ── 영속성 ────────────────────────────────────────────────
    def sleep(self, path: str) -> None:
        """관전 종료 시 호출: 관전 끄고 상태 스냅샷 저장."""
        self.set_watching(False)
        save_snapshot(self.agents, path, t=self.t)

    @classmethod
    def wake(cls, path: str, provider: ModelProvider, **kwargs) -> "World | None":
        """스냅샷에서 복원. 없으면 None(호출자가 기본 페르소나로 시작)."""
        loaded = load_snapshot(path)
        if loaded is None:
            return None
        agents, t = loaded
        world = cls(agents, provider, scheduler=TickScheduler(watching=True, start_t=t), **kwargs)
        return world
