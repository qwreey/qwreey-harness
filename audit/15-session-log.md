# 15. 세션 기록 자동화 — remember 조사, 환경 실측, 요약 품질 실측

> 작성 2026-11-10. 설계는 `drafts/session-log/DESIGN.md`, 프로토타입 스크립트는 `drafts/session-log/`.
> 배경(사용자 발언 2026-11-10): 에이전트가 세션 로그를 자주 빠뜨린다. 메인 세션이 직접 남기면 컨텍스트가 썩고, 느리고, 일부를 빠뜨리거나 아예 안 한다. 그래서 `~/.claude` 에서 찾아오는 일도 있다.
> 실제 사례: tbox 세션 5b53c2ca 첫 발언 "우리가 뭘 하고 있었는지 알겠어? 세션 트렌스크립트가 없어서"(L4).
> 관련 패턴: `audit/10` §2.1. compact 준비를 손으로 한 횟수가 64/9/4, `/compact` 58회다.
> 실측 환경: Claude Code 2.1.316. 요약 모델은 claude-sonnet-5-5 와 claude-haiku-5-5(CLI 별칭 `sonnet`, `haiku`).

## 1. remember 플러그인 (Digital-Process-Tools/claude-remember)

v0.45.1, 커밋 2fd0547(2026-11-07). `/tmp/remember-src.*/repo` 에 클론해 읽기만 했다. 크기는 셸 약 24.5k줄, 파이썬 약 5.5k줄, 테스트 파일 약 300개다.

| 항목 | remember 의 방식 |
|---|---|
| 훅 | SessionStart(기억 주입, 놓친 세션 복구), UserPromptSubmit(시각과 컨텍스트 % 주입), PostToolUse(증분 저장 트리거), SessionEnd(강제 flush). **PreCompact 는 쓰지 않는다** |
| 트랜스크립트 읽기 | 훅 stdin 의 `transcript_path` 를 그대로 쓴다(#407). 경로를 다시 만들지 않는다. 위치는 **줄 번호**로 세션별 `last-save.json` 에 둔다. `user`/`assistant` 의 text 와 tool_use 한 줄 요약만 남긴다. tool_result, thinking, isMeta, system-reminder 는 버린다. 입력 상한 300KB이고, 넘으면 **뒤쪽만** 남긴다 |
| 트리거 | PostToolUse 에서 지난 저장 뒤로 줄이 50줄 넘게 늘었고 쿨다운 120초가 지났으면 `nohup save-session.sh &`. 사람 발언이 3개 미만이면 건너뛴다(에이전트 교환이 30개를 넘으면 저장). SessionEnd 는 이 관문을 건너뛴다 |
| 요약 프롬프트 | `## HH:MM \| branch` 머리 + **한 문장**. 대화 언어로 쓴다. 약어로 줄인다(conf, impl…). "막힘·대기" 상태는 지우지 않는다. 직전 항목과 같거나 실질 작업이 없으면 `SKIP` |
| 통합 | now.md(버퍼) →(1시간마다 NDC 압축) today-*.md →(일별 2~4문장) recent.md →(3일 넘으면 주별 3~5문장) archive.md. recent 600토큰, archive 400토큰 상한. 넘치면 날짜 붙은 조각 파일로 회전한다 |
| 잠금 | `mkdir` 디렉터리 잠금 + `mv` 로 stale 인수(1,354줄짜리 lib-lock.sh). 읽는 쪽은 잠그지 않는다. 쓰기는 모두 같은 디렉터리의 임시 파일 + rename |
| 저장 | 기본은 `<project>/.remember/`(gitignore). 외부 모드 `~/.remember/{slug}`. worktree 는 git common-dir 로 본 체크아웃에 모은다 |
| SessionStart 주입 | 합계 9,000바이트 예산(Claude Code 의 10,000자 미리보기 한도 아래). 우선순위는 handoff → now → recent → today → archive 순이다. 넘친 것은 이름과 크기만 알린다. `source=compact` 에서는 identity 만 넣고 나머지는 이름만 |
| 요약 호출 | `claude -p --model haiku --output-format json --no-session-persistence --tools "" --setting-sources "" --strict-mcp-config --max-turns 4`, 빈 임시 cwd, 부모 세션 환경 변수(CLAUDECODE, CLAUDE_CODE_*) 제거, `REMEMBER_NESTED_SUMMARIZER=1`(자기 훅 no-op). 동시 요약기 4개 상한 |
| 비용 | README: 저장 1회 < $0.01, 하루 몇 센트(haiku) |
| 실패 처리 | 실패해도 위치는 그대로 둬서 다음에 재시도한다. 연속 실패 3회 상한. `hook-errors.log` + `/remember:doctor`. **에코 거부**: 중첩 `claude -p` 의 stdout 이 프롬프트를 되풀이한 것(훅 차단 메시지 등, exit 0)이면 버린다. 이것을 놓쳐 기억 파일이 7겹으로 중첩 오염된 사고가 있었다(#202) |
| 라이선스 | **Community License(비 OSI)**. 개인·내부 사용과 수정은 허용한다. 재배포 판매와 **경쟁 제품 제작은 금지**한다 |

결론
- **가져올 것**(아이디어만. 코드는 라이선스 때문에 쓰지 않고 새로 짠다)
  - `transcript_path` 를 그대로 신뢰한다.
  - 세션별 위치를 기록하고 증분으로 읽는다.
  - 중첩 호출을 격리한다(`--tools ""`, `--setting-sources ""`, `--no-session-persistence`, 빈 cwd, 환경 변수 제거, 재귀 표지 변수).
  - SessionEnd 는 stdin 만 읽고 곧바로 detach 한다(1.5초 예산).
  - 쓰기는 임시 파일 + rename 으로 한다.
  - 에코 거부, 실패하면 위치를 그대로 둬 재시도, SessionStart 주입 바이트 예산, worktree 를 본 체크아웃으로 모으기, `source=compact` 에서 다시 주입하지 않기.
- **버릴 것**
  - 한 문장 요약과 약어 압축: 결정·숫자·사용자 원문이 사라진다. 우리 목표는 시간순 기록과 검증이다.
  - now/today/recent/archive 를 덮어써 가는 연쇄 재압축: 압축한 것을 다시 압축하면 오류가 쌓이고, 원본 대조가 끊긴다.
  - SessionStart 에 기억 전체 주입: 우리는 인계 몇 줄과 coderag 안내만 넣는다.
  - UserPromptSubmit 시각·% 주입: `audit/10` H1 훅의 몫이다.
  - git 백업, 프로모, identity, Codex/Gemini/Antigravity 호환 층.
  - mkdir 잠금 구현: 파이썬 `fcntl.flock` 이면 프로세스가 죽을 때 자동으로 풀린다.
  - 줄 번호 위치 대신 **바이트 오프셋**을 쓴다(큰 파일에서 다시 셀 필요가 없다).
  - 300KB 꼬리 절단 대신 **구간을 나눠 모두** 요약한다.

## 2. 우리 환경 사실

### 2.1 트랜스크립트 구조 (실측)
- 위치: `~/.claude/projects/<키>/<session>.jsonl`. 키는 시작 디렉터리 경로의 `/`·`.` 를 `-` 로 바꾼 것이다(`/tmp/sl-hookproj.omyV` → `-tmp-sl-hookproj-omyV`).
- 서브에이전트: `<키>/<session>/subagents/agent-<id>.jsonl` + `agent-<id>.meta.json`(`agentType`, `description`, `model`, worktree 면 `worktreePath`, `worktreeBranch`). 큰 출력은 `<session>/tool-results/`.
- 세션이 아주 길다. quad a406edbc 는 10-20 → 11-10(3주, 64.6MB, compact 13회)이고, stl-luau 1cb06079 는 compact 18회(auto 10, manual 8)다. 지금 남은 메인 트랜스크립트는 27개, 1.2GB다.
- 레코드 `type`(rbvm 25dd5ae4 표본): user, assistant, attachment, system, queue-operation, mode, permission-mode, ai-title, last-prompt, file-history-*, cost-state 등.
- 사람 발언은 세 곳에 있다.
  - `type:user` + `origin.kind:"human"` + `promptSource:"typed"`
  - 작업 중 큐에 넣은 발언: `attachment.type:"queued_command"` + `origin.kind:"human"` (tbox 에서 사람 발언 15개 중 2개)
  - AskUserQuestion 의 답: 해당 `tool_result`
- 서브에이전트 보고: `type:user`, `origin.kind:"peer"`, 본문은 `<agent-message …>[Subagent hand-back] … The report follows:` 다음에 들여쓴 보고. 다른 세션 메시지는 `<cross-session-message from-name=…>`.
- 백그라운드 완료 알림: `origin.kind:"task-notification"`. 잡음이다.
- compact
  - `system/compact_boundary` 의 `compactMetadata.trigger`(auto|manual), `preTokens`(예 967,749)
  - 바로 다음 `type:user` + `isCompactSummary:true` 가 요약 본문(tbox 예 19,464자)이다
  - **compact 뒤에도 앞 줄은 지워지지 않는다**(append-only). 그래서 바이트 오프셋은 compact 를 넘어도 유효하다.
- `system/away_summary`: Claude Code 가 스스로 만든 짧은 회고(rbvm 2건, tbox 13건).
- 부피: tbox 12.9MB 를 줄이면 219k자(1.7%)가 된다. tool_result 와 tool_use 입력이 각각 약 76만 자로 대부분을 차지한다. 27개 전체는 8.67M자, 75일 동안 하루 약 11.6만 자다.
- **보존 기간**: `cleanupPeriodDays` 기본 30일. 그보다 오래된 트랜스크립트는 세션 시작 때 **알림 없이 지워진다**. 우리 `settings.json` 에는 이 키가 없다(기본값). 원문 대조와 사후 복구가 가능한 기간이 30일뿐이다.

### 2.2 훅 입력 (문서 + 실측)
실측: 임시 프로젝트 `/tmp/sl-hookproj.omyV` 의 `.claude/settings.json` 에 8개 이벤트를 걸고 stdin 과 환경을 덤프했다(`drafts/session-log/probe/hook-dump.sh`). `claude -p --model sonnet` 실행 2회.

| 이벤트 | transcript_path | 그 밖의 필드(실측) |
|---|---|---|
| SessionStart | ✅ | `source`(startup·resume·compact·…), resume 이면 `seconds_since_last_response`, `context_tokens`, `prompt_cache_likely_expired`, `estimated_cache_write_usd`. compact 이면 `model` |
| UserPromptSubmit | ✅ | `prompt_id`, `prompt` |
| PostToolUse | ✅ | `tool_name`, `tool_input`, `tool_response`(전체 결과라 크다), `tool_use_id`, `duration_ms`, `permission_mode`, `effort` |
| Stop | ✅ | `last_assistant_message`, `stop_hook_active`, `background_tasks`, `session_crons` |
| **PreCompact** | ✅ | `trigger`(manual), `custom_instructions`("keep the word banana" — `/compact` 인자). **stdout 은 compact 요약 지시로 쓰인다**(≤10,000자). exit 2 면 compact 를 막는다 |
| **PostCompact** | ✅ | `trigger`, **`compact_summary`(compact 요약 전문)** |
| SubagentStop | ✅ + `agent_transcript_path` | compact 를 하는 내부 에이전트도 SubagentStop 을 일으킨다(`agent_type:""`). 그 transcript 파일은 남지 않았다 |
| SessionEnd | ✅ | `reason`(-p 종료는 `other`) |

- `-p` 에서 `/compact <인자>` 를 `--resume <id>` 로 넘기면 PreCompact → SubagentStop → SessionStart(compact) → PostCompact 순으로 실제로 돈다. **PreCompact 를 스크립트로 유도할 수 있다.** auto compact 는 문서상 같은 훅에 `trigger:"auto"` 로 온다(직접 유도하지는 않았다).
- 환경: 훅 프로세스에 `CLAUDE_PROJECT_DIR`(시작 디렉터리), `CLAUDE_CODE_SESSION_ID`, `CLAUDECODE=1` 이 있다. stdin 의 `cwd` 는 **현재** 디렉터리라 세션 중 `cd` 하면 바뀐다(quad 세션들의 cwd 에 `.claude/audit/…` 하위가 섞여 있다). 저장 위치는 `CLAUDE_PROJECT_DIR` 로 정해야 한다.
- 문서: `transcript_path` 는 비동기로 써져 **현재 턴의 마지막 메시지가 아직 없을 수 있다.** 마지막 줄이 덜 써졌을 수도 있다. 읽는 쪽은 `\n` 으로 끝난 줄까지만 처리하고 오프셋을 거기에 둔다.

### 2.3 동시 세션과 worktree
- 같은 저장소의 세션들은 같은 키 디렉터리를 쓴다. 세션 ID 로 갈린다. quad 58bd1a5b(10-20 04:59 ~ 10-21)와 a406edbc(10-20 16:36 ~ 11-10)는 시간이 겹친다. 그래서 **세션 ID 별 파일과 잠금**이 필요하다.
- 서브에이전트 worktree(`isolation: worktree`)는 부모 세션의 `subagents/` 에 기록된다. 그 레코드의 `cwd` 는 worktree 경로다.
- **worktree 에서 시작한 세션**은 별도 키를 받는다(실측: `-tmp-sl-hookproj-omyV--claude-worktrees-wt1`). `CLAUDE_PROJECT_DIR` 은 worktree 경로다. worktree 안 `.claude/session/` 에 쓰면 worktree 를 지울 때 같이 사라진다. 그래서 `git rev-parse --git-common-dir` 로 **본 체크아웃**의 `.claude/session/` 에 써야 한다.
- 이 머신에는 지금 worktree 에서 시작한 메인 세션 기록이 없다.

### 2.4 훅 시간 제한과 detach
- 기본 timeout 은 command 훅 600초다. PreCompact 는 동기라 훅이 오래 걸리면 compact 도 그만큼 늦어진다.
- **SessionEnd 는 모든 훅을 합쳐 1.5초 예산**이다. settings 의 per-hook `timeout` 으로 최대 60초까지 늘릴 수 있다. 단, **플러그인 훅의 timeout 은 예산을 늘리지 못한다.** 다른 방법은 `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` 다.
- `async: true`(command 훅): 기다리지 않는다. timeout 을 적용하지 않는다. `-p` 에서는 끝날 때 죽인다(문서: 오래 살아야 하면 완전히 분리된 프로세스를 띄우라).
- 실측: SessionEnd 훅에서 `( sleep 8; … ) &`(평범한 백그라운드)와 `setsid -f …`(새 세션) 둘 다 `claude -p` 가 끝난 뒤 살아남아 파일을 썼다. 대화형 종료에서도 그런지는 재지 않았다. 그래서 **`setsid -f` + stdin/stdout/stderr 를 `/dev/null` 로**(추가 fd 도 닫는다. remember #646 은 fd 3 이 새어 호출자가 93초를 기다린 사고다)를 기준으로 한다.
- 문서: 동기 훅이 출력을 리다이렉트하지 않은 백그라운드 자식을 남기면 Claude Code 가 출력을 계속 읽으며 기다리거나 `refusing to honor the suspect capture` 로 거부한다. 분리한 자식의 출력은 반드시 리다이렉트한다.

### 2.5 재귀 훅 방지 (실측)
훅이 걸린 임시 프로젝트 안에서 `claude -p "Say ok" --model sonnet --tools "" --no-session-persistence` 를 실행했다.

| 격리 방법 | 프로젝트 훅 발화 | 비용 | 입력 토큰(cache 생성+읽기) |
|---|---|---|---|
| (없음, 비교: 위 2.2 실행) | 5종 발화 | — | — |
| `--setting-sources ""` | 0 | $0.0087 | 2,791 |
| `--settings '{"disableAllHooks":true}'` | 0 | $0.0176 | 7,695 |

- `--setting-sources ""` 가 더 싸다. 사용자·프로젝트 설정(CLAUDE.md 를 뺀 설정 원천)을 읽지 않아 시스템 프롬프트가 작다. 그래도 구독 로그인(OAuth)으로 인증된다.
- `--bare` 는 구독 로그인을 쓰지 않는다(`ANTHROPIC_API_KEY` 필요). 이 머신에는 API 키 환경 변수가 없다.
- `--no-session-persistence` 면 요약 호출의 트랜스크립트가 남지 않는다(실측 확인). 요약 세션이 다시 요약 대상이 되지 않는다.
- managed 설정의 훅은 위 방법으로 끌 수 없다(문서). 그래서 재귀 표지 환경 변수 `SESSION_LOG_NESTED=1` 도 함께 둔다. 우리 훅은 이것을 보면 곧바로 끝낸다.

## 3. 요약 품질 실측 (sonnet 대 haiku)

### 3.1 방법
- 표본: 크기가 다른 실제 트랜스크립트 3개. 메인 세션 c9a9e895 는 뺐다.
  - S: quad b68ec805(0.8MB → 줄여 19.7k자). OOM 대책 훅, 사용자 정정 2회, 커밋 4개
  - M: vitrine 17914eac(7.8MB → 62.7k자). 새 프로젝트 설계·구현, AskUserQuestion 결정, 권한 버그
  - L: mrow aa399095(6.4MB → 154.7k자, 9만 자 단위로 나눠 2구간). 리뷰 보고서, 사람 발언 25개, 실측 수치 많음
- 파이프라인(`drafts/session-log/`)
  - `extract.py` 로 줄인다.
  - `summarize.py` 가 `prompt.md` 로 구간마다 `claude -p` 를 1회 호출한다. 도구 없음, `--setting-sources ""`, `--no-session-persistence`, 빈 cwd. 모델은 텍스트만 돌려주고 파일은 스크립트가 쓴다.
  - 요약 항목마다 근거 줄 `(L123)` 을 붙이게 했다.
- 두 모델 모두 같은 입력, 같은 프롬프트, 같은 대조 표본을 썼다. 출력은 `/tmp/sl-eval/out/` 에만 뒀다.
- 누락 검사: 원문에서 고른 결정·숫자·사용자 지시 표본 10개(아래 표)가 요약에 맞게 들어 있나 본다.
- 오류 검사는 세 겹으로 했다.
  1. `verify.py`(기계): 항목의 숫자·커밋 해시·사용자 인용이 근거 줄 본문에 글자 그대로 있나 본다.
  2. `verify_llm.py`(sonnet): 결정·수치·지시 항목을 근거 줄과 함께 주고 ok/wrong/unsupported 를 판정하게 한다. 이것이 혼합안의 둘째 단계다.
  3. 사람(이 에이전트) 손 검사: 결정 절 전부(S·M·L 두 모델)와 L 수치 무작위 6개를 원문과 맞춰 봤다.

### 3.2 대조 표본 10개

| # | 원문 | sonnet | haiku |
|---|---|---|---|
| S1 | `prlimit --data` 기본 3 GiB, 에이전트가 정함 (L139) | ✅ | ✅ |
| S2 | OOM 점수 자식 1332, claude 669 (L139) | ✅ | ✅ |
| S3 | 사용자 정정 "스왑은 의도에 없었어"(L200) → `memory-swap` 20g(L209) | ✅ | ✅ |
| M1 | 백엔드 Go(Node 거부), Drive API 직접, 256비트 키, 이름 Vitrine — 사용자 답 (L262) | ✅ | ✅ |
| M2 | 동기화 주기 20분(L482), WorkManager 하한 15분 (L485) | ✅ | ✅ |
| M3 | 토큰 permission denied 원인 = 바인드 마운트 소유권, 서버 uid 10001 (L1232, L1314) | ✅ | ✅ |
| L1 | 사용자 지시: 문서 읽기에 opus 를 다 쓰지 말고 작은 모델로 (L42) | ✅ | ✅ |
| L2 | 사용자: lune 은 정체, lute·mlua 적용성을 보라 (L2105) | ✅ | ✅ |
| L3 | 사용자(작업 중): moonwave-luau 는 mrow 로 완전히 다시 쓴다 (L1282) | ✅ | ✅ |
| L4 | B7 재귀 한계: mlua 6,663, 나머지 6,662 (L2333, L2388) | ✅ | ✅ |

### 3.3 결과

| | sonnet | haiku | 혼합안(haiku 요약 + sonnet 대조) | haiku + 기계 대조만 |
|---|---|---|---|---|
| 표본 10개 누락 | 0 | 0 | 0 | 0 |
| 항목 수(S/M/L) | 33 / 49 / 111 | 42 / 74 / 125 | 같음 | 같음 |
| 숫자 대조(기계): 원문에 없는 수 | 0 / 110 | 0 / 123 | — | 0 |
| 인용 대조(기계): 원문과 다른 인용 | 0 / 34 | 0 / 50 | — | 0 |
| 근거 줄 어긋남(CITE_OFF, 내용은 원문에 있음) | 1 | 3 | — | 3(표시만) |
| sonnet 대조 판정 wrong / unsupported | 0 / 1 (위 CITE_OFF 와 같은 것) | 0 / 0 | 0 / 0 | — |
| 손 검사에서 찾은 의미 오류 | 0 | 1(경미: "Kotlin + Compose + WorkManager. 사용자 요청" — Kotlin 만 사용자 선택, 나머지는 에이전트 선택) | 1 | 1 |
| 비용 S / M / L (CLI 추정) | $0.099 / $0.197 / $0.449 | $0.009 / $0.015 / $0.033 | +$0.089 / +$0.113 / +$0.293 | +$0 |
| 합계 | **$0.745** | **$0.057** | $0.552 | **$0.057** |
| 시간 S / M / L | 17s / 20s / 75s | 44s / 54s / 139s | +9s / +8s / +29s | +1s 미만 |
| 출력 토큰(M) | 2,916 | 12,436 | | |

- 비용은 `claude -p` 가 낸 `total_cost_usd`(클라이언트 추정)다. 구독 로그인이면 청구액이 아니라 사용 한도를 쓴다. sonnet 은 haiku 의 약 13배다.
- haiku 가 2~3배 느리고 출력 토큰이 4배다(사고 토큰 포함으로 보인다). 백그라운드라 사용자 대기 시간과는 상관없다.
- 범위(덮은 내용): haiku 가 항목을 더 많이 남겼다. M 의 결정 절은 haiku 12개, sonnet 6개다. haiku 는 OAuth 프로덕션 게시, CSRF 규칙, `file_id` 재봉인 금지를 더 남겼다. sonnet 은 L 에서 `unwrap -> never` 실패 → `mrow.expect` 채택 같은 경위를 더 남겼다. 어느 쪽도 표본 결정을 빠뜨리지 않았다.
- 1MB 당 비용(줄인 텍스트 기준): sonnet 약 $3.1, haiku 약 $0.24.
  - 지금 남은 27개 세션 8.67M자를 모두 소급하면 sonnet 약 $27, haiku 약 $2다.
  - 평소 부피(하루 11.6만 자)로는 하루 sonnet 약 $0.36, haiku 약 $0.03이다.

### 3.4 판단 — haiku 는 용납 가능한가
**용납 가능하다.** 기본은 haiku + 기계 대조를 권한다. 근거는 다음과 같다.
- 이후 세션의 행동을 바꿀 수 있는 오류는 숫자·결정의 값이나 주체가 틀린 경우다. 이번 표본에서 haiku 는 숫자 123개, 인용 50개를 모두 원문 글자 그대로 옮겼다. sonnet 대조도 wrong 0 이었다.
- 찾은 의미 오류 1건(Compose·WorkManager 를 사용자 선택으로 적음)은 이후 세션이 "사용자 지시"로 오인할 수 있는 종류다. 그러나 근거 줄 L262 에 사용자 답 원문이 있어 대조하면 바로 드러난다. 저장할 때 사용자 지시는 **원문 인용만** 허용하고 기계로 대조하는 규칙이 이 위험을 막는다.
- 혼합안(haiku + sonnet 대조)은 이번 표본에서 새로 잡은 것이 없다(sonnet 대조는 haiku 요약에서 wrong·unsupported 0). 비용은 sonnet 단독의 74%다. 이득이 비용을 정당화하지 못한다. **기계 대조(무료)만 상시로 돌리는 혼합안**을 권한다.
- 근거 줄 어긋남은 haiku 가 3건으로 더 많다. 내용이 원문에 있으므로 기계 대조가 "근거 줄 다름"으로 표시하는 것으로 충분하다.
- 한계
  - 표본은 3세션, 한국어 위주다. 요약 프롬프트가 근거 줄 인용을 강제해서 두 모델 차이가 줄었을 수 있다.
  - 손 검사는 결정 절과 수치 일부만 했다(항목 약 60개).
  - 몇 주 동안 haiku 로 돌리고, 기계 대조에서 NUM_MISSING·QUOTE_BAD 비율이 1%를 넘으면 sonnet 으로 올리는 감시 기준을 둔다(DESIGN §8).
- 사용자 규칙("haiku 는 읽기 전용 조사만")과의 관계: 이 구조에서 haiku 는 도구가 없다. 텍스트만 만들고, 파일 쓰기와 검증은 스크립트가 한다. 2026-11-10 사용자 결정("품질 차이가 많이 나면 sonnet, 용납 가능하면 haiku")을 따른 판단이다.

### 3.5 다시 재는 법
```
X=/code/Projects/claude-doctor/drafts/session-log
python3 -I $X/summarize.py <transcript.jsonl> --model haiku --out /tmp/sl-eval/out
python3 -I $X/verify.py /tmp/sl-eval/out/<sid>.haiku.md <transcript.jsonl> --show
python3 -I $X/verify_llm.py /tmp/sl-eval/out/<sid>.haiku.md <transcript.jsonl> --model sonnet
```
원자료는 `/tmp/sl-eval/`(휘발성)에 있다.

## 4. 남긴 흔적
- 실측용 `claude -p` 가 `~/.claude/projects/-tmp-sl-hookproj-omyV/`(세션 8d631c87)와 `-tmp-sl-hookproj-omyV--claude-worktrees-wt1/` 을 만들었다. 다른 실측의 `-tmp-*` 디렉터리와 같은 성격이다. 지우려면 두 디렉터리를 지우면 된다.
- 요약 호출(`--no-session-persistence`)은 트랜스크립트를 남기지 않았다.
- 원본 저장소, `~/.claude` 설정, claude-doctor 의 다른 경로는 고치지 않았다.
