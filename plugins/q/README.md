# q 플러그인

사람이 직접 치는 하네스 명령을 한 접두(`/q:`)로 모은 플러그인이다. `/q:` 만 치면 자동완성에 전부 나온다. 이름 q 는 사용자명 qwreey 에서 왔다.
모델이 부르는 것은 `qwreey-advisor`, 툴킷 지식은 `luau-kb` 플러그인에 따로 있다.

| 명령 | 무엇 | 자세히 |
|---|---|---|
| `/q:start` | 온보딩(묻기, 개념 설명, 읽기 전용 진단, 동의받은 개선만 적용) | `docs/onboarding.md` |
| `/q:doctor` | 하네스 진단(결정적 검사 `scan.py` + 모델 판단) | `skills/doctor/SKILL.md` |
| `/q:away`, `/q:back` | 자리 비움 예산·슬롯. 상태는 사용자 레벨 `~/.claude/lib/subagent_ledger.py` 와 `hooks/subagent-slots.py` 가 맡는다 | `audit/21-cost-disclosure.md` |
| `/q:checkpoint`, `/q:import` | 세션 기록 즉시 저장, 저장소로 받아 가기 | `docs/session-log.md` |

- 훅(`hooks/hooks.json`)은 session-log 만이다. 저장 위치는 `~/.local/share/session-log/` 로 플러그인 이름과 무관하다(`CLAUDE_PLUGIN_DATA` 를 쓰지 않는다).
- away/back 은 `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/subagent_ledger.py` 를 부른다. 사용자 레벨 정본(`home/.claude`)을 먼저 apply 해야 한다.
- doctor 가 정본 검사를 하려면 `HARNESS_DOCTOR_ROOT`(`~/.claude/harness.env`)가 claude-doctor 폴더를 가리켜야 한다.
- 설치: `claude plugin install q@claude-doctor-market`.
- 테스트: `python3 -I plugins/q/tests/test_session_log.py`, `plugins/q/tests/e2e.sh`.
