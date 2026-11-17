# q

사람이 직접 치는 명령을 `/q:` 아래에 모은 플러그인이다. `/q:` 만 치면 자동완성에 전부 나온다. 처음 쓰는 사람을 위한 온보딩, 저장소의 Claude 설정 진단, 자리를 비울 때 쓸 예산 걸어 두기가 들어 있다. 여기에 평소 돌아가는 안전장치 몇 가지가 붙는다. 서브에이전트를 한꺼번에 많이 띄우기 전에 규모를 알리게 하고, 멈춘 듯한 백그라운드 작업과 낡은 플러그인 설치를 알려 준다. 평소에는 아무것도 막지 않는다. 막는 것은 `/q:away` 로 예산을 걸었을 때뿐이고, 진단과 온보딩은 사용자가 동의한 것만 고친다. 이름 q 는 만든 사람(qwreey)에서 왔다.

## 무엇이 달라지나
- `/q:start`: 역할과 경험을 묻고, 모르는 개념만 쉽게 설명한 뒤, 지금 환경을 읽기만 해서 진단하고 개선안을 하나씩 제안한다. 동의한 것만 적용한다.
- `/q:doctor`: 저장소의 CLAUDE.md, rules, 스킬, 설정, 훅을 진단하고 고칠 점을 제안한다. 항목마다 승인한 것만 고친다.
- `/q:away 30%` 처럼 예산을 걸고 자리를 비우면 동시 서브에이전트가 정한 수(기본 2)로 묶이고, 예산만큼 쓴 뒤로는 서브에이전트를 하나씩만 돌리고, 두 배를 쓰면 새 서브에이전트를 멈추고 진행 상황을 적은 뒤 기다린다. 돌아와서 `/q:back` 하면 그동안 쓴 양을 요약한다.
- 평소 Claude 가 서브에이전트를 한꺼번에 많이 띄우려 하면(동시 4개 이상, opus 2개 이상, Workflow) 먼저 몇 개를 어떤 모델로 돌리는지 알린다.
- 백그라운드 작업이 15분 넘게 진척 없거나 2시간 넘게 돌면 화면에 한 줄로 알려 준다. 세션을 열 때 설치된 플러그인이 마켓보다 낡았으면 업데이트 명령을 한 줄로 보여 준다(하루 한 번).
- 다른 플러그인의 훅 알림을 Claude 가 어떻게 다룰지(info, warn, action) 짧은 규약을 싣는다.

## 비용
- 늘 드는 것: 훅 알림 규약 두 줄(약 120 토큰)이 메인과 서브에이전트마다 실린다. 명령은 사용자 전용이라 설명이 맥락에 실리지 않는다. 훅은 모델을 부르지 않는다.
- `/q:start`, `/q:doctor` 는 실행할 때 보통 대화만큼 든다.

## 요구 사항
- `python3`. Linux·macOS·Windows(Windows 는 claude-doctor README 의 Windows 절).
- 구독 한도 %로 예산을 걸려면 claude-doctor 의 statusline 이 한도 값을 기록해야 한다. 없으면 달러 기준으로 바뀐다.

## 설정
`/plugin configure q@claude-doctor-market` 또는 `/config` 에서 고른다. 모두 기본 켜짐이다.
- 서브에이전트 고지와 자리 비움 슬롯(`harness_subagent_slots`): 끄면 규모 알림과 `/q:away` 제한이 모두 멈춘다.
- 설치 어긋남 알림(`harness_q_drift`)
- 방치된 백그라운드 작업 알림(`harness_q_stale`)

고급: 문턱과 예산 기본값, 규약 끄기(`HARNESS_Q_AMBIENT=off`)는 `~/.claude/harness.env` 나 저장소 `.claude/harness.env` 에 둔다([docs/how-it-works.md](docs/how-it-works.md)).

전부 끄기: `claude plugin disable q@claude-doctor-market` (제거는 `uninstall`).

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install q@claude-doctor-market
```

자세한 동작(훅 구성, 알림 조건과 설정, away 단계, 테스트): [docs/how-it-works.md](docs/how-it-works.md). 온보딩 구성: [docs/onboarding.md](docs/onboarding.md)
