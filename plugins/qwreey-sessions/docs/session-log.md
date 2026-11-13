---
title: session-log 훅과 /qwreey-sessions:checkpoint·/qwreey-sessions:import (qwreey-sessions 플러그인) — 세션 기록 자동화
description: 훅이 트랜스크립트를 분리 프로세스에서 증분 요약하고 원문과 기계 대조해 저장소 밖 외부 저장소에 coderag 기록으로 남긴다. 저장소 메인 에이전트가 /qwreey-sessions:import 로 받아 간다
keywords: [session-log, 세션 기록, PreCompact, SessionStart, handover, qwreey-sessions:import, qwreey-sessions:checkpoint, haiku, 외부 저장소, pending]
kind: reference
status: active
last_verified: 2026-11-10
---
# session-log 훅 (qwreey-sessions 플러그인)

메인 세션이 아무것도 하지 않아도 세션 기록이 남게 한다. 설계 근거는 `.claude/archive/research/drafts/session-log/DESIGN.md`, 조사·실측은 `.claude/audit/15-session-log.md`.

## 흐름
1. 훅이 트리거를 판단한다(PreCompact·SessionEnd 는 강제, PostToolUse·UserPromptSubmit 은 쿨다운 20분 + 512KB 증가).
2. `setsid -f` 로 분리한 워커(`scripts/cli.py flush`)가 바이트 오프셋부터 트랜스크립트를 줄이고(1~3%), 9만 자 구간마다 격리된 `claude -p --model haiku` 를 한 번 부른다.
   - 모델에게 도구를 주지 않는다(`--tools ""`). 파일 쓰기와 검증은 스크립트가 한다.
   - 격리: `--setting-sources ""`, `--no-session-persistence`, `--strict-mcp-config`, 빈 임시 cwd, `CLAUDECODE`·`CLAUDE_CODE_*` 제거, `SESSION_LOG_NESTED=1`(우리 훅은 이걸 보면 바로 끝난다).
3. 숫자·커밋 해시·사용자 인용을 그 구간의 원문 줄과 기계로 대조한다.
   - 원문에 없는 인용은 **뺀다**. 원문에 없는 숫자는 `⚠원문 불일치`, 근거 줄이 틀리면 `⚠근거 줄 다름` 을 붙인다.
   - 합계는 frontmatter `verify:` 에 남는다.
4. **외부 저장소**에 절을 덧붙인다. 저장소 안에는 아무것도 쓰지 않는다.
5. 다음 훅 기회에 메인 세션에 알린다. 저장소의 메인 에이전트가 `/qwreey-sessions:import` 로 골라 받아 가고, 커밋은 그 에이전트가 한다.

## 외부 저장소
`${SESSION_LOG_HOME:-${XDG_DATA_HOME:-~/.local/share}/session-log}/<project-key>/`
- `<project-key>` 는 본 체크아웃 경로의 영숫자 아닌 글자를 `-` 로 바꾼 것이다(`/code/Projects/quad` → `-code-Projects-quad`).
- 루트는 `CLAUDE_PROJECT_DIR`(없으면 stdin `cwd`)에서 `.git` 을 찾아 정한다. worktree 면 `commondir` 를 따라 본 체크아웃으로 올린다. 그래서 worktree 세션도 같은 키를 쓴다.

```
project.json                       {"root", "key"}
records/<시작일>-<sid8>[-N].md      세션 기록(64KB 넘으면 -2, -3)
index.json                         rid → pending | imported(위치, 커밋) | dismissed
.state/<sid>.json                  워커: offset(바이트), line, sections, failures, cost_usd
.state/<sid>.hook.json             훅: compact 회차, 알림 커서, 이미 한 알림
.state/<sid>.compact-<n>.md        PostCompact 의 compact_summary
.state/notices.jsonl, errors.log
```

기록 형식(coderag §11·§17·§21): frontmatter `title, description, keywords, kind: session, date, session_id, project, project_root, source_transcript, summarizer, verify`.
절마다 `## <날짜 시각–시각> · <트리거>` 다음 메타 줄 `id: <sid8>-<n> · summary: … · note: L<a>–L<b>` 을 둔다. 그 아래 `### 요약 / 사용자 지시와 정정 / 결정 / 바뀐 파일과 커밋 / 실측 수치 / 실패한 시도 / 미해결과 다음 단계` 가 오고, 항목마다 `(L…)` 근거 줄을 단다.

## 알림 (모델에게 들어가는 영어, `<harness-hook name="session-log" level=…>`)
| 때 | 훅 | level | 내용 |
|---|---|---|---|
| 요약을 시작함(쿨다운 트리거) | PostToolUse·UserPromptSubmit | info | 구간과 "끝나면 알린다" |
| 요약이 끝남 | 다음 PostToolUse·UserPromptSubmit 1회 | info | 새 절 수, 기록 경로, 대조 실패 수, pending 수 |
| 세션 시작 | SessionStart | info / warn·action (level 마다 태그 하나) | 인계(startup·clear 만, 직전 다른 세션의 미해결, ≤800자; resume 은 맥락이 복원되므로 없음. 기록이 트랜스크립트보다 `SESSION_LOG_HANDOVER_LAG_LINES` 넘게 뒤처졌으면 항목 대신 "뒤처짐" 한 줄, 트랜스크립트가 `SESSION_LOG_HANDOVER_LIVE_MIN` 분 안에 바뀐 세션은 아직 일하는 중이라 생략) + pending + 찾는 법 한 줄 |
| compact 뒤 | SessionStart(compact) | info / warn | 이 세션 기록 경로 + pending(새 회차라 다시) |
| commit 직전 | PreToolUse(Bash, `git … commit`) | warn | pending 과 정확한 명령 `session-log import`(막지 않음) |
| 인계·정리 | UserPromptSubmit(`/handover`·`/qwreey-sessions:checkpoint`·인계 낱말), PreToolUse(Skill handover) | info·warn | pending |
| 기록을 읽음 | PostToolUse(Read·Grep, `records_read.py`) | info | 스냅샷이니 현재 파일·git log 로 확인하라는 한 줄(세션·에이전트·compact 회차마다 한 번). 큰 기록(`SESSION_LOG_READ_WARN_KB`, 16KB 초과)을 offset·limit 없이 읽으면 `/qwreey-sessions:recall` 이나 검색 먼저 안내(그때마다) |
| compact 직전 | PreCompact(manual·auto) stdout | warn | 상기: 사용자 지시 원문, 아직 기록 안 된 최근 사용자 발언, 결정, 미해결, 끝난 일, 기록 경로 |
| compact 직전 | PreCompact(manual·auto) stdout, 태그 없음 | - | 요약기 지시 두 줄(`messages.COMPACT_INSTRUCTIONS`): 남길 것(사용자 결정 원문, 답 안 된 질문, 도는 백그라운드 에이전트, 커밋·바뀐 파일, 지금 걸린 제약)과 뺄 것(도구 원출력, 커밋된 파일 내용, 끝난 에이전트의 상세 보고). compact 마다 |

- dedup 단위는 **(session_id, compact 회차, 트리거)** 다.
  - 회차는 qwreey-sessions 자기 것(`scripts/compact_epoch.py`, `$TMPDIR/claude-qwreey-sessions-epoch/<sid>`)이고 hook.py 가 PreCompact 에서 올린다. PreCompact 는 SessionStart(compact)·PostCompact 보다 먼저라 읽는 훅(records_read 포함)이 항상 올라간 값을 본다. 취소된 compact 는 알림을 한 번 더 낼 뿐이다.
  - 같은 모듈의 사본이 q·qwreey-advisor·qwreey-conventions·qwreey-workspace 에 있고(정본은 저장소 `lib/compact_epoch.py`, `tools/tests/test-vendored-copies.py` 가 바이트 동일성을 검사), 각자 자기 회차를 올린다. 하네스가 없어도 돈다.
- pending 알림 level (action 은 쓰지 않는다: import 는 명령 하나라 막고 물을 일이 아니다)
  - 보관 위치 설정됨: 평소 info, commit 직전이거나 `SESSION_LOG_PENDING_STRONG_COUNT`(5)개·`…_DAYS`(7)일 이상이면 warn. 내용은 `session-log import` 한 줄.
  - 미설정: 평소 info, `SESSION_LOG_HOME_NUDGE_COUNT`(3)개 또는 `SESSION_LOG_HOME_NUDGE_DAYS`(3)일 이상(strong 도 포함)이면 warn 으로 위치를 사용자에게 제안하라고 한다(`docs/sessions/` 팀 공개, `.claude/sessions/` 에이전트 전용, 있으면 `handover/`·`handoff/`·`audit/`·`.claude/audit/`·`.claude/handoff/` 같은 이력 폴더, 밖에 두기).
  - `archive_only`: pending 알림이 없다.
- 주입 안전
  - 인계와 상기에는 구조화된 항목만 넣는다: 개수, 경로, ⚠ 없는 미해결·결정 제목(110자), 대조를 통과한 사용자 인용.
  - 자유 텍스트 요약(`### 요약`)은 넣지 않는다.
  - `<`·`>` 는 `‹`·`›` 로 바꾼다.
- 한 출력에 알림이 여럿이면 태그 하나에 가장 높은 level 을 단다(규약 `HOOK-MESSAGES.md`).
- 메시지 문자열은 모두 `scripts/sllib/messages.py` 에 있다.

## 받아 가기와 보관 위치
기록은 그 시점의 스냅샷이다. 낡아도 되고 최신으로 유지하지 않는다. 읽는 쪽이 낡았을 수 있음을 알고 확인하면 된다.
```
session-log import [rid…]               # 대기 전부(또는 고른 것)를 보관 폴더로 그대로 복사 + imported. 고르거나 고쳐 쓰지 않는다
session-log dismiss <rid…> [--reason …]
session-log home [PATH | --archive-only | --unset]   # 저장소 보관 폴더 보기·저장
session-log pending                     # rid  ~토큰  절 수  생성일  [⚠대조 실패] + 요약 한 줄
session-log show <rid> [--section N]
session-log status                      # 세션별 오프셋·비용·실패, imported 기록의 커밋
session-log flush [--force] [--wait]    # 지금 요약(/qwreey-sessions:checkpoint)
session-log backfill --plan plan.json [--budget 4] [--dry-run]
```
- 보관 위치는 저장소의 `.claude/session-log.json` 이다: `{"records_home": "docs/sessions"}` 또는 `{"archive_only": true}`. 커밋하면 동료가 같은 위치를 쓴다. 외부 저장소 `project.json` 은 기계마다 달라 공유가 안 되고, `.claude/conventions.json` 은 qwreey-conventions 의 스키마라 q 전용 파일로 나눴다.
- 위치가 없으면 `--to` 가 없는 import 는 거절하고 사용자에게 묻고 `session-log home <경로>` 로 정하라고 한다(원치 않은 폴더에 파일이 남지 않게). `archive_only` 도 `--to` 가 없으면 거절한다.
- 복사본은 frontmatter 바로 뒤에 두 줄 머리말(세션 id, 덮는 기간, 원본 트랜스크립트, "스냅샷이라 낡았을 수 있으니 현재 파일·git log 로 확인")만 붙고 본문은 그대로다.
- 가져간 뒤 새 절이 붙으면 다시 pending 이 되고, 다음 import 가 같은 파일을 늘어난 판으로 덮는다.
- `bin/session-log` 이 PATH 에 없으면 `"${CLAUDE_PLUGIN_ROOT}/bin/session-log"` 로 부른다.
- 스킬: `/qwreey-sessions:import`(한 줄 import, 위치 없으면 사용자에게 한 번 묻기), `/qwreey-sessions:recall`(옛 논의 찾기: haiku 가 위치만 찾고 sonnet 이 그 절만 읽어 요약하며 현재 상태와 대조, 메인이 행동 전에 검증), `/qwreey-sessions:checkpoint`(지금 flush 하고 새 미해결·지시만 본다).

## 설정
우선순위는 환경 변수 > 저장소 `.claude/harness.local.env` > 저장소 `.claude/harness.env`(저장소는 `$CLAUDE_PROJECT_DIR`) > 사용자 `harness.env`(`$HARNESS_ENV`, 없으면 `$CLAUDE_CONFIG_DIR/harness.env` 또는 `~/.claude/harness.env`) > 기본값이다. `SESSION_LOG_*` 키만 읽고, `SESSION_LOG_HOME`·`SESSION_LOG_CLAUDE` 는 저장소 층이 바꾸지 못한다. 읽기는 `scripts/harness_env.py`(하네스 로더의 사본, 설치된 로더가 있으면 그것). 목록과 기본값은 `scripts/sllib/config.py` `DEFAULTS` 에 있다.
- 주요 키: `SESSION_LOG_HOME`, `SESSION_LOG_MODEL`(haiku), `SESSION_LOG_DISABLE`, `SESSION_LOG_RECORD_NONINTERACTIVE`(기본 꺼짐: `CLAUDE_CODE_ENTRYPOINT` 가 `sdk` 로 시작하는 `claude -p`·SDK 세션은 기록하지 않는다), `SESSION_LOG_COOLDOWN_MIN`(20), `SESSION_LOG_GROW_KB`(512), `SESSION_LOG_HANDOVER_CHARS`(800), `SESSION_LOG_HANDOVER_LAG_LINES`(400), `SESSION_LOG_HANDOVER_LIVE_MIN`(10), `SESSION_LOG_PRECOMPACT_CHARS`(3000), `SESSION_LOG_COMPACT_INSTRUCTIONS`(on), `SESSION_LOG_PENDING_STRONG_COUNT`(5), `SESSION_LOG_PENDING_STRONG_DAYS`(7), `SESSION_LOG_HOME_NUDGE_COUNT`(3), `SESSION_LOG_HOME_NUDGE_DAYS`(3), `SESSION_LOG_READ_WARN_KB`(16), `SESSION_LOG_MAX_PARALLEL`(2).
- harness.env 제안(하네스 담당이 정본에 넣을 때): `SESSION_LOG_HOME=${XDG_DATA_HOME:-~/.local/share}/session-log` 를 명시하고, 필요하면 `SESSION_LOG_MODEL=haiku` 를 둔다. 다른 sandbox 로 옮길 때는 이 두 키만 본다.

## coderag 연결 (메모)
- 외부 저장소의 `records/` 는 coderag frontmatter 계약(§11.4, §17)을 지킨다. 그래서 global 계층 문서 루트로 색인할 수 있다.
- 예: global 설정에 `[[contexts.docs.targets]] module = "session-log" source = "~/.local/share/session-log" options = { exclude = [".state"] }`.
  - 저장소별로 나누려면 `source = "…/session-log/<project-key>/records"`.
  - 점 디렉터리는 기본 제외라 `.state/` 는 저절로 빠진다.
- 가져간 사본은 저장소 보관 폴더에 있어 coderag 의 프로젝트 문서 루트에서 잡힌다(점 디렉터리 `.claude/sessions/` 는 설정에 따라).

## 의존성과 이식성
- `python3`(표준 라이브러리만, `-I` 로 실행), `claude`(PATH), `git`(선택: import 커밋 조회), `setsid`(없으면 `start_new_session`).
- 경로를 하드코딩하지 않는다. 트랜스크립트는 stdin `transcript_path` 로 받는다. 소급(backfill)만 `${CLAUDE_CONFIG_DIR:-~/.claude}/projects` 를 본다.

## 테스트
- `python3 -I plugins/qwreey-sessions/tests/test_session_log.py`: 단위 테스트. 가짜 `claude`(`plugins/qwreey-sessions/tests/fixtures/fake_claude.py`)를 쓰고 비용은 0이다.
- `plugins/qwreey-sessions/tests/e2e.sh [--auto-compact]`: 임시 git 프로젝트에서 `claude -p --plugin-dir` 로 실제 훅과 haiku 를 돌린다. 결과는 `$T/report.json` 에 남는다. 모델이 실제로 본 문자열은 e2e 세션 트랜스크립트에서 뽑는다.
