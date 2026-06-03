"""AG-World — 자율 에이전트 관전형 소셜 월드 (콘솔 v1).

설계: ~/.gstack/projects/AGWorld/j-unknown-design-20260603-223739.md

핵심 원칙:
- LLM은 ModelProvider 포트 뒤로. v1은 FakeProvider(결정론적)로 엔진 검증.
- 슬립 온 디스커넥트: 관전자가 볼 때만 세계가 돈다. 안 보면 캐릭터도 잔다(틱 0).
- 무대엔 감정 이모지만, 말은 피드에서 (The Sims 방식).
- 비용: 틱 + 2계층 모델 + 롤링 윈도우 컨텍스트.
"""

__version__ = "0.1.0"
