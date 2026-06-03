"""CostMeter — provider를 감싸 티어별 토큰/콜/비용을 계측.

성공지표 "세션 비용 ~$0.15 이하"의 측정 근거. 백엔드가 뭐든(로컬/클라우드) 동일하게 계측.
로컬 provider면 가격표에서 해당 티어를 $0으로 두면 비용이 자동으로 0이 된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import TIER_AMBIENT, TIER_DECISIVE
from .providers import ModelProvider, ModelResponse

# 티어별 1K 토큰당 달러 (입력, 출력). v1 기본은 클라우드 상한선 가정.
# 로컬 앰비언트로 가려면 ambient를 (0.0, 0.0)으로 바꾸면 끝.
DEFAULT_PRICES = {
    TIER_AMBIENT: (0.0003, 0.0006),
    TIER_DECISIVE: (0.003, 0.015),
}


@dataclass
class TierStat:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class CostMeter:
    """provider 래퍼. respond를 위임하면서 호출 비용을 누적한다."""

    provider: ModelProvider
    prices: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(DEFAULT_PRICES))
    stats: dict[str, TierStat] = field(default_factory=dict)

    def respond(self, prompt: str, agent_id: str, tier: str) -> ModelResponse:
        resp = self.provider.respond(prompt, agent_id)
        self.record(tier, resp.prompt_tokens, resp.completion_tokens)
        return resp

    def record(self, tier: str, prompt_tokens: int, completion_tokens: int) -> None:
        s = self.stats.setdefault(tier, TierStat())
        s.calls += 1
        s.prompt_tokens += prompt_tokens
        s.completion_tokens += completion_tokens

    def tier_cost(self, tier: str) -> float:
        s = self.stats.get(tier)
        if not s:
            return 0.0
        in_price, out_price = self.prices.get(tier, (0.0, 0.0))
        return (s.prompt_tokens / 1000.0) * in_price + (s.completion_tokens / 1000.0) * out_price

    def session_cost(self) -> float:
        return round(sum(self.tier_cost(t) for t in self.stats), 6)

    def total_calls(self) -> int:
        return sum(s.calls for s in self.stats.values())

    def summary(self) -> str:
        rows = []
        for tier, s in sorted(self.stats.items()):
            rows.append(
                f"  {tier:9s} calls={s.calls:4d} in={s.prompt_tokens:6d} "
                f"out={s.completion_tokens:5d} ${self.tier_cost(tier):.4f}"
            )
        rows.append(f"  TOTAL    ${self.session_cost():.4f}")
        return "\n".join(rows)
