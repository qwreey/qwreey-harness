---
title: session-log 훅과 /q:checkpoint·/q:import (q 플러그인) — 세션 기록 자동화
description: 훅이 트랜스크립트를 분리 프로세스에서 증분 요약하고 원문과 기계 대조해 저장소 밖 외부 저장소에 coderag 기록으로 남긴다. 저장소 메인 에이전트가 /q:import 로 받아 간다
keywords: [session-log, 세션 기록, PreCompact, SessionStart, handover, q:import, q:checkpoint, haiku, 외부 저장소, pending]
kind: reference
status: active
last_verified: 2026-11-10
---
# session-log 훅 (q 플러그인)

메인 세션이 아무것도 하지 않아도 세션 기록이 남게 한다. 설계 근거는 `drafts/session-log/DESIGN.md`, 조사·실측은 `audit/15-session-log.md`.

## 흐름
1. 훅이 트리거를 판단한다(PreCompact·SessionEnd 는 강제, PostToolUse·UserPromptSubmit 은 쿨다운 20분 + 512KB 증가).
2. `setsid -f` 로 분리한 워커(`scripts/cli.py flush`)가 바이트 오프셋부터 트랜스크립트를 줄이고(1~3%), 9만 자 구간마다 격리된 `claude -p --model haiku` 를 한 번 부른다.
   - 모델에게 도구를 주지 않는다(`--tools ""`). 파일 쓰기와 검증은 스크립트가 한다.
   - 격리: `--setting-sources ""`, `--no-session-persistence`, `--strict-mcp-config`, 빈 임시 cwd, `CLAUDECODE`·`CLAUDE_CODE_*` 제거, `SESSION_LOG_NESTED=1`(우리 훅은 이걸 보면 바로 끝난다).
3. 숫자·커밋 해시·사용자 인용을 그 구간의 원문 줄과 기계로 대조한다.
   - 원문에 없는 인용은 **뺀다**. 원문에 없는 숫자는 `⚠원문 불일치`, 근거 줄이 틀리면 `⚠근거 줄 다름` 을 붙인다.
   - 합계는 frontmatter `verify:` 에 남는다.
4. **외부 저장소**에 절을 덧붙인다. 저장소 안에는 아무것도 쓰지 않는다.
5. 다음 훅 기회에 메인 세션에 알린다. 저장소의 메인 에이전트가 `/q:import` 로 골라 받아 가고, 커밋은 그 에이전트가 한다.

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

기록 형식(coderag §11·§17·§21): frontmatter `title, description, keywords, kind: session, status, last_verified, session_id, project, project_root, source_transcript, summarizer, verify`.
절마다 `## <날짜 시각–시각> · <트리거>` 다음 메타 줄 `id: <sid8>-<n> · summary: … · note: L<a>–L<b>` 을 둔다. 그 아래 `### 요약 / 사용자 지시와 정정 / 결정 / 바뀐 파일과 커밋 / 실측 수치 / 실패한 시도 / 미해결과 다음 단계` 가 오고, 항목마다 `(L…)` 근거 줄을 단다.

## 알림 (모델에게 들어가는 영어, `<harness-hook name="session-log" level=…>`)
| 때 | 훅 | level | 내용 |
|---|---|---|---|
| 요약을 시작함(쿨다운 트리거) | PostToolUse·UserPromptSubmit | info | 구간과 "끝나면 알린다" |
| 요약이 끝남 | 다음 PostToolUse·UserPromptSubmit 1회 | info | 새 절 수, 기록 경로, 대조 실패 수, pending 수 |
| 세션 시작 | SessionStart | info / warn·action | 인계(직전 다른 세션 또는 resume 이면 이 세션의 미해결, ≤800자) + pending + 찾는 법 한 줄 |
| compact 뒤 | SessionStart(compact) | info / warn | 이 세션 기록 경로 + pending(새 회차라 다시) |
| commit 직전 | PreToolUse(Bash, `git … commit`) | warn·action | pending 과 "같은 커밋에 넣기 좋음"(막지 않음) |
| 인계·정리 | UserPromptSubmit(`/handover`·`/q:checkpoint`·인계 낱말), PreToolUse(Skill handover) | warn·action | pending |
| compact 직전 | PreCompact(manual·auto) stdout | warn | 상기: 사용자 지시 원문, 아직 기록 안 된 최근 사용자 발언, 결정, 미해결, 끝난 일, 기록 경로 |

- dedup 단위는 **(session_id, compact 회차, 트리거)** 다.
  - 회차는 PreCompact 가 세운 표지를 SessionStart(compact)·PostCompact 중 먼저 온 쪽이 소비하며 올린다. 그래서 한 compact 에 한 번 오른다.
  - 하네스 `~/.claude/lib/compact_epoch.py` 와 같은 규칙이지만 import 하지 않는다. 하네스가 없어도 돈다.
- pending 이 `SESSION_LOG_PENDING_STRONG_COUNT`(5)개 이상이거나 가장 오래된 것이 `…_DAYS`(7)일 이상이면 level=action 과 강한 문구를 쓴다.
- 주입 안전
  - 인계와 상기에는 구조화된 항목만 넣는다: 개수, 경로, ⚠ 없는 미해결·결정 제목(110자), 대조를 통과한 사용자 인용.
  - 자유 텍스트 요약(`### 요약`)은 넣지 않는다.
  - `<`·`>` 는 `‹`·`›` 로 바꾼다.
- 한 출력에 알림이 여럿이면 태그 하나에 가장 높은 level 을 단다(규약 `HOOK-MESSAGES.md`).
- 메시지 문자열은 모두 `scripts/sllib/messages.py` 에 있다.

## 받아 가기
```
session-log pending                     # rid  ~토큰  절 수  생성일  [⚠대조 실패] + 요약 한 줄
session-log show <rid> [--section N]
session-log import <rid…> [--to .claude/session/] [--force]   # 복사 + imported
session-log import <rid…> --merged-into <path>                # 저장소 관례대로 합쳤으면 표시만
session-log dismiss <rid…> [--reason …]
session-log status                      # 세션별 오프셋·비용·실패, imported 기록의 커밋(git log 로 찾아 채움)
session-log flush [--force] [--wait]    # 지금 요약(/q:checkpoint)
session-log backfill --plan plan.json [--budget 4] [--dry-run]
```
- `bin/session-log` 이 PATH 에 없으면 `"${CLAUDE_PLUGIN_ROOT}/bin/session-log"` 로 부른다.
- 가져간 뒤 새 절이 붙으면 다시 pending 이 된다.
- 스킬: `/q:import`(목록을 보고 저장소 관례대로 합치거나 고른다), `/q:checkpoint`(지금 flush 하고 새 미해결·지시만 본다).

## 설정
우선순위는 환경 변수 > `harness.env`(`$HARNESS_ENV` → `$CLAUDE_CONFIG_DIR/harness.env` → `~/.claude/harness.env`, `SESSION_LOG_*` 키만) > 기본값이다. 목록과 기본값은 `scripts/sllib/config.py` `DEFAULTS` 에 있다.
- 주요 키: `SESSION_LOG_HOME`, `SESSION_LOG_MODEL`(haiku), `SESSION_LOG_DISABLE`, `SESSION_LOG_COOLDOWN_MIN`(20), `SESSION_LOG_GROW_KB`(512), `SESSION_LOG_HANDOVER_CHARS`(800), `SESSION_LOG_PRECOMPACT_CHARS`(3000), `SESSION_LOG_PENDING_STRONG_COUNT`(5), `SESSION_LOG_PENDING_STRONG_DAYS`(7), `SESSION_LOG_MAX_PARALLEL`(2).
- harness.env 제안(하네스 담당이 정본에 넣을 때): `SESSION_LOG_HOME=${XDG_DATA_HOME:-~/.local/share}/session-log` 를 명시하고, 필요하면 `SESSION_LOG_MODEL=haiku` 를 둔다. 다른 sandbox 로 옮길 때는 이 두 키만 본다.

## coderag 연결 (메모)
- 외부 저장소의 `records/` 는 coderag frontmatter 계약(§11.4, §17)을 지킨다. 그래서 global 계층 문서 루트로 색인할 수 있다.
- 예: global 설정에 `[[contexts.docs.targets]] module = "session-log" source = "~/.local/share/session-log" options = { exclude = [".state"] }`.
  - 저장소별로 나누려면 `source = "…/session-log/<project-key>/records"`.
  - 점 디렉터리는 기본 제외라 `.state/` 는 저절로 빠진다.
- 가져간 사본은 저장소 `.claude/` 아래에 있으므로 coderag 의 프로젝트 문서 루트에서 그대로 잡힌다.

## 의존성과 이식성
- `python3`(표준 라이브러리만, `-I` 로 실행), `claude`(PATH), `git`(선택: import 커밋 조회), `setsid`(없으면 `start_new_session`).
- 경로를 하드코딩하지 않는다. 트랜스크립트는 stdin `transcript_path` 로 받는다. 소급(backfill)만 `${CLAUDE_CONFIG_DIR:-~/.claude}/projects` 를 본다.

## 테스트
- `python3 -I plugins/q/tests/test_session_log.py`: 단위 테스트. 가짜 `claude`(`plugins/q/tests/fake_claude.py`)를 쓰고 비용은 0이다.
- `plugins/q/tests/e2e.sh [--auto-compact]`: 임시 git 프로젝트에서 `claude -p --plugin-dir` 로 실제 훅과 haiku 를 돌린다. 결과는 `$T/report.json` 에 남는다. 모델이 실제로 본 문자열은 e2e 세션 트랜스크립트에서 뽑는다.
