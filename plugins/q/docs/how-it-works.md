# q 동작 상세

구성: 사용자 전용 스킬 넷(`start`, `doctor`, `away`, `back`, 모두 `disable-model-invocation: true`라 모델이 스스로 부르지 않고 설명도 맥락에 실리지 않는다)과 훅(`hooks/hooks.json`). 스킬별 절차는 각 `skills/*/SKILL.md`, 온보딩 구성은 [onboarding.md](onboarding.md).

## 훅
| 이벤트(matcher) | 스크립트 | 하는 일 |
|---|---|---|
| SessionStart(startup·resume·clear·compact), SubagentStart, UserPromptSubmit | `scripts/ambient.py` | 규약 주입(아래) |
| SessionStart(startup·resume·clear) | `scripts/drift.py` | 설치 어긋남 고지 |
| PreToolUse(Agent·Workflow), PostToolUse(모든 도구), SubagentStart, SubagentStop, Stop | `scripts/subagent-slots.py` | 서브에이전트 규모 고지, away 슬롯·예산 |
| Stop, SubagentStop, UserPromptSubmit | `scripts/stale_work.py` | 방치된 백그라운드 작업 알림 |
| PreCompact(manual·auto) | `scripts/compact_epoch.py q`, `scripts/ambient.py PreCompact` | q 의 compact 회차를 올리고, 다시 실릴 `<plugin name="q">` 블록을 요약에서 빼라는 한 줄을 낸다 |

모든 훅은 모델을 부르지 않고, 실패하면 조용히 통과한다.

## 규약 주입 (`ambient.py`)
- `context/ambient.md`(훅 알림의 위상과 info·warn·action 의 뜻, `~/.claude` 는 claude-doctor `home/` 에서 고친다는 줄, mise shim 우회 줄. 영어 다섯 줄)를 `<plugin name="q" nonce="…">` 로 감싸 `additionalContext` 로 낸다. 다른 플러그인의 훅 메시지는 이 배경을 전제로 쓰인다(`home/.claude/HOOK-MESSAGES.md`).
- SessionStart 는 메인에, SubagentStart 는 서브에이전트에 싣는다. fork 는 부모 맥락을 물려받으므로 건너뛴다.
- UserPromptSubmit 은 세션 중간에 플러그인을 켠 경우의 보충으로, (세션, compact 회차)당 한 번만 싣는다.
- 끄기: `HARNESS_Q_AMBIENT=off`(환경 변수 또는 harness.env 층: 사용자 `~/.claude/harness.env` < 저장소 `.claude/harness.env` < 저장소 `.claude/harness.local.env`. 층 규칙은 `home/.claude/lib/harness_env.py` 머리, 플러그인은 늘 옆의 `scripts/harness_env.py` 사본을 쓴다).
- `scripts/ambient.py` 은 저장소 `lib/ambient.py` 의 바이트 사본이다(고치지 말고 정본을 고친 뒤 `python3 -I tools/sync-copies.py --apply`). 플러그인마다 다른 것은 `context/ambient.json`(`plugin`, `events`, `off_switch`, `epoch`)에 둔다. 서브에이전트에 다른 글을 실으려면 `context/subagent.md` 를 둔다(없으면 `ambient.md`).

## 서브에이전트 규모 고지와 away (`subagent-slots.py`, 원장 `subagent_ledger.py`)
- 평소(attended): 막지 않는다. 이 호출로 동시 실행이 `HARNESS_FANOUT_WARN_CONCURRENT`(기본 4)개 이상, opus 이상이 `HARNESS_FANOUT_WARN_BIG`(기본 2)개 이상, 또는 Workflow 호출(`HARNESS_FANOUT_WARN_WORKFLOW=on`)이면 "사용자에게 규모를 알리라" 는 warn 을 낸다. 팬아웃 한 묶음(실행 중 0 에서 다시 0 이 될 때까지)과 compact 회차마다 한 번.
- away(`/q:away` 로 선언): 실행 중 수가 슬롯(기본 2) 이상이면 새 Agent 를 `deny`(`queue: …`, level=action). 예산을 넘으면(1단계) 슬롯을 `HARNESS_AWAY_OVER_SLOTS`(기본 1)로 줄이고 재고 알림을 한 번 준다. 예산의 `HARNESS_AWAY_STAGE2_MULT`(기본 2)배를 넘으면(2단계) 새 Agent·Workflow 를 모두 거절하고 진척을 파일에 적은 뒤 사용자를 기다리게 한다. 메인 세션 자체는 끊지 않는다. 메인이 서브에이전트 없이 일해도 PostToolUse 에서 같은 안내를 한 번 받는다.
- 예산 단위: 구독 한도 %(statusline 이 쓰는 `<sid>.limits.json` 을 읽는다), USD(트랜스크립트 usage 를 API 목록가로 환산), 에이전트 수. `HARNESS_AWAY_PLAN=auto|usd|pct`. 한도 값이 `HARNESS_AWAY_LIMITS_STALE_MIN`(기본 10분) 넘게 갱신되지 않으면 USD 로 바꾼다. away 중 Workflow 는 `HARNESS_AWAY_WORKFLOW`(기본 `idle`: 실행 중 0 일 때만).
- 세는 법: PreToolUse 에서 예약(+1), PostToolUse(`async_launched`)·SubagentStart 에서 실행 중, SubagentStop 에서 −1. 어긋나면 `background_tasks`, 트랜스크립트 mtime, 예약 TTL 로 복구하고, 수동으로는 `/q:away reset`.
- 평소에는 PostToolUse 마다 상태 파일의 `away.on` 만 보고 끝난다(원장 모듈을 읽지 않는다).
- 상태: `$TMPDIR/claude-subagent-slots/<sid>.json`. 설정 우선순위: 환경 변수 > 저장소 `.claude/harness.local.env` > 저장소 `.claude/harness.env` > `~/.claude/harness.env` > 기본값(`subagent_ledger.py` 의 `CFG_DEFAULTS`). 원장은 자기 키(`HARNESS_SUBAGENT_`·`HARNESS_FANOUT_`·`HARNESS_AWAY_`·`HARNESS_SLOTS_` 접두)만 낸다. 저장소 층이 실행 경로 같은 하네스 값을 바꾸지 못하게 하는 것은 로더의 `USER_ONLY` 다.
- claude-doctor 의 statusline 은 설치된 q 의 원장을 읽어 away 상태와 서브에이전트 수를 보인다. q 가 없으면 그 항목만 뺀다.
- 끄기: `HARNESS_SUBAGENT_SLOTS=off`.

## 방치된 작업 알림 (`stale_work.py`)
- 출처: Stop·SubagentStop 입력의 `background_tasks`(type 은 subagent, workflow, shell 등. monitor 는 뺀다). 시작 시각이 없어 나이는 이 훅이 처음 본 때부터 센다. 진척 신호는 출력 파일의 크기와 mtime 이다: 서브에이전트는 트랜스크립트, 셸 등은 Claude Code 가 쓰는 `<tmp>/claude-<uid>/<프로젝트 키>/<sid>/tasks/<id>.output`(프로젝트 키는 트랜스크립트가 있는 디렉터리 이름, tmp 는 `CLAUDE_CODE_TMPDIR`, 훅의 `TMPDIR`, `/tmp` 순으로 찾는다). 신호가 없는 작업(workflow 등)은 멈춤 판정을 하지 않는다.
- 멈춤: 진척 없이 `HARNESS_Q_STALE_IDLE_MIN`(15)분 이상이고 나이 `HARNESS_Q_STALE_AGE_MIN`(30)분 이상. 오래 실행: 나이 `HARNESS_Q_STALE_LONG_MIN`(120)분 이상.
- 전달: Stop(메인)이 사용자에게 `systemMessage` 한 줄, 다음 UserPromptSubmit 이 모델에 `additionalContext`. 문구는 "멈췄거나 대기 중일 수 있음" 같은 질문형이다. 두 상태 모두 끝난 일에 딸린 작업이나 조건을 기다리며 도는 루프면 명령과 출력을 보고 멈추거나(TaskStop) 사용자에게 알리라고 권하고, 오래 실행 문구는 그 밖이면 사용자에게 한 줄 알리라고 한다. 셸 등은 출력 파일 경로를 함께 싣는다. (세션, 작업, 상태)마다 한 번.
- 상태: `$TMPDIR/claude-q-stale/<sid>.json`. 끄기: `HARNESS_Q_STALE=off`(환경 변수).

## 설치 어긋남 고지 (`drift.py`)
- SessionStart 에서 사용자에게만 한 줄(`systemMessage`)을 보인다. 모델에는 주지 않는다.
- 플러그인: 켜 둔 마켓 플러그인의 설치 버전이 마켓의 `plugin.json` 버전보다 낮으면 `claude plugin update <name>@<market>` 을 보인다. 원격 마켓은 로컬 사본이 `marketplace update` 될 때까지의 비교다.
- home: 저장소 루트에 `tools/home-sync.sh` 가 있으면(claude-doctor) `home-sync.sh status` 를 돌려 어긋남을 한 줄로.
- 같은 내용은 하루 한 번(바뀌면 바로). compact 로 다시 시작한 세션은 건너뛴다. 상태: `$TMPDIR/claude-q-drift/state.json`. 끄기: `HARNESS_Q_DRIFT=off`(환경 변수).

## /q:doctor
결정적 검사(`skills/doctor/scripts/scan.py` 와 `scan_*.py`, 기록 규약 검사 `scripts/records_check.py`, 팩 검사 `pack_checks.py`)를 돌리고 모델이 판단을 더한다. claude-doctor 정본과 비교하려면 `HARNESS_DOCTOR_ROOT`(`~/.claude/harness.env`)가 claude-doctor 폴더를 가리켜야 한다. 툴킷별 검사는 `skills/doctor/references/toolkits/`.

## 플랫폼
훅은 표준 라이브러리 Python 3 이다. 원장(`subagent_ledger.py`)이 `fcntl` 잠금을 써서 away 와 규모 고지는 Linux·macOS 에서만 돈다(Windows 에서는 훅이 조용히 통과한다).

## 테스트
```bash
python3 -I plugins/q/tests/test-subagent-slots.py
python3 -I plugins/q/tests/test_ambient.py
python3 -I plugins/q/tests/test_notices.py          # drift, stale_work
python3 -I plugins/q/tests/test_stale_work.py       # stale_work: 셸 출력 파일 신호와 문구
python3 -I plugins/q/tests/test_compact_epoch.py
python3 -I plugins/q/tests/test_harness_nonce.py
python3 -I plugins/q/tests/test_records_check.py
python3 -I plugins/q/tests/test_pack_checks.py
python3 -I plugins/q/skills/doctor/tests/test-memory-checks.py
```
모델을 부르지 않는다.
