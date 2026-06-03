# AG-World

외부/내장 AI 에이전트를 아바타로, 작은 월드에서 자율적으로 사회생활하게 만들고
유저는 **관전**하다 **귓속말**로 개입하는 소셜 시뮬. '하는 게임'이 아니라 '보는 게임'.

이 저장소는 **콘솔 v1**입니다. 설계 문서대로 LLM 없이 엔진부터 검증하는 단계.

## 빠르게 보기

```bash
python3 -m agworld --ticks 8              # 8틱 자동 재생
python3 -m agworld --live                 # 실시간 관전(10초마다 틱, 아무 때나 귓속말)
python3 -m agworld --live --interval 3    # 틱 간격 조절
python3 -m agworld --interactive          # 매 틱 소나에게 귓속말(턴제)
python3 -m agworld --snapshot s.json      # 슬립/웨이크 (자고 깨면 이어감)
```

`--live`는 터미널(TTY)에서: 틱이 타이머로 흐르고, 보면서 아무 때나 소나에게 속삭이면
다음 차례에 반영돼요. `q`로 나가면 캐릭터들도 잠듭니다(슬립 온 디스커넥트).

3명(루리·단·소나)이 시나리오 없이 떠들고, 감정이 무대에 이모지로 뜨고, 키워드/관계/귓속말이
⚡결정적 순간을 만든다. `소나`가 내 에이전트(★).

## 설계 원칙

- **LLM은 포트 뒤로.** `ModelProvider` 인터페이스. v1은 `FakeProvider`(결정론적 캐닝)로
  엔진을 100% 테스트. 실제 LLM(EXAONE 로컬 / Haiku급 클라우드)은 같은 인터페이스로 나중에.
  "마법이 안 터지면" 원인이 엔진 버그인지 모델 품질인지 분리된다.
- **슬립 온 디스커넥트.** 관전자가 볼 때만 세계가 돈다. 안 보면 캐릭터도 잔다(틱 0).
  자는 동안 아무 일도 안 일어나므로 리플레이 없음, 비용 캡이 정의상 완벽.
- **무대엔 감정 이모지만, 말은 피드에서** (The Sims 방식). 라이브 다자 대화를 로그 스팸이
  아니라 읽히는 드라마로.
- **비용:** 틱 + 2계층 모델(앰비언트=싼/순간=비싼) + 롤링 윈도우(최근 8턴) 컨텍스트.
  `CostMeter`가 토큰을 계측. 앰비언트를 로컬 모델로 돌리면 비용 ≈ 0.

## 구조

```
agworld/
  models.py       Emotion(7-enum) · Agent · Turn · Utterance · Tick
  providers.py    ModelProvider 포트 + FakeProvider (실패주입 포함)
  context.py      롤링 윈도우 트리밍 + 프롬프트 빌더(귓속말=격리 힌트)
  moments.py      결정적 순간 판정(규칙기반: 귓속말/관계델타/키워드)
  whisper.py      귓속말 큐(큐잉/레이트리밋/새니타이즈)
  cost.py         CostMeter(티어별 토큰·비용 계측)
  scheduler.py    TickScheduler(슬립 온 디스커넥트) + SpeakerSelector(라운드로빈)
  persistence.py  스냅샷 저장/복원(원자적, 틱 리플레이 없음)
  sim.py          World — 한 틱 조립 파이프라인
  console.py      관전 화면 렌더(무대 이모지 + 피드)
  cli.py          데모 엔트리포인트
```

## 테스트

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

의존성 0 (stdlib만). 78개 테스트, 엔진 전 경로 결정론적 커버.

## 배포 (Render 무료)

런타임 의존성 0이라 배포가 간단하다. `render.yaml` 블루프린트가 포함돼 있다.

1. 이 저장소를 GitHub에 푸시.
2. [Render](https://render.com) → **New > Blueprint** → 저장소 선택.
3. Render가 `render.yaml`을 읽어 자동 구성. 시작 명령:
   `python -m agworld --web --host 0.0.0.0 --port $PORT --interval 6`
4. 배포되면 `https://agworld-xxxx.onrender.com` 링크로 접속.

주의:
- 무료 플랜은 **15분 유휴 시 슬립** → 다음 접속 때 콜드스타트(~30초). 재시작 시 메모리 월드가 리셋된다(스냅샷은 임시 파일시스템이라 영속 안 됨).
- `http.server`는 개발용 서버다. 데모/소규모엔 충분하지만 트래픽이 커지면 WSGI/ASGI로 교체 필요.
- 현재 World는 **전역 1개** — 접속자 전원이 같은 방을 본다(유저별 세션은 미구현).
- 슬립 없는 상시 무료가 필요하면 Oracle Cloud Always Free(VM 직접 관리) 또는 Fly.io 고려.

## 다음

- 실제 `ModelProvider` 구현(로컬 EXAONE/Ollama, 클라우드).
- 2.5D 아이소메트릭 뷰어(설계 문서의 관전 화면 섹션 참고).
- 자세한 설계: `~/.gstack/projects/AGWorld/j-unknown-design-20260603-223739.md`
- 연기된 일: `TODOS.md`
