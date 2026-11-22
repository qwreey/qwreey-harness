---
format: 1
title: 68. 훅 바이너리 자리 debate 종합
description: 훅 바이너리를 플러그인에 실을지 PATH 에 깔지는 동료가 플러그인을 받는 길(claude.ai 조직 배포 대 마켓 CLI)에 달려 열어 두고, rtk·qx 꼴(setup 이 settings.json 에 훅을 적기)은 버리며, 어느 쪽이든 플러그인 폴더를 CLAUDE_PLUGIN_ROOT 로 찾게 먼저 고친다
---
# 68. 훅 바이너리 자리 debate 종합

> Snapshot 2026-11-22. May differ from now; check current files and git log before relying on it.

P(지금처럼 플러그인 `native/` 에 싣기)와 Q(PATH 에 한 벌 깔고 에이전트마다 붙이기), opus 2개, 1회전, 종합은 메인 세션. 판을 가르는 공식 문서 문장은 메인이 따로 다시 확인했다. 근거: `.claude/plan/rust-hook-backend.md`, audit 67, `.claude/base/harness-principles.md`, coderag 래퍼, rtk·qx 문서, Claude Code·Codex 공식 문서. 사용자(Q57): "c) 아직 모름, 둘 다 열어 둔다".

## Trigger
coderag 래퍼를 bash 내장만으로 고친 뒤(훅 하나 12.0 -> 4.6 ms, 바이너리 직접 1.1 ms) 사용자가 물었다: "그냥 local bin 에 넣던가 하는게 맞지 않나 ... rtk 같은 도구 보면 보통 바이너리를 그냥 로컬에 깔도록 하니까", "qx setup claude-code, qx setup codex 식으로 ... 우리가 만일 벤더 중립을 지킨다면 이런 다른 사람들의 접근들도 한번 보는것 좋을지도", "그럼 토론을 띄워볼래?".

## Facts both sides confirmed
메인이 공식 문서에서 다시 확인한 것은 따옴표로 적는다.
- claude.ai 조직 배포: "Organization sync reads the marketplace repository's default branch". 소스는 "each plugin source must be of type `github`, `url`, or `git-subdir`, or a relative path that starts with `./`"(`archive` 없음). "claude.ai rejects a plugin that has one"(맨 위 `bin/`). (claude.com/docs/plugins/org-sync)
- 실행 형식 훅: "Claude Code resolves `command` as an executable on `PATH` and spawns it directly with `args`". "On Windows, exec form requires `command` to resolve to a real executable such as a `.exe`". 확장자 없는 이름을 `.exe` 로 찾는지는 문서에 없다. (code.claude.com/docs/en/hooks)
- Codex: "If a plugin update changes a bundled script, Codex requires a new review even if the hook definition stays the same." Codex 도 플러그인 `hooks/hooks.json` 을 읽고 `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` 를 준다. (learn.chatgpt.com/docs/hooks.md)
- 플러그인 맨 위 `bin/` 은 Bash 도구의 PATH 에만 오른다. 훅 프로세스의 PATH 에는 없다(P 가 `/proc/<claude>/environ` 로 확인).
- settings.json 에 적은 훅에는 `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_PLUGIN_OPTION_*` 가 오지 않는다(plugins-reference). 우리 crate 10곳이 이것을 쓴다.
- `native/` 는 git 에서 빠져 있고(`.gitignore` 의 `plugins/*/native/`) 손으로 복사한다. 그래서 지금 동료가 설치하면 바이너리가 없고 Rust 훅은 아무것도 하지 않는다.
- 바이너리 여덟 개 합 15.4 MB, tar.gz 6.6 MB(이미 strip). `.exe` 이름의 바이너리도 Linux 에서 그대로 돈다(P 실측).
- 지금도 PATH 에 기대는 것이 있다: `python3` 이름, Windows 의 Git Bash(README).

## Accepted by both
- rtk·qx 꼴(`<tool> setup <agent>` 가 `~/.claude/settings.json` 에 훅을 적기)은 Claude Code 에 쓰지 않는다. 플러그인 옵션이 오지 않고, 플러그인마다 끄기와 관리자 `enabledPlugins` 배포를 잃으며, 이 저장소가 마이그레이션 0006 에서 걷어낸 길이다. rtk·qx 는 설정도 글도 없는 단일 도구라 그 꼴이 맞는다.
- 벤더 중립에 PATH 가 꼭 필요하지는 않다. 하위 명령 꼴 `<bin> hook <name>` 이 이미 에이전트와 무관하고, Codex 도 플러그인 hooks.json 을 받는다.
- 지연은 가르는 기준이 아니다. 래퍼 비용은 bash 탓이고 두 안 모두 래퍼가 없다.
- 바이너리가 없으면 어느 안이든 도구마다 막지 않는 훅 오류가 된다.
- coderag 의 사람용 CLI 는 PATH 가 맞다.

## Disagreements
| Issue | P | Q | Chosen and why |
|---|---|---|---|
| 바이너리 자리 | 플러그인 `native/<bin>.exe`(모든 OS 에서 `.exe`, hooks.json 하나) | PATH 에 한 벌, hooks.json 이 이름으로 부름 | 사용자(Q57 c): 동료가 받는 길이 정해질 때까지 열어 둔다 |
| 동료에게 보내는 법 | OS별 release zip(`archive` 소스, sha256), git 없어도 됨 | 설치 스크립트 한 줄과 OS 무관한 플러그인 하나 | 열어 둠. 조직 배포라면 `archive` 도 OS별 ref 도 못 쓴다(위 사실) |
| 판 어긋남 | 한 판으로 와서 생길 수 없다 | plugin.json `metadata` 의 최소 판, 낮으면 조용히 끝내고 한 번 알림 | P 가 구조로 낫다. Q 를 고르면 Q 의 장치를 쓴다 |
| coderag | 훅은 플러그인 안 바이너리, 모델은 스킬 본문의 `${CLAUDE_PLUGIN_ROOT}` 경로, 사람용 CLI 는 따로 PATH | 훅과 CLI 가 같은 PATH 바이너리, 래퍼와 맨 위 `bin/` 을 걷음 | 열어 둠. 두 쪽 모두 맨 위 `bin/` 래퍼는 조직 배포에서 거부되니 걷는다는 데 같다 |
| Codex | 같은 바이너리로 Codex 용 묶음을 필요할 때 만든다 | `setup codex` 를 나중에. 플러그인에 실으면 판마다 재승인 | 열어 둠. Codex 에 훅을 붙일 계획이 아직 없다 |

## Alternatives
| Option | Pros | Cons | Raised by |
|---|---|---|---|
| (1a) `native/` + OS별 ref 에 커밋 | 설치 단계 없음, 판이 같음 | 조직 배포는 기본 브랜치만 읽음, git 기록이 판마다 약 20 MB 늘어남 | current(audit 67) |
| (1b) `native/` + OS별 release zip(`archive`) | git 없이 설치, 판이 같음, git 기록이 늘지 않음 | 조직 배포가 받지 않음, OS별 마켓 파일, 실기기 확인 전 | P |
| (1c) `command` 플러그인 소스(설치된 도구가 플러그인 폴더를 내놓음) | 판이 구조로 맞음, 바이너리 하나 | 조직 배포가 받지 않음, 관리자가 끌 수 있음, Windows 는 copy 모드만 | P, Q |
| (2) PATH + 플러그인 hooks.json 이 이름으로 | 플러그인이 OS 와 무관, coderag CLI 와 같은 자리, LSP 플러그인의 공식 선례 | 설치 한 단계, 판 어긋남, GUI 로 띄운 Claude 의 PATH(추측), 이름 충돌(`q`) | Q |
| (3) PATH + `setup <agent>` 가 settings.json 에 | 에이전트마다 한 명령, `--uninstall` | 위 "Accepted by both" | 사용자 제시(rtk, qx) |
| (5) SessionStart 가 release 를 `CLAUDE_PLUGIN_DATA` 로 받음 | 문서가 권하는 꼴 | 네트워크와 셸, 첫 세션에 훅 없음, `.exe` 문제 그대로 | Q |
| (6) 다중 명령 바이너리 하나 | 15 MB 대신 하나, 데몬이 캐시 하나를 쥠 | 한 판이 모든 플러그인의 hooks.json 판을 받아야 함 | Q |

## Proposed wording
계획 `.claude/plan/rust-hook-backend.md` 열린 문제 1번의 바이너리 자리 문단을 갈음한다.
```
   - 바이너리 자리(audit 68, Q57 c: 열어 둔다): 동료가 플러그인을 받는 길에 달렸다. claude.ai 조직 배포는 기본 브랜치만 읽고 `archive` 소스와 맨 위 `bin/` 을 받지 않으므로, 그 길이면 플러그인에 싣되(바이너리를 기본 브랜치에 커밋하거나 다른 길을 0단계에서 찾는다) PATH 설치는 밀 수 없다. 마켓 CLI 면 (1b) 플러그인 `native/` + OS별 release zip 과 (2) PATH 에 한 벌 + hooks.json 이 이름으로 부르기가 둘 다 된다. rtk·qx 꼴(setup 이 settings.json 에 훅을 적기)은 플러그인 옵션이 오지 않아 쓰지 않는다. 0단계에서 잴 것: Windows 실행 형식이 확장자 없는 이름에서 `.exe` 를 찾나, 모든 OS 에서 `<bin>.exe` 이름이 되나, GUI·Cowork 로 띄운 Claude 의 PATH, 바이너리가 없을 때 사용자에게 보이는 것.
```

## Not accepted
- 지금 바로 한쪽으로 정하기: 판을 가르는 사실(동료가 받는 길, Windows 의 이름 찾기, Cowork 의 PATH)이 아직 없다. 어느 쪽이든 먼저 할 정리가 같다.
- (3) rtk·qx 꼴: 위 "Accepted by both".

## Fix regardless
- 플러그인 폴더를 `CLAUDE_PLUGIN_ROOT` 로 먼저 찾는다. proc-guard, workspace, conventions 가 바이너리 자리(exe_dir, argv[0])에서 위로 올라가 `plugin.json` 을 찾는다(`crates/qwreey-proc-guard/src/context.rs`, `crates/harness-hook/src/settings/mod.rs`). PATH 로 옮기면 깨지고, 플러그인에 실어도 환경 값이 더 확실하다. advisor, sessions 는 이미 그렇게 한다.
- qwreey-sessions 의 맨 위 `bin/session-log` 는 커밋되어 있어 이 플러그인은 조직 배포에서 거부된다. 옮기면 모델이 셸에서 `session-log` 를 부르는 길이 바뀌므로 사용자가 정한다.
- coderag 플러그인의 맨 위 `bin/` 래퍼도 같은 이유로 조직 배포에서 거부된다.

## For the user
1. 동료는 플러그인을 어떻게 받나: (a) claude.ai 조직 배포·Cowork (b) 마켓 CLI (c) 아직 모름. 답: c.
2. 동료 기기에 git 과 GitHub 계정이 있나(없으면 `archive` 나 조직 배포).
3. coderag CLI 를 동료가 셸에서 직접 쓰나.
4. Codex 에도 훅을 붙일 계획이 있나.
5. 바이너리를 하나로 합칠지, 그리고 PATH 에 오를 이름.
6. qwreey-sessions 의 맨 위 `bin/session-log` 를 옮길지.

## Next
1. `CLAUDE_PLUGIN_ROOT` 우선(위 Fix regardless 1), 대조로 출력이 그대로임을 확인.
2. 0단계 3(빈 바이너리로 배포 경로)에서 위 "잴 것"을 실기기로 잰다.
3. 동료가 받는 길이 정해지면 이 종합의 Disagreements 첫 줄을 정한다.
