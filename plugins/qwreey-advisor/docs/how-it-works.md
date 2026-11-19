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
| SessionStart(startup·resume·clear·compact), UserPromptSubmit | `ambient.py` | `context/ambient.md`(자기 점검 한 줄과 "Reviews: do them unasked" 두 줄: 언제 검토하나, 시작한 검토·요청받은 검토를 어떻게 보고하나, 내장 advisor 도구는 사용자가 요청할 때만)를 `<plugin name="qwreey-advisor">` 로 감싸 싣는다. 메인 세션에만(SubagentStart 를 등록하지 않는다: 검토 시점과 보고는 메인의 일). UserPromptSubmit 은 SessionStart 가 안 돈 세션(세션 중간에 켬)의 보충으로 (세션, compact 회차)당 한 번 |
| PreCompact(manual·auto) | `compact_epoch.py`, `ambient.py PreCompact` | 이 플러그인의 compact 회차를 올리고, 요약기에게 다시 실릴 블록을 요약에서 빼라는 한 줄을 낸다 |
| PreToolUse(Bash·Write·Edit·MultiEdit·NotebookEdit·mcp__.*) | `readonly-for-reviewers.py` → `auditor-readonly-guard.py` | 입력의 `agent_type` 이 리뷰어일 때만 읽기 전용 가드를 건다 |
| PreToolUse(Bash·ExitPlanMode), PostToolUseFailure, SubagentStop(모든 에이전트), UserPromptSubmit, PostToolBatch, Stop | `second-opinion-nudge.py` (+ `commit_scope.py`, `review_record.py`, `handback_notice.py`) | 검토 시점 알림, 검토 기록, 서브에이전트 보고 알림(아래) |
| PreToolUse(Agent·Task) | `expand-inherit-prompt.py`, `track-reviewer.py` | fork 표지 펼치기, 리뷰어 호출 표시 |

`hooks/ambient.py` 은 저장소 `lib/ambient.py` 의 바이트 사본이다(고치지 말고 정본을 고친 뒤 `python3 -I tools/sync-copies.py --apply`). 플러그인마다 다른 것은 `context/ambient.json`(`plugin`, `events`, `off_switch`, `epoch`)에 둔다. 끄기: `HARNESS_QWREEY_ADVISOR_AMBIENT=off`(환경 변수 또는 harness.env).

플러그인 에이전트는 frontmatter 의 `hooks`·`permissionMode`·`mcpServers` 를 무시한다. 그래서 가드는 에이전트 파일이 아니라 `hooks/hooks.json` 에 걸고 `agent_type` 으로 리뷰어만 고른다.

## 검토 시점 알림 (`second-opinion-nudge.py`)
막지 않는다(ExitPlanMode 의 `deny` 설정 제외). 서브에이전트 안(`agent_id` 있음)에서는 SubagentStop 기록 말고는 아무것도 하지 않는다. 메시지는 영어 `<harness-hook name="qwreey-advisor" level="warn">`(보고 알림만 `info`).
- 같은 실패 두 번(PostToolUseFailure): 도구 이름과 오류 첫 줄(숫자는 `#` 로)로 서명을 만들고, 이번 회차에 같은 서명이 두 번째면 stuck 검토를 권한다. 사용자 중단과 `grep`·`test`·`diff`·`which` 같은 확인 명령의 실패는 세지 않는다.
- 커밋 직전(PreToolUse Bash, `git commit`): 커밋될 diff 의 추가+삭제 줄이 등급 임계 이상이면 done 검토를 권한다. PreToolUse 는 명령이 돌기 전이라, 같은 명령이 스테이징하는 범위는 `commit_scope.py` 가 명령을 읽어 더한다.
  - `git add <경로>`(`git stage` 포함): 지금 index(`--cached`) + `git diff HEAD -- <경로>` + 그 경로 아래 추적 안 된 파일의 줄 수(`.gitignore` 존중, 바이너리 0).
  - `git add -A`·`git add .`(현재 폴더 기준)·`git commit -a`: `git diff HEAD` 전체(+ `-A`·`.` 는 추적 안 된 파일). `git add -u` 는 추적 파일만.
  - `git commit <경로>`: 그 경로의 `git diff HEAD`. `cd <폴더> &&`, `git -C <폴더>`, `;`·`&&`·`|`·줄바꿈, `2>&1` 같은 리다이렉트, `-m "$(cat <<EOF ...)"` 를 읽는다. 다른 저장소에 커밋하면 그 저장소의 등급을 쓴다.
  - 읽지 못하는 명령(따옴표 오류, 경로에 `$VAR`·명령 치환, `add -p`·`-i`·`-e`, `--pathspec-from-file`)은 예전처럼 `--cached`(커밋에 `-a` 면 `HEAD`)로 잰다. `--dry-run` 커밋은 건너뛴다. git 호출은 rev-parse 1회와 diff·ls-files 최대 3회.
- 턴 끝(Stop, 기본 켜짐, `HARNESS_REVIEW_STOP=off` 로 끔): 커밋 안 된 diff(`git diff HEAD`)가 임계 이상일 때 같은 알림. Stop 의 additionalContext 는 턴을 이어 가게 하므로 `home/.claude/HOOK-MESSAGES.md` 의 Stop 규칙을 따른다: `stop_hook_active` 재진입, 빈 답, 오류·한도 알림(`API Error`, `Prompt is too long` 등), 끝 다섯 줄 안에 `?` 로 끝나는 줄이 있는 답(사용자에게 묻는 중)이면 내지 않는다. 같은 diff 로 턴이 다시 끝나도 아래 조건(diff 해시를 회차당 한 번, 알림 뒤 쿨다운)이 막고, 상태를 쓰지 못하면 알림도 내지 않는다.
- 계획 종료(ExitPlanMode, 기본 `warn`): high 등급에서만. 계획에 `qwreey-advisor: reviewed`(또는 `skip <사유>`) 줄이 없을 때 `warn` 은 권하기만 하고, `HARNESS_REVIEW_PLAN=deny` 면 거절한다. deny 는 계획 모드를 막으므로 저장소가 켠다.
- 다시 울리지 않는 조건: 메인이 부른 검토(리뷰어 또는 inherit-advisor fork)가 `HARNESS_REVIEW_FRESH_MIN` 분 안에 끝났을 때, 같은 diff 해시를 이번 회차에 이미 알렸을 때, done 알림 뒤 같은 시간 동안.
- 알림이 권하는 리뷰어 모델: high 는 opus, mid·low 는 sonnet.
- 저장소 이름은 git common dir 의 부모 폴더 이름이라 worktree 안에서도 본 저장소로 센다. git 저장소가 아니면 아무것도 하지 않는다(보고 알림은 기본 등급으로 낸다).
- 검토로 치는 것(`review_record.py`, SubagentStop): `qwreey-advisor:reviewer`, 그리고 `agent_type` 이 `fork` 이고 transcript 앞부분에 표지(`[qwreey-advisor:inherit]` 또는 펼친 뒤의 `[second opinion: inherit]`)가 있는 것. fork transcript 는 부모 대화를 복사하지 않아 앞 64KB 만 읽는다. 호출자는 transcript 옆 `agent-<id>.meta.json` 의 `parentAgentId`(또는 `spawnDepth` > 1)가 있으면 subagent, 리뷰어는 run 줄도 본다.

### 서브에이전트 보고 알림 (`handback_notice.py`)
검토가 아닌 서브에이전트가 돌려준 보고에 권고·선택지·열린 질문이 있으면 메인에게 `info` 한 줄을 낸다: 사용자에게 넘겨 결정하게 할 거라면 그 안은 그 에이전트 혼자 확인한 것이고, inherit-advisor(추론)나 fresh-advisor(틀)가 먼저 볼 수 있다. 직접 확인한 사실이나 그대로 전하는 질문이면 건너뛰어도 된다고 적는다. 보고마다 한 번(이어 받은 에이전트가 다른 보고를 내면 다시 본다, 내용 해시로 구분). 토론 입장문(설명이 `debate` 나 `토론` 으로 시작, qwreey-debate 스킬이 `debate:` 로 붙인다)은 메인이 종합할 재료라 내지 않는다. 토큰 간격 리마인더는 두지 않았다: 이 사건 알림으로 먼저 써 보고 빈틈이 보이면 다시 본다.
- 전달 경로(실측, claude 2.1.316, haiku 탐침): SubagentStop 이 보고가 메인에 들어가기 전에 돈다. 입력의 `last_assistant_message` 와, SubagentHandback 으로 끝낸 에이전트는 transcript 끝 512KB 의 마지막 SubagentHandback 입력을 분류해 `<session>.handbacks.json` 에 남긴다. 메인이 띄운 것(meta 의 `spawnDepth` 1, `parentAgentId` 없음)만 대기로 둔다.
  - 메인이 쉬고 있으면 보고가 새 턴으로 들어오고 UserPromptSubmit 의 `prompt` 에 그 글(`<task-notification>` 의 `<result>`, 또는 `<agent-message from="<id>">` 의 `[Subagent hand-back]`)이 실린다. 이 경로는 prompt 를 직접 분류하므로 SubagentStop 기록이 없어도 된다. SubagentHandback 을 쓴 에이전트의 task-notification 은 본문 대신 안내만 실어 그때는 상태를 쓴다.
  - 메인이 일하는 중이면 보고가 다음 도구 결과와 함께 붙고 UserPromptSubmit 이 돌지 않는다. 메인의 PostToolBatch 가 대기 중인 것을 한 줄로 묶어 낸다.
- 내지 않는 경우: 검토 자신의 보고(run 줄·표지 포함), 보고 뒤에 메인이 부른 검토가 끝났을 때, 같은 묶음에서 메인이 리뷰어나 inherit-advisor fork 를 띄웠을 때, `HARNESS_REVIEW_HANDBACK=off`, off 등급 저장소, 서브에이전트 안.
- 분류(기계적): 제목 줄(마크다운 제목, 목록 기호가 붙을 수 있는 줄 전체 굵게, 콜론으로 끝나는 짧은 줄)에 Recommendation(s)·Proposal·Open questions·Questions for the user·To decide·권고·추천·제안·선택지·사용자 결정·미결·열린 질문 같은 말이 하나 있거나, 본문 문구(`I recommend`, `your call`, `do you want`, `Recommendation:`, 권합니다·사용자 결정이 필요·어느 쪽을 등)·`Q1`/`Option A` 줄 둘 이상 중 신호가 둘 이상이면 낸다. 코드 블록은 보지 않는다. `Design choices`·`Open points` 같은 구현 보고의 제목에는 걸리지 않는다.
- 재생(이 저장소의 한 세션 transcript, 메인에 온 서브에이전트 보고 252건, 에이전트 217개): 검토 3개는 0건, 검토가 아닌 에이전트 214개 중 51개(24%)에서 한 번씩 났다. 대부분 설계안·조사·토론 입장이고, 사용자에게 결정을 넘기는 "Open questions ... each with my recommendation" 보고가 포함된다.

### 설정
설정 층(사용자 `~/.claude/harness.env`, `$CLAUDE_CONFIG_DIR` 가 있으면 그 아래 < 플러그인 옵션(`/config`, `settings.json` 의 `pluginConfigs`, `plugin.json` `userConfig` 에 둔 네 키) < 저장소 `.claude/harness.env` < 저장소 `.claude/harness.local.env`)과 환경 변수에서 읽고, 환경 변수가 이긴다. 저장소는 `$CLAUDE_PROJECT_DIR`, 없으면 훅 `cwd`. 읽기는 옆의 `hooks/harness_env.py` 사본(하네스 로더의 사본). 파일이 없으면 환경 변수와 기본값만 쓴다.

| 키 | 기본 | 뜻 |
|---|---|---|
| `HARNESS_REVIEW_TIERS` | 없음 | `저장소=high\|mid\|low\|off` 를 공백으로 나열 |
| `HARNESS_REVIEW_DEFAULT` | `mid` | 목록에 없는 저장소의 등급(옵션 `harness_review_default`) |
| `HARNESS_REVIEW_LINES` | `high=40 mid=200 low=0` | done 알림 임계(추가+삭제 줄, 0 은 끔) |
| `HARNESS_REVIEW_FRESH_MIN` | `90` | 최근 검토로 치는 시간(분) |
| `HARNESS_REVIEW_STOP` | `on` | `on`(또는 `1`) 이면 Stop 알림을 낸다. `off` 로 끈다(옵션 `harness_review_stop`) |
| `HARNESS_REVIEW_PLAN` | `warn` | high 등급 계획 검토. `warn` 은 권고, `deny` 는 거절, `off` 는 끔(옵션 `harness_review_plan`) |
| `HARNESS_REVIEW_HANDBACK` | `on` | `off` 면 서브에이전트 보고 알림을 끈다(옵션 `harness_review_handback`) |
| `HARNESS_QWREEY_ADVISOR_AMBIENT` | `on` | `off` 면 규약 주입을 끈다(옵션 `harness_qwreey_advisor_ambient`) |

`off` 등급은 알림만 멈춘다. 스킬은 여전히 부를 수 있다(inherit-advisor 는 off 저장소에서 사용자가 요청할 때만 부르라고 적혀 있다).

### 상태
- dedup: `$TMPDIR/claude-second-opinion/` 아래 (세션, compact 회차) 단위 파일. 회차는 이 플러그인 자기 것(`hooks/compact_epoch.py`, PreCompact 가 올린다).
- 최근 검토 시각: 같은 폴더의 `<session>.last-review`. compact 를 넘어 유지한다.
- 서브에이전트 보고: 같은 폴더의 `<session>.handbacks.json`(에이전트별 시각·설명·분류·알림 여부, 3일 지나면 지움, `.lock` 으로 잠금). compact 를 넘어 유지한다(에이전트마다 한 번).
- 상태 경로, 훅 파일 이름, `HARNESS_REVIEW_*` 에 남은 `second-opinion` 은 기존 기록이 이어지도록 그대로 둔 이름이다.

## 리뷰어 호출 표시 (`track-reviewer.py`)
`qwreey-advisor:reviewer` 를 부를 때마다 uuid 를 만들고 `/tmp/claude-audit/<uuid>/` 를 스크래치로 만든 뒤, prompt 끝에 `[qwreey-advisor run: <uuid> caller=<main|subagent> scratch=...]` 한 줄을 붙인다(`updatedInput`). 호출자는 입력에 `agent_id` 가 있으면 subagent 다. SubagentStop 에서 nudge 가 리뷰어 transcript 의 첫 user 메시지에서 이 줄을 읽어, 메인이 부른 리뷰어만 "최근 검토" 로 기록한다. transcript 옆 meta.json 이 서브에이전트가 띄웠다고 하면 그것도 subagent 로 친다. 둘 다 없거나 읽지 못하면 main 으로 친다. 스크래치 위치는 `CLAUDE_AUDIT_SCRATCH` 로 바꾼다.

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
- `review-ledger.py add|stats`: 검토마다 종류, 리뷰어, 호출자, 트리거, 판정, 발견·채택 수를 `${XDG_STATE_HOME:-~/.local/state}/claude-second-opinion/ledger.jsonl` 에 덧붙인다. `stats` 는 트리거·리뷰어별 채택률과 미기록 수를 보인다. 채택률이 낮은 트리거는 임계를 올리거나 끈다.
  - 자동 행: 리뷰어나 inherit-advisor fork 가 끝나면 SubagentStop 이 `auto_add` 로 판정 `미기록`, `auto: true`, `ref: agent-<id>` 인 행을 남긴다(kind 는 리뷰어 description `second opinion: <kind>` 나 `inherit`, reviewer 는 meta 의 model 로 `opus-sub`·`sonnet-sub` 나 `fork`). 메인이 add 를 잊어도 사용 횟수가 보이게 하려는 것이다.
  - 겹침: 나중에 `add` 가 같은 검토를 적으면 그 행에 `supersedes: <자동 행 ref>` 를 적는다. `--ref agent-<id>` 가 맞으면 그 행, 아니면 같은 세션(`CLAUDE_CODE_SESSION_ID`)에서 검토자 계열(fork 또는 `*-sub`)이 같고 아직 짝이 없는 가장 최근 자동 행(6시간 안). `stats` 는 짝이 생긴 자동 행을 세지 않는다. append 만 하므로 옛 행을 고치지 않고, 여러 세션이 같이 써도 안전하다. 같은 계열 검토 둘을 한 세션에서 연달아 돌리고 add 를 한 번만 하면 나중 것과 짝지어진다(앞 것은 미기록으로 남는다).
- `advisor-stats.py --all`: 내장 advisor 호출 수와 비용.
- `user-asks.py`: 트랜스크립트에서 사용자 원문 추출(브리프의 미답 질문용).

## 한계
- 같은 작업 트리를 여러 세션이 쓰면 diff 계산이 세션을 가르지 못해, 남의 변경으로 알림이 울리거나 다시 울릴 수 있다. 브리프의 "Files I changed" 가 리뷰어의 범위를 정하고, 목록 밖 변경은 발견이 아니라 맥락으로 다룬다.
- 보고 알림의 분류는 낱말 휴리스틱이라 제목 없이 산문으로 권하는 보고는 놓치고, 토론 입장처럼 메인이 종합할 중간 보고에도 난다. 메인이 일하는 중이면 PostToolBatch 알림이 보고와 같은 다음 요청에 실리는데, 둘의 순서는 보장하지 않는다(알림이 에이전트 설명을 적는다).
- 같은 호출에 PreToolUse 훅 둘이 `updatedInput` 을 낼 때의 병합은 공식 문서에 없다. `expand-inherit-prompt.py` 는 fork 에만, `track-reviewer.py` 는 리뷰어에만 걸려 겹치지 않는다.

## 플랫폼
훅은 표준 라이브러리 Python 3 과 `git` 을 쓴다. 스크래치와 가드는 `/tmp/claude-audit/` 를 전제로 한다.

## 테스트
```bash
python3 -I plugins/qwreey-advisor/tests/test-second-opinion-nudge.py   # 알림, 한 명령의 add+commit 범위. 임시 HOME 과 git 저장소, 하네스 lib 있음·없음 둘 다
python3 -I plugins/qwreey-advisor/tests/test-track-reviewer.py         # run 줄, SubagentStop 호출자 판별(run 줄, meta), fork 검토, ledger 자동 행과 짝짓기
python3 -I plugins/qwreey-advisor/tests/test-handback-notice.py       # 보고 분류, SubagentStop -> UserPromptSubmit·PostToolBatch 알림, 건너뛰는 경우
python3 -I plugins/qwreey-advisor/tests/test-readonly-for-reviewers.py # 리뷰어에게만 가드가 걸리는지
python3 -I plugins/qwreey-advisor/tests/test-expand-inherit-prompt.py  # fork 표지 펼치기
python3 -I plugins/qwreey-advisor/tests/test-ambient.py                # 규약 주입, PreCompact 한 줄
```
모델을 부르지 않는다.
