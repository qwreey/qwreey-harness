---
title: 세션 기록 자동화 설계 (session-log)
description: 메인 세션이 아무것도 하지 않아도 PreCompact·SessionEnd·PostToolUse 훅이 백그라운드 요약기로 트랜스크립트를 증분 요약해 .claude/session/auto/ 에 coderag frontmatter 기록을 남기는 설계
keywords: [session-log, 세션 기록, PreCompact, SessionEnd, transcript_path, 증분 요약, remember, checkpoint, handover, haiku, sonnet]
kind: plan
status: landed in plugins/q/docs/session-log.md; 설계 근거로 남김
last_verified: 2026-11-10
---
# 세션 기록 자동화 설계 (session-log)

2026-11-10. 조사와 실측 근거는 `.claude/scopes/plugins/qwreey-sessions/audit/15-session-log.md` 에 있다. 이 폴더의 스크립트는 실측용 프로토타입이고 본 구현이 아니다.

> **구현됨: `plugins/q/` (이름 변경: 옛 plugins/session-log)** (README 가 현재 동작의 정본). 아래 본문과 달라진 점(사용자 결정 2026-11-10):
> - **저장 위치를 저장소 밖으로 옮겼다.** `${SESSION_LOG_HOME:-${XDG_DATA_HOME:-~/.local/share}/session-log}/<project-key>/records/` 에 둔다. 키는 git common-dir 기준이라 worktree 도 같은 키를 쓴다. §5.1 의 `.claude/session/auto/` 는 쓰지 않는다. 저장소에는 아무것도 쓰지 않는다.
> - **받아 가기 흐름**: 기록은 `pending` 으로 쌓인다. 저장소 메인 에이전트가 `/session-import`(`session-log pending|show|import|dismiss`)로 저장소 관례에 맞게 합치거나 고르고, 커밋도 그 에이전트가 한다. index 에 `imported`(위치, 커밋)나 `dismissed` 를 남긴다.
> - **알림**: 요약 완료(다음 PostToolUse·UserPromptSubmit 1회, info), pending(SessionStart·commit 직전 PreToolUse·PreCompact·handover, warn, 5개나 7일을 넘으면 action), PreCompact 상기(warn), 인계(info). 모두 `<harness-hook name="session-log" level=…>` 로 감싼 영어다(`home/.claude/HOOK-MESSAGES.md`).
> - **dedup 단위**는 (session_id, compact 회차, 트리거)다. 회차는 PreCompact 표지를 SessionStart(compact)·PostCompact 가 소비하며 올린다.
> - **주입 안전**: SessionStart 와 UserPromptSubmit 출력은 user turn 에 그대로 들어간다. 그래서 인계와 상기에는 구조화 항목(개수, 경로, ⚠ 없는 항목 제목, 대조를 통과한 인용)만 넣는다. 자유 텍스트 요약은 넣지 않고 `<>` 는 무력화한다. §7.1 의 "미해결 그대로 주입"을 대체한다.
> - **대조 실패 처리**: 원문에 없는 사용자 인용은 뺀다. 숫자는 ⚠ 표시를 붙인다. 대조 범위는 파일 전체가 아니라 그 구간이다(메모리, 그리고 더 엄격한 대조).
> - 요약 프롬프트는 영어로 바꿨다(`sllib/messages.py`). 절 제목은 한국어를 유지한다.
> - Stop 훅, 일별·주별 통합(§6)은 아직 구현하지 않았다.

| 파일 | 하는 일 |
|---|---|
| `extract.py` | 트랜스크립트를 바이트 오프셋부터 읽어 잡음을 거르고 마스킹한다. 줄마다 `L<원본 줄>` 을 붙인다 |
| `prompt.md` | 요약 프롬프트(절 일곱 개, 항목마다 근거 줄) |
| `summarize.py` | 구간을 나누고 격리된 `claude -p` 를 호출한다. 에코를 거부하고 frontmatter 를 붙여 쓴다 |
| `verify.py` | 숫자·해시·사용자 인용을 근거 줄 본문과 기계로 대조한다 |
| `verify_llm.py` | (혼합안 실측용) 결정·수치·지시를 모델에게 근거 줄과 대조시킨다 |
| `probe/` | 훅 stdin 덤프, 트랜스크립트 구조 보기 |

## 0. 목표와 원칙
- **메인 세션은 아무것도 하지 않는다.** 기록은 훅이 띄운 분리 프로세스가 쓴다. 메인 컨텍스트에 들어가는 것은 SessionStart 의 몇 줄뿐이다.
- **원본에 묶인 기록.** 항목마다 트랜스크립트 줄 번호 `(L123)` 을 단다. 숫자와 사용자 인용은 저장 전에 기계로 대조한다. 요약이 틀리면 이후 세션이 그것을 믿기 때문이다.
- **덮어쓰지 않는다.** 세션 기록은 덧붙이기만 한다. 일별·주별 통합은 별도 파일로 만들고, 원본 세션 기록에서 다시 만든다(압축의 압축을 압축하지 않는다. remember 의 오염 사고를 피한다).
- **실패는 조용히, 그러나 남긴다.** 훅은 어떤 경우에도 메인 세션을 막지 않는다. 실패는 상태 파일과 오류 로그에 남기고 SessionStart 한 줄로 알린다.
- remember(Community License, 경쟁 제품 금지)의 코드는 쓰지 않는다. 아이디어만 참고하고 새로 짠다.

## 1. 전체 그림
```
훅(가벼움, <100ms)                                분리 프로세스(setsid, 출력 /dev/null)
PreCompact ─────┐                                ┌─ flock .state/<sid>.lock (못 잡으면 pending 표시 후 끝)
SessionEnd ─────┤ stdin: session_id,             ├─ offset 부터 extract → 마스킹 → 구간 나누기(≤90k자)
PostToolUse ────┤ transcript_path, trigger  ──▶  ├─ 구간마다 claude -p (격리) → 형식·에코 검사
 (async, 쿨다운) │ → 트리거 판단 → detach          ├─ verify(숫자·인용·해시) → 표시 달기
Stop(쿨다운) ────┤                                ├─ 세션 파일에 절 덧붙임(임시 파일 + rename)
/checkpoint ────┘ (수동: flush --wait)           └─ state 갱신(offset), pending 이면 한 번 더
SessionStart ── 인계 몇 줄 + 안내 한 줄 주입 / 필요하면 일별·주별 통합을 detach
```

## 2. 트리거

| 이벤트 | 조건 | 동작 | 근거 |
|---|---|---|---|
| **PreCompact**(auto·manual) | 항상 | 강제 flush(쿨다운 무시). stdout 지시는 §7.3(선택) | compact 직전이 자연스러운 구간 경계다. 이 시점이 사용자가 손으로 64회 반복한 "기록 → compact" 의식에 해당한다. compact 뒤에도 트랜스크립트 앞부분은 남는다(append-only). 그래서 데이터 보존이 아니라 **시점** 때문에 쓴다 |
| **SessionEnd** | 항상 | 강제 flush. stdin 만 읽고 곧바로 detach | 예산 1.5초. 플러그인 훅은 timeout 으로 예산을 못 늘린다 |
| **PostToolUse** | `async: true`. 지난 실행 뒤 20분 이상 **그리고** 트랜스크립트가 지난 오프셋보다 512KB 이상 자람 | 일반 flush | 몇 시간짜리 자율 작업 중간 기록. stat 두 번이면 판단이 끝난다 |
| Stop | PostToolUse 와 같은 쿨다운 | 일반 flush | 턴 끝이 구간 경계로 더 깔끔하다. PostToolUse 보다 드물게 불린다 |
| PostCompact | 항상 | `compact_summary` 를 `.state/<sid>.compact-<n>.md` 로 보관(요약 호출 없음) | 공짜로 받는 메인 모델 요약. 트랜스크립트가 30일 뒤 지워져도 남는다 |
| 수동 `/checkpoint` | 사용자나 모델 | `session-log flush --wait 120` 후 새 절의 "미해결" 만 보여 준다 | `.claude/audit/10` §2.1 |

- 일반 flush 는 줄인 텍스트가 3,000자 미만이면 요약하지 않는다. 오프셋도 그대로 둬 다음에 합친다. 강제 flush 는 500자 이상이면 요약한다.
- 재귀 방지: 훅 첫 줄에서 `SESSION_LOG_NESTED=1` 이면 곧바로 끝낸다. 요약 호출 자체는 `--setting-sources ""` 로 사용자·프로젝트 훅을 싣지 않는다(실측 0회 발화).
- 서브에이전트 안에서 부른 훅(`agent_id` 있음)은 무시한다. 서브에이전트 보고는 메인 트랜스크립트의 peer 메시지로 들어온다.

## 3. 처리 (분리 프로세스)
1. **저장 위치 결정**
   - `CLAUDE_PROJECT_DIR` 를 쓴다. stdin `cwd` 는 세션 중 `cd` 로 바뀌므로 쓰지 않는다.
   - `git rev-parse --git-common-dir` 로 worktree 면 본 체크아웃으로 올린다. 저장 위치는 `<root>/.claude/session/auto/` 다.
   - git 저장소가 아니면 `CLAUDE_PROJECT_DIR` 그대로 쓴다.
2. **잠금**
   - `.state/<sid>.lock` 에 `fcntl.flock(LOCK_EX|LOCK_NB)` 를 건다. 프로세스가 죽으면 커널이 푼다.
   - 못 잡으면 `.state/<sid>.pending` 을 만들고 끝낸다. 잡은 쪽이 끝날 때 pending 을 보고 최대 3번 더 돈다.
   - 기계 전체 동시 요약 상한은 2다(`${XDG_RUNTIME_DIR:-/tmp}/session-log/slot-{0,1}.lock`).
3. **읽기**
   - `.state/<sid>.json` 의 `offset`(바이트)부터 읽는다. `\n` 으로 끝난 줄까지만 처리한다(트랜스크립트는 비동기로 써진다).
   - 남기는 것: 사람 발언(typed, 작업 중 큐 `queued_command`, AskUserQuestion 답), 어시스턴트 text, 도구 한 줄(Bash 명령 앞부분과 설명, Edit/Write 경로, Agent 설명, **git commit 메시지**), 도구 오류 앞부분, 서브에이전트 보고·다른 세션 메시지(앞 1,500자), compact 경계.
   - 버리는 것: thinking, 일반 tool_result, attachment 류 reminder, compact 요약(이전 기록과 중복), task-notification, 메타 레코드.
   - 부피는 원본의 1~3%다(tbox 12.9MB → 219k자).
4. **마스킹**: 저장 전, 그리고 모델에 넘기기 전에 한다.
   - 대상: Anthropic·GitHub·AWS·Slack 키, JWT, 개인 키 블록, `token=…` 류 대입, Roblox 쿠키(`extract.py` `MASKS`).
   - tool_result 를 기본으로 버리므로 `cat .env` 같은 출력은 애초에 들어오지 않는다.
5. **구간 나누기**: 줄 경계에서 ≤90,000자. 구간 하나가 세션 파일의 절 하나가 된다.
6. **요약 호출**(§4): 형식 검사로 `## 요약` 이 있는지 보고, 에코 검사로 프롬프트 문구가 되풀이되면 거부한다.
7. **검증**(§8): `verify.py` 규칙으로 숫자·해시·인용을 근거 줄 본문(JSONL 의 message.content 만, 메타데이터 제외)과 대조한다.
   - 어긋난 항목 끝에 `⚠원문 불일치` 또는 `⚠근거 줄 다름` 을 붙인다.
   - frontmatter `verify:` 에 개수를 남긴다.
8. **쓰기**: 세션 파일에 절을 덧붙인다. 같은 디렉터리에 임시 파일을 만들고 rename 한다. 그다음 state 의 offset 을 옮긴다.
9. **실패**
   - 호출 실패, 시간 초과(300초), 형식 실패면 offset 을 그대로 두고 `failures` 를 1 늘린다. 오류는 `.state/errors.log` 에 남긴다.
   - 같은 구간이 3회 실패하면 "요약 실패 — 원문 L a–b, 사람 발언 N개" 자리표시 절을 쓰고 넘어간다(무한 재시도 방지).
   - 트랜스크립트가 없으면(30일 정리) 건너뛴다.

## 4. 요약 모델과 실행 방법

### 4.1 모델
**기본 haiku + 기계 대조**를 권한다. 설정으로 sonnet 으로 바꿀 수 있다.
- 근거: `.claude/audit/15` §3. 표본 10개 누락은 두 모델 모두 0이었다. haiku 는 숫자 123개와 인용 50개가 원문과 모두 일치했다. 의미 오류는 경미한 1건이었다.
- 비용은 sonnet 의 1/13이다. 3세션 합계 $0.057 대 $0.745.
- haiku 는 도구 없이 텍스트만 만든다. 파일 쓰기와 검증은 스크립트가 한다.
- 혼합안(haiku 요약 + sonnet 대조)은 비용이 sonnet 의 74%인데 새로 잡은 오류가 없었다. 상시로 쓰지 않는다.
- 일별·주별 통합도 같은 모델을 쓴다. 입력이 이미 짧은 기록이라 싸다.

### 4.2 `claude -p` 대 API 직접 호출

| 기준 | `claude -p`(추천) | API 직접(SDK/curl) |
|---|---|---|
| 인증 | 이미 로그인한 구독(OAuth)을 그대로 쓴다. 새 비밀이 없다 | `ANTHROPIC_API_KEY` 를 둬야 한다(이 sandbox 에는 없다). 키 보관 문제가 생긴다 |
| 비용 | 구독 사용 한도에서 나간다. CLI 가 `total_cost_usd` 로 추정치를 준다. 호출마다 시스템 프롬프트가 약 2.8k 토큰 붙는다(`--setting-sources ""` 기준) | 토큰 단가대로 따로 청구된다. 오버헤드가 없다 |
| 재귀 훅 | 막아야 한다. `--setting-sources ""`(실측 0회), `--no-session-persistence`(트랜스크립트 안 남음), `--tools ""`, 빈 cwd, `CLAUDECODE`·`CLAUDE_CODE_*` 제거, `SESSION_LOG_NESTED=1`. managed 훅은 못 끈다 → 표지 변수로 막는다 | 훅 개념이 없다 |
| 이식성 | 훅이 도는 곳에는 `claude` 가 항상 있다 | python 패키지나 curl, 키 배포가 필요하다 |
| 모델 이름 | 별칭(`haiku`, `sonnet`)이 최신을 따라간다 | ID 를 고정해 관리해야 한다 |
| `--bare` | 쓰지 않는다. 구독 로그인을 안 쓰고 API 키를 요구한다 | — |

- 호출 꼴: `claude -p --model <m> --output-format json --tools "" --setting-sources "" --no-session-persistence --strict-mcp-config --mcp-config '{"mcpServers":{}}'`, stdin 으로 프롬프트를 넘긴다.
- API 키가 있는 환경을 위해 `backend = "api"` 를 나중에 넣을 수 있게 호출부를 한 함수로 둔다.

## 5. 저장

### 5.1 배치
```
<root>/.claude/session/
  README.md                  (기존 관행 그대로. auto/ 는 건드리지 않음)
  2026-…-NN-slug.md          (사람·에이전트가 쓰는 서술 기록. 그대로)
  auto/
    2026-11-10-c9a9e895.md   세션 기록. <세션 시작일>-<session_id 앞 8자>. 64KB 를 넘으면 -2, -3
    daily/2026-11-10.md      일별 통합
    weekly/2026-W46.md       주별 통합
    .state/                  (자체 .gitignore 에 `*`) <sid>.json, <sid>.lock, <sid>.pending, <sid>.compact-<n>.md, errors.log
```
- quad `doc-check.py` 는 `session/` 을 건너뛴다(`SKIP_DIRS`). 그래서 `auto/` 가 색인 규칙과 부딪히지 않는다.
- coderag doc ID 는 `doc session.auto.2026-11-10-c9a9e895 in ".claude"` 이다(§11.2).

### 5.2 세션 파일 형식 (coderag §11.4, §17, §21)
```markdown
---
title: 세션 c9a9e895 — 세션 기록 자동화 조사·설계
description: <가장 최근 구간의 description. 120자 이내>
keywords: [<구간 keywords 의 합, 최대 12개>]
kind: session
status: active                 # 통합 뒤 30일 지나면 archived(§6)
last_verified: 2026-11-10      # 마지막 절을 쓴 날
session_id: c9a9e895-fd27-4494-abc9-c2985ecca5e0
project: claude-doctor
source_transcript: ~/.claude/projects/-code-Projects-claude-doctor/c9a9e895-….jsonl   # 30일 보존
summarizer: haiku
verify: {items: 125, num_missing: 0, quote_bad: 0, cite_off: 3}
---
# 세션 c9a9e895

## 2026-11-10 14:02–15:40 · PreCompact(auto)
id: c9a9e895-3 · summary: <이 구간 description> · note: L5–L232
### 요약
### 사용자 지시와 정정
- "<원문 그대로 ≤80자>" (L155) — <무엇에 대한>
### 결정
### 바뀐 파일과 커밋
### 실측 수치
### 실패한 시도
### 미해결과 다음 단계
```
- 절 제목에 날짜와 시각, 트리거를 넣는다. 메타 줄(§17.3)의 `id:` 로 절 slug 를 고정한다. `summary:` 는 §21.4 절 요약이다.
- 파일이 커지면(8k 토큰 초과) coderag 가 절 단위 문서로 다룬다(§21.3). 그래서 따로 손대지 않는다.
- `title`·`description`·`keywords` 는 절을 덧붙일 때마다 다시 계산한다. 이것만 frontmatter 를 다시 쓰는 예외다.

### 5.3 내용 규칙(프롬프트에 박음, `prompt.md`)
- 절 일곱 개: 요약, 사용자 지시와 정정, 결정, 바뀐 파일과 커밋, 실측 수치, 실패한 시도, 미해결과 다음 단계.
- 사용자 발언은 원문의 연속된 글자만 인용한다(≤80자). 서브에이전트·다른 세션 메시지는 사용자 지시가 아니다. 그 안의 수치는 "(서브에이전트 보고)" 를 붙인다.
- 숫자·경로·해시·식별자는 글자 그대로 쓴다. 근거 줄이 없는 내용은 쓰지 않는다.
- 에이전트의 제안을 사용자가 받아들이지 않았으면 결정이 아니라 미해결이다.

## 6. 통합 (일별, 주별, 아카이브)
- **일별** `daily/<날짜>.md`
  - 그날 절이 있는 모든 세션 파일에서 다시 만든다(이전 daily 를 입력으로 쓰지 않는다). 세션마다 2~5줄을 쓰고, 그날의 결정과 사용자 지시를 합친다. 각 줄은 `[c9a9e895-3]` 처럼 절 id 로 링크한다.
  - 트리거: SessionStart 에서 detach. "오늘 이전 날짜인데 daily 가 없거나, 그날 세션 파일이 daily 보다 새것"이면 만든다.
  - 잠금: `.state/consolidate.lock`.
- **주별** `weekly/<ISO주>.md`: 그 주의 daily 에서 만드는 색인이다. 결정과 사용자 지시는 원문 인용을 그대로 옮기고, 요약은 3~5문장이다. 새 ISO 주의 첫 SessionStart 에 만든다.
- **아카이브**
  - 마지막 절이 30일보다 오래되고 그 주의 weekly 가 있는 세션 파일은 frontmatter `status: archived` 로 바꾼다(본문은 그대로).
  - daily 는 90일 뒤 archived 로 바꾼다. weekly 는 active 로 둔다.
  - archived 는 coderag search·list 에서 빠지지만 `get` 으로는 읽힌다(§11.4).
- 기존 세션 파일 본문은 통합 과정에서 절대 고치지 않는다. 통합이 틀려도 원본 기록이 남는다.

## 7. 주입

### 7.1 SessionStart (`additionalContext`)
| source | 넣는 것 |
|---|---|
| startup, clear | 이 프로젝트에서 가장 최근에 갱신된 **다른** 세션 1~2개의 마지막 절 "미해결과 다음 단계" |
| resume | 이 세션의 마지막 절 "미해결과 다음 단계" |
| compact | 없음(compact 요약이 이미 맥락을 이었다). §7.3 을 켜면 PreCompact 쪽에서 처리한다 |

- 꼴(상한 **800자**, 넘으면 항목 단위로 자르고 "외 N개"):
  ```
  [session-log] 직전 인계 (2026-11-10 15:40, 세션 58bd1a5b):
  - <미해결 1> (L…)
  - <미해결 2>
  자동 세션 기록은 .claude/session/auto/ 에 있다. 찾을 때는 coderag search(또는 doc-locator)로 찾고 결정·숫자는 (L…) 로 원문을 확인한다.
  ```
- 요약 실패나 오류가 있으면 한 줄을 더한다: `[session-log] 기록 실패 2건 — .claude/session/auto/.state/errors.log`.
- 같은 저장소에 지금 갱신 중인 다른 세션이 있으면 한 줄을 더한다(quad 처럼 동시 세션이 많은 곳에서 유용, 선택).

### 7.2 크기 근거
- Claude Code 의 훅 출력 한도는 10,000자다. remember 는 9,000바이트를 썼다.
- 우리는 기억 전체가 아니라 인계만 넣는다. 그래서 800자(한글 기준 약 1.3k 토큰, coderag §21.2 추정식)로 둔다.
- 매 세션 고정비라 작게 시작해서 모자라면 늘린다.

### 7.3 PreCompact stdout (선택, 추천)
- PreCompact 훅의 stdout 은 compact 요약 지시가 된다(≤10,000자, 실측 확인).
- 훅이 모델 호출 없이 extract 만으로 "지난 compact 이후 사용자 발언 원문 목록"(≤6,000자)을 뽑아 다음 지시를 붙여 낸다: "다음 사용자 발언은 요약에 원문 그대로 보존하라."
- 이것은 `.claude/audit/10` 의 "작업 중 지시가 compact 를 거치며 사라진다" 문제를 직접 겨냥한다. 메인 세션은 이 비용을 compact 요약 안에서만 낸다.

## 8. 검증과 감시
- 저장 때: `verify.py` 규칙(기계, 무료)을 적용한다.
  - `NUM_MISSING`(원문 어디에도 없는 수), `QUOTE_BAD`(원문에 없는 인용)는 `⚠원문 불일치` 를 붙인다.
  - `CITE_OFF`(근거 줄만 다름)는 `⚠근거 줄 다름` 을 붙인다.
- 읽는 쪽 규칙(안내 한 줄과 coderag 스킬에 둠): 자동 기록은 요약이다. 결정·숫자를 근거로 행동하기 전에 `(L…)` 로 트랜스크립트를 확인한다. 트랜스크립트가 지워졌으면 ⚠ 표시가 없는 항목만 믿는다.
- 감시: 주별 통합 때 `verify` 합계를 weekly 머리에 적는다. NUM_MISSING+QUOTE_BAD 가 항목의 1%를 넘으면 weekly 에 "요약 모델 상향 검토" 한 줄을 남긴다.
- 정확도 회귀 시험: 이번 실측 3세션의 대조 표본 10개를 `tests/` 로 옮긴다. 프롬프트를 바꿀 때 다시 돌린다.

## 9. 기존 것과의 관계
- **`/handover`(stl-luau-doctor, 사람이 손보는 인계)**: 자동 기록은 handover 의 **입력**이다.
  - handover 0단계에 "auto 기록의 미해결·사용자 지시를 todos·question 과 대조"를 넣는다.
  - 자동 기록은 todos·question·conventions 를 고치지 않는다. 커밋도 하지 않는다(공유 체크아웃에 여러 세션이 있다).
- **`.claude/session/README.md` 관행**(quad: `YYYY-MM-DD-NN-slug.md` 서술 기록 + `session-summary.md` 색인)
  - 서술 기록은 그대로 둔다. 논쟁 과정과 판단 이유는 사람이나 에이전트가 쓰는 쪽이 낫다.
  - 자동 기록은 "기록이 하나도 없어 `~/.claude` 를 뒤지는" 경우를 없애는 안전망이다.
  - README 색인에는 `auto/` 한 줄만 둔다.
- **메모리**(`~/.claude/projects/*/memory`): 메모리는 오래 가는 사실과 선호(작고 항상 로드됨)이고, 세션 기록은 시간순 기록이다.
  - 요약기는 메모리를 쓰지 않는다.
  - `/checkpoint` 가 "사용자 지시와 정정" 가운데 반복되는 것을 메모리 후보로 **제안만** 한다(사람 승인).
- **`/checkpoint`(.claude/audit/10 §2.1)**
  1. `session-log flush --wait 120`
  2. 새 절의 "미해결과 다음 단계"와 "사용자 지시"만 읽는다(작다).
  3. compact 인자 초안(남길 것 / 잊을 것 / 다음 할 일)을 만든다.
  - 메인이 기억을 더듬어 쓰는 대신 기록을 근거로 쓴다.
- **컨텍스트 % 훅(H1)**: 따로 둔다. 60·75·90% 알림에 "`/checkpoint` 를 제안하라"를 붙이면 둘이 이어진다.
- **트랜스크립트 보존**: `cleanupPeriodDays` 기본 30일. 자동 기록의 `(L…)` 대조와 소급 생성은 그 안에서만 된다(D3).

## 10. 배포
**추천: coderag 와 같은 마켓의 별도 플러그인 `session-log`.**
- 생명주기가 다르다. session-log 는 모델 호출과 비용이 드는 훅이고, coderag 는 결정적인 색인·검색 도구다. coderag 만 쓰고 싶은 저장소나 사람이 있다.
- coderag 불변식("런타임은 캐시만, 프로바이더는 gen 때만")과 섞지 않는다.
- 구현 언어가 다르다. session-log 는 python 스크립트 몇 개이고, coderag 는 Rust 바이너리 빌드다.
- 실패를 격리할 수 있다. 요약기가 고장 나도 검색은 산다.
- 결합점은 **frontmatter 스키마(coderag §11.4, §17)라는 문서화된 계약 하나**다. coderag 의 SessionStart `gen --changed` 훅(§22 A)이 새 기록을 색인한다. coderag 가 없어도 기록은 평범한 markdown 이다.

이식성
- 경로를 하드코딩하지 않는다.
  - 저장 위치는 `CLAUDE_PROJECT_DIR` 와 git common-dir 로 정한다.
  - 트랜스크립트는 stdin `transcript_path` 로 받는다.
  - 스크립트는 `${CLAUDE_PLUGIN_ROOT}`, 사용자 설정은 `${CLAUDE_PLUGIN_DATA}/config.json`, 프로젝트 설정은 `.claude/session-log.json` 에 둔다.
  - 환경 변수 `SESSION_LOG_MODEL`·`SESSION_LOG_DISABLE` 로 덮어쓸 수 있다.
- 의존성: `python3`(표준 라이브러리만), `claude`(PATH), `git`(선택), `setsid`(없으면 `nohup` + `os.setsid()` 를 python 에서).
- SessionEnd 1.5초: 훅은 stdin 을 읽고 detach 만 한다(python 기동 약 50ms). 플러그인 훅은 timeout 으로 예산을 늘릴 수 없으므로 detach 가 유일한 길이다.
- 다른 sandbox: 저장소마다 `.claude/session/auto/` 가 생기고, 사용자가 pull 할 때 같이 온다(D2).

## 11. 결정 필요
- **D1 요약 모델**: haiku + 기계 대조(추천, `.claude/audit/15` §3.4) / sonnet / 혼합안(haiku + sonnet 대조, 비용 74%, 이번 표본에서 이득 없음).
- **D2 자동 기록의 git**: 추적하고, 커밋은 `/handover`·`/checkpoint` 에서 사람이 한다(추천. 워커는 커밋하지 않는다) / `.gitignore`(기록이 sandbox 에만 남는다).
- **D3 트랜스크립트 보존**: 정본 `home/.claude/settings.json` 에 `cleanupPeriodDays: 180` 을 넣는다(추천. 대조·소급 기간을 늘린다. 디스크는 지금 1.2GB+서브에이전트) / 기본 30일.
- **D4 PreCompact stdout 으로 사용자 발언 원문 보존 지시**(§7.3): 켬(추천) / 끔.
- **D5 소급 생성**: 남은 트랜스크립트 27개를 haiku 로 소급 요약(약 $2, 30일 정리 전에) / 하지 않음.
- **D6 배포**: 같은 마켓의 별도 플러그인(추천) / coderag 플러그인에 포함.
- **D7 중간 트리거**: PostToolUse(async) + Stop, 쿨다운 20분·512KB(추천) / PostToolUse 만 / 중간 트리거 없음.
- **D8 저장 위치**: `.claude/session/auto/`(추천, 요청안) / `.claude/session-log/`(기존 session/ 관행과 완전 분리).
- **D9 SessionStart 주입 상한**: 800자(추천) / 1,500자 / 주입 없음(안내 한 줄만).

## 12. 구현 순서
1. **M0 워커 CLI**: `session-log flush|status|verify|backfill`. 이 폴더 스크립트를 정리해 state·잠금·원자적 쓰기·실패 처리를 붙인다. `/checkpoint` 스킬과 연결한다.
2. **M1 훅**: PreCompact, SessionEnd, PostToolUse(async)+Stop 쿨다운, PostCompact 보관. `-p` 로 `/compact` 를 유도해 끝까지 시험한다(`.claude/audit/15` §2.2 방법).
3. **M2 SessionStart 주입**과 오류 한 줄.
4. **M3 통합**: daily, weekly, archived 전환. 동시 세션 잠금 시험(quad 형태: 같은 키에 두 세션).
5. **M4 소급**: `backfill --since` 로 남은 트랜스크립트를 처리한다(D5). 대조 표본 회귀 시험.
