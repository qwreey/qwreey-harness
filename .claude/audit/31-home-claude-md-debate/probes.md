# .claude/audit/31 프로브와 구현 결과 (2026-11-11, Claude Code 2.1.316, sonnet)

파일은 /tmp/probe31, /tmp/e2e (저장소 밖). 비용: 프로브 약 $0.71 (예산 $0.5 초과: 3번 n=5 가 $0.375), 구현 e2e 약 $0.25. `--dangerously-skip-permissions` 는 쓰지 않았다.

## 1. 플러그인 스킬명과 agent_id: 확인
`--plugin-dir /tmp/probe31/plug`(플러그인 `pp`, 스킬 `ws`)로 시험했다.
- PostToolUse(Skill): `tool_input = {"skill": "pp:ws"}`, `tool_response.commandName = "pp:ws"`. 즉 `<플러그인>:<스킬>` 형식.
- 서브에이전트 안에서 부르면 같은 훅 입력에 `agent_id`(예: `ae503326be1b2870a`)와 `agent_type` 이 함께 온다. 메인은 `agent_id` 가 없다.
- 슬래시 `/pp:ws`: UserPromptExpansion `command_name: "pp:ws"`, `command_source: "plugin"`, PostToolUse(Skill) 는 없다.
- 게이트는 `^([\w.-]+:)?workspace$` 로 감지한다(q:workspace, 단독 스킬 workspace).

## 2. 명령 분류기: 기존 분류기는 형제 경로 쓰기를 대부분 놓친다
기존 bash-bypass-reminder 의 쓰기 판정(`INPLACE` 또는 `REDIRECT`)은 경로를 보지 않고, 코드 확장자 리다이렉트와 `sed -i`/`patch`/`git apply` 만 쓰기로 본다. 새 분류기(`plugins/q/scripts/wslib.py classify_bash`)는 `cd` 추적, `git -C`, 쓰기 동사(rm, mv, cp, touch, mkdir, tee ...), git 변경 하위 명령, 스크립트 쓰기 패턴을 본다. 작업공간 /code/Projects, 세션 저장소 claude-doctor.

| 구분 | 명령 | 기존 | 새 |
|---|---|---|---|
| 쓰기 | `cd /code/Projects/quad && sed -i ... src/x.luau` | 잡음(경로는 안 봄) | write:quad |
| 쓰기 | `sed -i ... /code/Projects/stl-luau/README.md` | 잡음 | write |
| 쓰기 | `echo hi > /code/Projects/rbvm/notes.txt` | **미탐**(.txt 는 코드 확장자 밖) | write |
| 쓰기 | `cd ../rbvm && echo hi >> NOTES` | **미탐** | write |
| 쓰기 | `rm -rf /code/Projects/tbox/build` | **미탐** | write |
| 쓰기 | `cd /code/Projects/mrow && git commit -am wip` | **미탐** | write |
| 쓰기 | `git -C /code/Projects/quad checkout -b x` | **미탐** | write |
| 쓰기 | `python3 -c "open('/code/Projects/coderag/a.py','w')..."` | **미탐** | write |
| 쓰기 | `cp ./notes.md /code/Projects/claude-doctor/packs/luau-kb/notes.md` | **미탐** | write |
| 쓰기 | `cd /code/Projects/vitrine && touch foo.go` | **미탐** | write |
| 읽기 | 위 9개 읽기 명령(cat, ls, git log, grep, sed -n, cd+cat, cp 소스만, python 스크립트 실행) | 오탐 0 | read 9/9, 오탐(쓰기로 오인) 0 |
| 읽기 | `cat README.md \| head` | 0 | None(형제 아님) |

- 기존: 쓰기 10개 중 2개만 잡음(미탐 8). 새: 10/10. 읽기 쪽 오탐은 양쪽 0. 읽기 9개를 넣었다(10번째는 형제와 무관한 `cat README.md`).
- 기존 분류기를 import 해서 재사용하지 않았다: 판정이 `main()` 안에 있고 경로 정보가 없다.
- 알려진 한계: 변수·서브셸·`xargs`·`bash -c "..."` 안의 경로, 심볼릭 링크는 못 잡는다. 인터프리터는 `write|open(…'w')|unlink|rmtree|rename` 같은 낱말이 있어야 쓰기로 본다. 못 잡은 쓰기는 읽기 warn 으로 떨어진다(막히지 않음).

## 3. description 만으로 먼저 로드하는 비율: 5/5
게이트 훅 없이(`plug2`), description 은 "Load before reading or changing any repo other than the current one: ...". 형제 저장소를 읽는 과제 5개(문구를 달리함), sonnet, `-p`. 5번 모두 첫 도구가 `Skill q:workspace` 였고 그 뒤에 Read/Bash 가 왔다.
- 한계: `-p` 의 스킬 목록은 짧다. 실제 세션은 스킬이 수십 개라 비율이 낮을 수 있다. 쓰기 deny 는 그래서 필요하다.
- e2e 1회차(게이트 있음, "승인됨" 이라고 말해 준 과제)에서도 모델이 먼저 로드했다.

## 4. auto 모드의 프로젝트 밖 편집: 권한 확인이 뜨지 않는다
`--permission-mode auto`, cwd /tmp/probe31/proj, 대상 /tmp/probe31/other/f.txt. 두 번 시험: `--allowedTools Read Edit` 와 `--allowedTools Read`(Edit 허용 없음). 둘 다 확인 요청 없이 Edit 성공, `permission_denials: []`. (훅 입력의 `permission_mode` 도 "auto" 였다.) 따라서 권한 시스템은 형제 저장소 쓰기를 막지 않고 게이트 훅이 유일한 방어선이다.

## 5. 최종 본문 토큰 실측
`claude -p ok --model sonnet --system-prompt <본문> --tools "" --setting-sources ""`: 기준선(빈 system prompt) input 512, 본문 input 2 + cache_creation 1,513 = 1,515. 차이 **약 1,003 토큰**(2,840 B). 추정 1.0k 와 일치. 이전 설치본(약 2.8k 토큰대, .claude/audit/28)보다 약 1.8k 적다.

## 구현 결과
- 게이트: `plugins/q/scripts/workspace_gate.py` + `wslib.py`, `hooks/hooks.json` 에 PreToolUse(Edit|Write|MultiEdit|NotebookEdit|Read|Grep|Glob|Bash), PostToolUse(Skill), UserPromptExpansion, SessionStart(compact) 추가.
- 스킬: `plugins/q/skills/workspace/SKILL.md`(frontmatter `allowed-tools: Bash(python3 -I *map.py*)` 가 있어야 `` !`...` `` 지도가 주입된다. 없으면 모델이 직접 실행함), `scripts/map.py`.
- e2e(/tmp/e2e 흉내 작업공간, `-p`, 플러그인 사본에 게이트 훅만): Read -> Edit 가 `PreToolUse:Edit hook error: <harness-hook name="workspace-gate" level="action">` 로 deny -> `Skill q:workspace` -> 지도 주입 확인 -> Edit 재시도 통과, 파일이 바뀜. deny.log 에 기록됨.
- compact 회차: 하네스 `compact_epoch` 의 `$TMPDIR/claude-compact-epoch/<sid>` 를 읽기만 하고(q 플러그인은 하네스 lib 를 import 하지 않는 기존 방침), 그 파일을 올리는 rearm-on-compact 가 없는 기기를 위해 SessionStart(compact) 에서 표시 파일을 지운다. 단위 테스트로 둘 다 확인.
- qwreey-advisor fresh-advisor 본문에는 이미 "Decide each finding: accepted / rejected ... tell the user in 1-3 lines" 가 있어 바꾸지 않았다.
- 본문 수정이 필요해 보이는 곳: 없음. (참고: 본문의 "Before touching one, load the `q:workspace` skill" 는 읽기에도 적용되는 문구라, 읽기는 막지 않고 한 번 warn 만 하는 게이트와 약하게 어긋난다. 의도된 차이로 보고 고치지 않음.)

## 사용자에게 물을 것
옛 home CLAUDE.md 형제 지도에 손으로 쓴 요점이 있었다. 지도가 각 저장소 CLAUDE.md 의 첫 줄을 읽게 되었으므로, 아래를 각 저장소 CLAUDE.md 로 옮길지(해당 저장소 세션이 고치는 것이 맞다):
1. quad: "가장 큰 Luau 타입 한계 연구 (`.claude/base/typing-limits.md`)" 포인터.
2. stl-luau: "성능 실측 (`.claude/base/perf-measurements.md`)" 포인터.
3. rbvm: "Studio 엔진 동작 기록" 포인터.
4. luau-kb: "Luau/Roblox 공유 지식 정본(스킬·스니펫·typedefs)" 한 줄(kb 저장소는 지도에서 항상 맨 위라 CLAUDE.md 첫 줄이 곧 설명).
5. claude-doctor: "하네스 정본·진단(`PLAN.md`, `/q:doctor`), 외부 프로젝트 반입 감사(`intake/`)" 포인터(이 저장소 CLAUDE.md 는 이미 "Pointers only" 첫 줄).
6. coderag: 지식 계층(global / pack / project) 설명이 CLAUDE.md 첫 줄에 오는지(지금 첫 줄은 "작업 시작 전 ... 먼저 읽어라" 인용문).
7. 지도 첫 줄이 어색한 저장소(nekolog, test 는 설명 없음, quad-v1 "문서화된 사용법", VideoSync 문장이 120자에서 잘림): 첫 줄을 한 문장 요약으로 쓸지.
