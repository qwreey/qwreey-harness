# q 플러그인

사람이 직접 치는 하네스 명령을 한 접두(`/q:`)로 모은 플러그인이다. `/q:` 만 치면 자동완성에 전부 나온다. 이름 q 는 사용자명 qwreey 에서 왔다.
모델이 부르는 것은 `qwreey-advisor`, 툴킷 지식은 `luau-kb` 플러그인에 따로 있다. 세션 기록(`/qwreey-sessions:checkpoint`·`import`·`recall`)은 `qwreey-sessions`, 다른 저장소 게이트와 지도(`qwreey-workspace:workspace`)는 `qwreey-workspace` 로 나뉘어 각각 고를 수 있다.

| 명령 | 무엇 | 자세히 |
|---|---|---|
| `/q:start` | 온보딩(묻기, 개념 설명, 읽기 전용 진단, 동의받은 개선만 적용) | `docs/onboarding.md` |
| `/q:doctor` | 하네스 진단(결정적 검사 `scan.py` + 모델 판단) | `skills/doctor/SKILL.md` |
| `/q:away`, `/q:back` | 자리 비움 예산·슬롯. 상태는 `scripts/subagent_ledger.py`(원장)와 `scripts/subagent-slots.py`(훅)가 맡는다 | `.claude/audit/21-cost-disclosure.md` |

- 훅(`hooks/hooks.json`): 상시 규약 주입(`ambient.py`), 서브에이전트 고지·슬롯(`subagent-slots.py`), 설치 어긋남 고지(`drift.py`, SessionStart: 켠 플러그인의 설치 버전이 마켓보다 낮거나 claude-doctor 에서 `home-sync.sh status` 가 어긋남을 보이면 사용자에게 한 줄, 같은 내용은 하루 한 번, 끄기 `HARNESS_Q_DRIFT=off`), 오래 방치된 백그라운드 작업 알림(`stale_work.py`, Stop·SubagentStop 이 판정하고 UserPromptSubmit 이 모델에, Stop 이 사용자에게 전달, 끄기 `HARNESS_Q_STALE=off`). PreCompact 에서 q 자기 compact 회차(`scripts/compact_epoch.py`, 정본)를 올리고, `ambient.py PreCompact` 가 요약기에게 compact 뒤 다시 실릴 `<plugin name="q">` 블록을 요약에서 빼라는 한 줄을 낸다(끄기는 주입과 같은 `HARNESS_Q_AMBIENT=off`).
- away/back 은 이 플러그인의 `scripts/subagent_ledger.py` 를 부른다. statusline(`~/.claude/statusline/harness-status.py`)은 `installed_plugins.json` 에서 설치된 q 를 찾아 그 원장을 읽고, q 가 없으면 서브에이전트·away 항목만 뺀다.
- doctor 가 정본 검사를 하려면 `HARNESS_DOCTOR_ROOT`(`~/.claude/harness.env`)가 claude-doctor 폴더를 가리켜야 한다.
- 설치: `claude plugin install q@claude-doctor-market`.
- 테스트: `plugins/q/tests/` 의 `test_*.py`, `test-subagent-slots.py`.
