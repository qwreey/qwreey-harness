# qwreey-advisor 동작 상세

구성: 스킬 둘(`qwreey-advisor:inherit-advisor`, `qwreey-advisor:fresh-advisor`), 리뷰어 에이전트 하나(`qwreey-advisor:reviewer`), 훅 다섯 개(`hooks/hooks.json`). 모델이 따르는 절차는 각 `skills/*/SKILL.md` 와 `agents/reviewer.md` 에 있고, 여기서는 사람이 알아야 할 구조를 정리한다. 설계 근거와 비용 실측은 `rationale-fresh-advisor.md`, `rationale-inherit-advisor.md`.

## 두 검토
| | inherit-advisor | fresh-advisor |
|---|---|---|
| 누가 | 대화를 이어받은 fork(`subagent_type="fork"`). 메인과 같은 모델로만 돈다 | 새 컨텍스트의 `qwreey-advisor:reviewer`(기본 opus, 호출 때 `model` 로 정한다) |
| 무엇을 | 흐름에서 놓친 것, 숨은 전제, 방금 끝낸 설계의 반례 | diff 와 "끝났다, 된다, 안전하다" 는 주장을 사용자 원문과 파일에 대조해 반증 |
| 입력 | 짧은 표지. 훅이 `skills/inherit-advisor/templates/fork-prompt.md` 원문으로 펼친다 | `skills/fresh-advisor/templates/brief.md` 꼴의 5~15줄 브리프 |
| 비용 | 1회 약 $0.5~0.6(30만 토큰 맥락, opus, 캐시가 따뜻할 때). 캐시가 식었으면 맥락을 다시 써서 약 $1.5 더 | opus 약 $1, sonnet 약 $0.4, 2~3분 |

둘 다 결과는 영어 보고서로 메인에게 온다. 메인이 스스로 부른 검토는 발견마다 확인해 받아들임·버림을 사용자에게 1~3줄로 알리고, 사용자가 요청한 검토는 보고 전문을 한국어로 보인다. 내장 `advisor` 도구는 쓰지 않는다.

## 훅
| 이벤트(matcher) | 스크립트 | 하는 일 |
|---|---|---|
| SessionStart(startup·resume·clear·compact), UserPromptSubmit | `ambient.py` | `context/ambient.md` 한 줄을 `<plugin name="qwreey-advisor">` 로 감싸 싣는다. 메인 세션에만. UserPromptSubmit 은 SessionStart 가 안 돈 세션(세션 중간에 켬)의 보충으로 (세션, compact 회차)당 한 번 |
| PreCompact(manual·auto) | `compact_epoch.py`, `ambient.py PreCompact` | 이 플러그인의 compact 회차를 올리고, 요약기에게 다시 실릴 블록을 요약에서 빼라는 한 줄을 낸다 |
| PreToolUse(Bash·Write·Edit·MultiEdit·NotebookEdit·mcp__.*) | `readonly-for-reviewers.py` → `auditor-readonly-guard.py` | 입력의 `agent_type` 이 리뷰어일 때만 읽기 전용 가드를 건다 |
| PreToolUse(Bash·ExitPlanMode), PostToolUseFailure, SubagentStop(리뷰어), Stop | `second-opinion-nudge.py` | 검토 시점 알림(아래) |
| PreToolUse(Agent·Task) | `expand-inherit-prompt.py`, `track-reviewer.py` | fork 표지 펼치기, 리뷰어 호출 표시 |

`hooks/ambient.py` 은 저장소 `lib/ambient.py` 의 바이트 사본이다(고치지 말고 정본을 고친 뒤 `python3 -I tools/sync-copies.py --apply`). 플러그인마다 다른 것은 `context/ambient.json`(`plugin`, `events`, `off_switch`, `epoch`)에 둔다. 끄기: `HARNESS_QWREEY_ADVISOR_AMBIENT=off`(환경 변수 또는 harness.env).

플러그인 에이전트는 frontmatter 의 `hooks`·`permissionMode`·`mcpServers` 를 무시한다. 그래서 가드는 에이전트 파일이 아니라 `hooks/hooks.json` 에 걸고 `agent_type` 으로 리뷰어만 고른다.

## 검토 시점 알림 (`second-opinion-nudge.py`)
막지 않는다(ExitPlanMode 의 `deny` 설정 제외). 서브에이전트 안(`agent_id` 있음)에서는 SubagentStop 기록 말고는 아무것도 하지 않는다. 메시지는 영어 `<harness-hook name="qwreey-advisor" level="warn">`.
- 같은 실패 두 번(PostToolUseFailure): 도구 이름과 오류 첫 줄(숫자는 `#` 로)로 서명을 만들고, 이번 회차에 같은 서명이 두 번째면 stuck 검토를 권한다. 사용자 중단과 `grep`·`test`·`diff`·`which` 같은 확인 명령의 실패는 세지 않는다.
- 커밋 직전(PreToolUse Bash, `git commit`): 커밋될 diff(`-a` 면 `git diff HEAD`, 아니면 `--cached`)의 추가+삭제 줄이 등급 임계 이상이면 done 검토를 권한다.
- 턴 끝(Stop, 기본 꺼짐): `HARNESS_REVIEW_STOP=1` 이면 커밋 안 된 diff 가 임계 이상일 때 같은 알림.
- 계획 종료(ExitPlanMode, 기본 꺼짐): high 등급에서 `HARNESS_REVIEW_PLAN=deny` 면 계획에 `qwreey-advisor: reviewed`(또는 `skip <사유>`) 줄이 없을 때 거절하고, `warn` 이면 권하기만 한다.
- 다시 울리지 않는 조건: 메인이 부른 리뷰어가 `HARNESS_REVIEW_FRESH_MIN` 분 안에 끝났을 때, 같은 diff 해시를 이번 회차에 이미 알렸을 때, done 알림 뒤 같은 시간 동안.
- 알림이 권하는 리뷰어 모델: high 는 opus, mid·low 는 sonnet.
- 저장소 이름은 git common dir 의 부모 폴더 이름이라 worktree 안에서도 본 저장소로 센다. git 저장소가 아니면 아무것도 하지 않는다.

### 설정
`~/.claude/harness.env`(`$CLAUDE_CONFIG_DIR` 가 있으면 그 아래, 읽기는 하네스의 `lib/harness_env.py`)와 환경 변수에서 읽고, 환경 변수가 이긴다. 하네스가 없으면 환경 변수와 기본값만 쓴다.

| 키 | 기본 | 뜻 |
|---|---|---|
| `HARNESS_REVIEW_TIERS` | 없음 | `저장소=high\|mid\|low\|off` 를 공백으로 나열 |
| `HARNESS_REVIEW_DEFAULT` | `mid` | 목록에 없는 저장소의 등급 |
| `HARNESS_REVIEW_LINES` | `high=40 mid=200 low=0` | done 알림 임계(추가+삭제 줄, 0 은 끔) |
| `HARNESS_REVIEW_FRESH_MIN` | `90` | 최근 검토로 치는 시간(분) |
| `HARNESS_REVIEW_STOP` | 빈 값 | `1` 이면 Stop 알림을 켠다 |
| `HARNESS_REVIEW_PLAN` | 빈 값 | `deny` 또는 `warn` 이면 high 등급 계획 검토를 켠다 |
| `HARNESS_QWREEY_ADVISOR_AMBIENT` | 빈 값 | `off` 면 규약 주입을 끈다 |

`off` 등급은 알림만 멈춘다. 스킬은 여전히 부를 수 있다(inherit-advisor 는 off 저장소에서 사용자가 요청할 때만 부르라고 적혀 있다).

### 상태
- dedup: `$TMPDIR/claude-second-opinion/` 아래 (세션, compact 회차) 단위 파일. 회차는 이 플러그인 자기 것(`hooks/compact_epoch.py`, PreCompact 가 올린다).
- 최근 검토 시각: 같은 폴더의 `<session>.last-review`. compact 를 넘어 유지한다.
- 상태 경로, 훅 파일 이름, `HARNESS_REVIEW_*` 에 남은 `second-opinion` 은 기존 기록이 이어지도록 그대로 둔 이름이다.

## 리뷰어 호출 표시 (`track-reviewer.py`)
`qwreey-advisor:reviewer` 를 부를 때마다 uuid 를 만들고 `/tmp/claude-audit/<uuid>/` 를 스크래치로 만든 뒤, prompt 끝에 `[qwreey-advisor run: <uuid> caller=<main|subagent> scratch=...]` 한 줄을 붙인다(`updatedInput`). 호출자는 입력에 `agent_id` 가 있으면 subagent 다. SubagentStop 에서 nudge 가 리뷰어 transcript 의 첫 user 메시지에서 이 줄을 읽어, 메인이 부른 리뷰어만 "최근 검토" 로 기록한다. 줄이 없거나 읽지 못하면 main 으로 친다. 스크래치 위치는 `CLAUDE_AUDIT_SCRATCH` 로 바꾼다.

## 읽기 전용 가드 (`auditor-readonly-guard.py`)
리뷰어에게만 걸린다. 종료 코드 2 로 막고 사유를 리뷰어에게 돌려준다.
- Write·Edit·MultiEdit·NotebookEdit: `/tmp/claude-audit/<아무 폴더>/` 밖이면 거절. 가드는 리뷰어의 run 폴더를 알 수 없어 그 아래 전체를 허용한다. 목적은 저장소 보호이지 리뷰어끼리 격리가 아니다.
- Bash: `rm`·`mv`·`cp`·`tee`·`sed -i` 같은 쓰기 명령의 경로와 `>`·`>>` 대상이 스크래치나 `/dev/null` 밖이면 거절. 읽기용(`status`·`diff`·`log`·`show` 등)이 아닌 git 하위 명령, 네트워크(`curl`·`ssh` 등), 패키지·툴체인 변경(`npm`·`pip`·`cargo`·`mise install` 등), `sudo`, `rojo` 거절.
- `mcp__roblox-studio__*`: 전부 거절(여러 세션이 같이 쓰고 상태를 바꾼다).
- 한계: `bash x.sh`, `python3 -c`, `luau probe.luau` 안에서 일어나는 쓰기는 보지 못한다.

## fork 표지 펼치기 (`expand-inherit-prompt.py`)
`subagent_type == "fork"` 이고 prompt 가 `[qwreey-advisor:inherit]` 로 시작할 때만, `next:` 줄과 `options:`(현재 `reqs`)를 읽어 `templates/fork-prompt.md`(reqs 면 `fork-prompt-reqs.md` 를 더해)로 바꾼다. `updatedInput` 은 `permissionDecision: "allow"` 와 함께 보낸다(없으면 auto 모드가 바뀐 호출을 거절할 수 있다). 템플릿이 없거나 형식이 틀리면 그대로 통과시키며, 표지 자체가 "검토만, 작업·편집·커밋 금지" 라 fork 가 작업을 이어 하지 않는다.

## 검토 기록과 통계
`skills/fresh-advisor/scripts/`:
- `review-ledger.py add|stats`: 검토마다 종류, 리뷰어, 호출자, 트리거, 판정, 발견·채택 수를 `${XDG_STATE_HOME:-~/.local/state}/claude-second-opinion/ledger.jsonl` 에 덧붙인다. `stats` 는 트리거·리뷰어별 채택률을 보인다. 채택률이 낮은 트리거는 임계를 올리거나 끈다.
- `advisor-stats.py --all`: 내장 advisor 호출 수와 비용.
- `user-asks.py`: 트랜스크립트에서 사용자 원문 추출(브리프의 미답 질문용).

## 한계
- 같은 작업 트리를 여러 세션이 쓰면 diff 계산이 세션을 가르지 못해, 남의 변경으로 알림이 울리거나 다시 울릴 수 있다. 브리프의 "Files I changed" 가 리뷰어의 범위를 정하고, 목록 밖 변경은 발견이 아니라 맥락으로 다룬다.
- 같은 호출에 PreToolUse 훅 둘이 `updatedInput` 을 낼 때의 병합은 공식 문서에 없다. `expand-inherit-prompt.py` 는 fork 에만, `track-reviewer.py` 는 리뷰어에만 걸려 겹치지 않는다.

## 플랫폼
훅은 표준 라이브러리 Python 3 과 `git` 을 쓴다. 스크래치와 가드는 `/tmp/claude-audit/` 를 전제로 한다.

## 테스트
```bash
python3 -I plugins/qwreey-advisor/tests/test-second-opinion-nudge.py   # 알림. 임시 HOME 과 git 저장소, 하네스 lib 있음·없음 둘 다
python3 -I plugins/qwreey-advisor/tests/test-track-reviewer.py         # run 줄, SubagentStop 호출자 판별, ledger --caller
python3 -I plugins/qwreey-advisor/tests/test-readonly-for-reviewers.py # 리뷰어에게만 가드가 걸리는지
python3 -I plugins/qwreey-advisor/tests/test-expand-inherit-prompt.py  # fork 표지 펼치기
python3 -I plugins/qwreey-advisor/tests/test-ambient.py                # 규약 주입, PreCompact 한 줄
```
모델을 부르지 않는다.
