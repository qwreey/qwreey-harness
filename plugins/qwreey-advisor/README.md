# qwreey-advisor

모델이 스스로 집어 드는 독립 검토. 근거와 실측은 claude-doctor `audit/18-second-opinion.md` §9·§11·§12. 스킬별 설계 근거는 `docs/rationale-<스킬>.md`(유지보수자용, 모델이 읽지 않는다).

| 구성 | 이름 | 하는 일 |
|---|---|---|
| 스킬 | `qwreey-advisor:inherit-advisor` | 대화를 이어받은 fork 를 "독립 검토자"로 돌려 세워, 흐름에서 놓친 것·숨은 전제·방금 끝낸 설계의 반례를 묻는다. 결론·결정을 말하기 전, 끝났다고 보고 넘어가기 전. 메인은 표지만 보내고 훅이 후행 프롬프트로 펼친다. 1회 약 $0.5~0.6(30만 토큰 맥락, opus) |
| 스킬 | `qwreey-advisor:fresh-advisor` | 새 컨텍스트 리뷰어에게 짧은 브리프만 주고 diff·주장을 반증하게 한다. 커밋·완료 전, 같은 실패 2회, 구현 검증. opus 약 $1, sonnet 약 $0.4 |
| 에이전트 | `qwreey-advisor:reviewer` | fresh-advisor 의 읽기 전용 리뷰어(기본 opus, 호출 때 model 로 낮춘다) |
| 훅 | `hooks/second-opinion-nudge.py` | 같은 실패 2회, 임계 이상 커밋(기본 high 40줄·mid 200줄)에서 검토를 권한다. 막지 않는다. 서브에이전트 안에서는 조용하다 |
| 훅 | `hooks/expand-inherit-prompt.py` | PreToolUse(Agent). fork 호출의 표지 prompt 를 `templates/fork-prompt.md` 원문으로 바꾼다(`updatedInput` + allow). 표지가 아니면 통과 |
| 훅 | `hooks/readonly-for-reviewers.py` | 리뷰어 에이전트에게만 읽기 전용 가드(`auditor-readonly-guard.py`)를 건다 |

이 스킬들은 내장 `advisor` 도구를 부르지 않는다. 내장 advisor 도구는 가격 대비 효용이 diff 기반 리뷰보다 낮아 사용자가 요청할 때만 쓴다.

## 설치

```bash
claude plugin marketplace add /code/Projects/claude-doctor   # claude-doctor-market
claude plugin install qwreey-advisor@claude-doctor-market
```

훅은 설치하는 순간부터 모든 세션에서 돈다(플러그인 훅은 스킬 사용과 무관하게 등록된다).

## 설정 (선택)

훅과 스킬은 claude-doctor 하네스의 `~/.claude/harness.env` 와 `~/.claude/lib/` 를 쓴다(`$CLAUDE_CONFIG_DIR` 가 있으면 그 아래). 없으면 기본값으로 돈다.

| 키 | 기본 | 뜻 |
|---|---|---|
| `HARNESS_REVIEW_TIERS` | 없음 | `저장소=high|mid|low|off` 목록. 저장소 이름은 git common dir 의 부모 이름 |
| `HARNESS_REVIEW_DEFAULT` | `mid` | 목록에 없는 저장소의 등급 |
| `HARNESS_REVIEW_LINES` | `high=40 mid=200 low=0` | done 알림 임계(추가+삭제 줄, 0 = 끔) |
| `HARNESS_REVIEW_FRESH_MIN` | `90` | 이 시간(분) 안에 리뷰어가 끝났으면 다시 알리지 않는다 |
| `HARNESS_REVIEW_STOP` | 빈 값 | `1` 이면 커밋 안 된 큰 diff 로 턴을 끝낼 때도 알린다 |
| `HARNESS_REVIEW_PLAN` | 빈 값 | `deny`·`warn` 이면 high 등급 ExitPlanMode 에서 계획 검토를 요구한다 |

- dedup 상태는 `$TMPDIR/claude-second-opinion/` 에 (세션, compact 회차) 단위로 둔다. 회차는 이 플러그인 자기 것(`hooks/compact_epoch.py`, PreCompact 훅이 올림)이라 하네스 lib 없이도 돈다.
- 원장은 `${XDG_STATE_HOME:-~/.local/state}/claude-second-opinion/ledger.jsonl`.
- 상태 경로와 훅 파일 이름에 옛 이름 `second-opinion` 이 남은 이유: 플러그인 이름이 `qwreey-advisor` 로 바뀌어도 기존 원장·dedup 기록이 이어지도록 경로는 그대로 둔다. 환경 변수 `HARNESS_REVIEW_*` 도 그대로다.

## 알아 둘 것

- 리뷰어 호출마다 PreToolUse 훅(`hooks/track-reviewer.py`)이 uuid 를 만들고 `/tmp/claude-audit/<uuid>/` 를 스크래치로 준비해, prompt 끝에 `[qwreey-advisor run: <uuid> caller=<main|subagent> scratch=...]` 한 줄을 붙인다. 읽기 전용 가드는 가드가 run 폴더를 알 수 없으므로 `/tmp/claude-audit/` 아래 경로를 허용하고 그 밖은 막는다(목적은 저장소 보호이지 리뷰어끼리 격리가 아니다).
- '최근 검토'(커밋 알림을 끄는 기록)는 메인이 부른 리뷰어만 센다. 일꾼 서브에이전트가 띄운 리뷰어는 세지 않는다. 호출자 판별은 `docs/rationale-fresh-advisor.md`.
- 같은 작업 트리를 여러 세션이 쓰면 알림의 diff 계산은 세션을 가르지 못한다(`docs/rationale-fresh-advisor.md`). 브리프의 "Files I changed" 가 리뷰어의 범위를 정한다.
- 플러그인 에이전트는 frontmatter 의 `hooks`·`permissionMode`·`mcpServers` 를 무시한다. 그래서 읽기 전용 가드는 에이전트 파일이 아니라 플러그인 `hooks/hooks.json` 의 PreToolUse 에 있고, 입력의 `agent_type` 으로 이 플러그인의 검토자만 고른다.
- fork 는 메인과 같은 모델로만 돈다. 메인이 방금 응답한 직후(캐시가 따뜻할 때) 부른다. 캐시가 식었으면 맥락 전체를 다시 써서 30만 토큰에서 opus 약 $1.5 가 더 든다.
- 모델이 스스로 부른 검토는 메인이 발견을 확인해 받아들임/버림을 1~3줄로 알리고, 사용자가 요청한 검토는 보고 전문을 한국어로 보인다.

## 테스트

```bash
python3 -I tests/test-second-opinion-nudge.py        # 훅 알림(claude-doctor 정본 home/.claude/lib 를 복사해 쓴다)
python3 -I tests/test-readonly-for-reviewers.py      # 검토자 읽기 전용 가드 선택
python3 -I tests/test-expand-inherit-prompt.py       # fork 표지 펼침 훅
```
