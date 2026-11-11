# q 플러그인

사람이 직접 치는 하네스 명령을 한 접두(`/q:`)로 모은 플러그인이다. `/q:` 만 치면 자동완성에 전부 나온다. 이름 q 는 사용자명 qwreey 에서 왔다.
모델이 부르는 것은 `qwreey-advisor`, 툴킷 지식은 `luau-kb` 플러그인에 따로 있다.

| 명령 | 무엇 | 자세히 |
|---|---|---|
| `/q:start` | 온보딩(묻기, 개념 설명, 읽기 전용 진단, 동의받은 개선만 적용) | `docs/onboarding.md` |
| `/q:doctor` | 하네스 진단(결정적 검사 `scan.py` + 모델 판단) | `skills/doctor/SKILL.md` |
| `/q:away`, `/q:back` | 자리 비움 예산·슬롯. 상태는 `scripts/subagent_ledger.py`(원장)와 `scripts/subagent-slots.py`(훅)가 맡는다 | `audit/21-cost-disclosure.md` |
| `/q:checkpoint`, `/q:import`, `/q:recall` | 세션 기록 즉시 저장, 저장소로 한 줄 복사, 옛 논의 찾기(서브에이전트) | `docs/session-log.md` |

- 훅(`hooks/hooks.json`): session-log, 상시 규약 주입(`ambient.py`), 형제 저장소 게이트(`workspace_gate.py`), 서브에이전트 고지·슬롯(`subagent-slots.py`), 기록을 읽을 때의 스냅샷 안내(`records_read.py`, PostToolUse Read·Grep). 설치 어긋남 고지(`drift.py`, SessionStart: 켠 플러그인의 설치 버전이 마켓보다 낮거나 claude-doctor 에서 `home-sync.sh status` 가 어긋남을 보이면 사용자에게 한 줄, 같은 내용은 하루 한 번, 끄기 `HARNESS_Q_DRIFT=off`), 오래 방치된 백그라운드 작업 알림(`stale_work.py`, Stop·SubagentStop 이 판정하고 UserPromptSubmit 이 모델에, Stop 이 사용자에게 전달, 끄기 `HARNESS_Q_STALE=off`)도 있다. PreCompact 에서 q 자기 compact 회차를 올린다. 저장 위치는 `~/.local/share/session-log/` 로 플러그인 이름과 무관하다(`CLAUDE_PLUGIN_DATA` 를 쓰지 않는다).
- away/back 은 이 플러그인의 `scripts/subagent_ledger.py` 를 부른다. statusline(`~/.claude/statusline/harness-status.py`)은 `installed_plugins.json` 에서 설치된 q 를 찾아 그 원장을 읽고, q 가 없으면 서브에이전트·away 항목만 뺀다.
- doctor 가 정본 검사를 하려면 `HARNESS_DOCTOR_ROOT`(`~/.claude/harness.env`)가 claude-doctor 폴더를 가리켜야 한다.
- 설치: `claude plugin install q@claude-doctor-market`.
- 테스트: `python3 -I plugins/q/tests/test_session_log.py`, `plugins/q/tests/e2e.sh`.
