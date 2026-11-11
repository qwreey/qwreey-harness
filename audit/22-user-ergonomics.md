# 22. 사용자 가시성(statusline, 위쪽 배치, 테마, 응답 표시)

> **2026-11-11:** 사용자 가시성(mod·테마·표시) 작업은 별도 저장소 `/code/Projects/quietcode-claude` 로 옮겼다(q-ui 시제품 포함, 이 문서의 사본은 그쪽 `docs/research-user-ergonomics.md`). 이 문서는 이력으로 남긴다. statusline 스크립트는 away 한도 파일 때문에 claude-doctor 에 남는다.

- 날짜: 2026-11-11. 로컬 Claude Code 2.1.316, 문서는 `/tmp/ccdocs/*.md` 사본과 code.claude.com/docs 원문(WebFetch)이다.
- 표기: **할 수 있음 / 없음 / 미확인**. 출처는 문서 파일명이다. [실측]은 이번에 돌려 본 것이다.
- 구현: `home/.claude/statusline/harness-status.py`(정본), `home/.claude/harness.env`(주석 한 블록), `hooks/tests/test-subagent-slots.py`(132/132 통과). 실제 `~/.claude` 에는 반영하지 않았다.

## 0. 요지
- statusline 의 한도·리셋 표시는 공식 입력 필드로 충분하다(`/usage` 대체 가능). 시제품은 한 줄이 기본이다.
- **statusline 위치(위쪽)를 옮기는 설정은 없다.** 공식으로 허용되는 위쪽 배치는 터미널 탭 제목(OSC 0/2)이다. 훅이 `terminalSequence` 로 보낸다.
- 아래쪽 혼잡을 줄이는 공식 설정은 여럿 있다(§3). effort 줄 자체의 커스텀은 설정이 **없다**.
- 사용자 정의 테마는 **있다**(`~/.claude/themes/*.json`, 색 토큰 override).
- markdown 은 렌더러가 지원한다. 응답 습관은 CLAUDE.md 몇 줄로 개선한다(§6).

## 1. ui-themes (yugal1107/ui-themes) — 읽기만 했다(WebFetch, 실행·설치 안 함)
- 라이선스 MIT(2026, Yugal Burde). 플러그인: `.claude-plugin/`, `hooks/`, `statusline/`, `themes/`(JSON 3종), `docs/`, `tests/`.
- 하는 일: 프롬프트·응답을 색 박스로 그리고(함수 훅 API, 문서에서 "초기 접근"이라 했다), 응답 markdown 요소를 테마 색으로 칠하고, 한 줄 statusline 을 준다. `/ui-theme` 명령. 설정은 사용자가 `statusLine` 항목을 손으로 넣는다.
- statusline: 모델·폴더·git 브랜치(더러우면 다른 색)·컨텍스트·5h/7d 한도 한 줄. jq 와 Nerd Font 필요. 테마 JSON 의 `statusline` 블록이 모델별 색과 ok/warn/hot/muted/sep 색을 정한다.
- 스크립트는 한 번 복사해 두고 업데이트가 덮어쓰지 않는다(사용자 권한으로 매번 실행되기 때문). 새 버전은 시작 때 알리고 `.bak` 을 남기며 적용한다.
- **빌린 것:** (1) 한 줄 구성(모델·폴더·브랜치·컨텍스트·한도), (2) 더러움 표시, (3) ok/warn/hot 문턱 색, (4) 구분자·보조 글자는 흐리게, (5) "스크립트는 덮어쓰지 않고 알린 뒤 적용" 원칙(우리는 home-sync diff/apply 가 같은 역할).
- **안 빌린 것:** 박스 렌더링(함수 훅 API 가 초기 접근이고 우리 하네스 범위 밖), jq 의존(우리는 python), `/ui-theme` 명령 체계. 박스는 `/theme` 사용자 정의 테마(§5)와 mods(§4)로 대체 가능한 부분이 있다.
- 설치는 사용자 확인 사항이다(서드파티 코드가 매번 실행된다).

## 2. statusline 입력과 동작 (statusline.md)
| 항목 | 분류 | 근거 |
|---|---|---|
| `rate_limits.five_hour/seven_day.used_percentage`(0~100), `resets_at`(epoch 초) | 할 수 있음 | statusline.md Available data. 구독자(Pro/Max/Ultra)만, 첫 API 응답 뒤에만, 창마다 따로 없을 수 있음 |
| 구독자가 아닐 때의 한도 | 없음 | rate_limits 가 없다. 그래서 비용 USD 로 대체한다 |
| `effort.level`(low~max), `thinking.enabled` | 할 수 있음 | 모델이 effort 를 지원할 때만 있다 |
| `cost.total_cost_usd`, `context_window.used_percentage` | 할 수 있음 | |
| `workspace.current_dir/project_dir/git_worktree/repo`, `worktree.*`, `vim.mode`, `output_style.name`, `agent.name` | 할 수 있음 | git 브랜치 필드는 **없다**(`worktree.branch` 는 worktree 세션에만). 그래서 `.git/HEAD` 를 직접 읽는다 |
| 여러 줄, ANSI 색, OSC 8 링크 | 할 수 있음 | "What your script can output" |
| `padding`, `refreshInterval`(최소 1초), `hideVimModeIndicator` | 할 수 있음 | Manually configure |
| 터미널 폭 | 할 수 있음 | `COLUMNS`·`LINES` 환경 변수(tput 는 안 된다) |
| 출력이 비었거나 비정상 종료 | 동작 | 줄이 빈다. 그래서 `STYLE=off` 는 빈 출력이다. 신뢰하지 않은 폴더에서도 비어 있다 |
| 업데이트 시점 | 동작 | 새 응답, /compact, 권한 모드 변경, vim 토글, 300ms 디바운스, 실행 중이면 이전 실행 취소 |
| 권한 프롬프트·도움말 중에는 숨음 | 동작 | |
| `subagentStatusLine`: 서브에이전트 패널의 각 행 본문을 커스텀, 빈 `content` 로 행 숨김 | 할 수 있음 | statusline.md "Subagent status lines". 아래쪽 패널 혼잡 완화에 쓸 수 있다(미시도) |

## 3. 아래쪽 혼잡을 줄이는 공식 설정
| 대상 | 분류 | 방법과 출처 |
|---|---|---|
| spinner 팁 | 할 수 있음 | `spinnerTipsEnabled:false`, `spinnerTipsOverride`, `spinnerVerbs` (settings-reference) |
| "Cooked for" 소요 시간 | 할 수 있음 | `showTurnDuration:false` |
| PR 상태 배지(푸터) | 할 수 있음 | `prStatusFooterEnabled:false` (interactive-mode PR review status) |
| 서브에이전트 패널의 행 | 일부 | 행 본문 커스텀·숨김은 `subagentStatusLine`. 패널 자체를 끄는 설정은 **미확인**(문서에서 못 찾음) |
| vim 모드 표시 | 할 수 있음 | `hideVimModeIndicator`(statusLine 안) |
| 권한 모드(auto mode) 줄 | **미확인** | 끄는 설정을 못 찾았다. 색은 theme 토큰(`autoAccept`, `planMode`, `warning`)로 바꿀 수 있다. mods 의 `SessionMode` 렌더 사이트가 있으나 §4 |
| update available 줄 | **미확인** | 숨기는 설정을 못 찾았다. 자동 업데이트 쪽 설정(`minimumVersion` 등)은 알림이 아니라 설치 정책이다 |
| 시작 로고의 작업 디렉터리 | 할 수 있음 | `CLAUDE_CODE_HIDE_CWD=1`(env-vars). 화면 공유용 |
| 전체 대화 요약 보기 | 할 수 있음 | `viewMode:"focus"`(마지막 프롬프트·도구 한 줄 요약·최종 응답만; 전체화면 렌더러 필요), `/focus` |
| 애니메이션 | 할 수 있음 | `prefersReducedMotion:true` |
| 렌더러 | 할 수 있음 | `tui:"fullscreen"`(입력창이 하단 고정, 깜빡임 없음)·`default`. 전체화면은 연구 미리보기. 문서상 2026-05-06 이후 사용자는 기본이 전체화면 |
| 시도하지 않은 것 | | 위 항목 대부분을 실제로 켜 보지는 않았다(문서 근거만) |

## 4. 위쪽 배치
| 방법 | 분류 | 근거 |
|---|---|---|
| statusline 위치 설정 | **없음** | statusline.md: "appears at the bottom of the interface". 위치 키가 없다 |
| 터미널 탭·창 제목(OSC 0/2) | **할 수 있음, 공식 허용** | hooks.md: 훅 JSON 출력의 `terminalSequence` 는 OSC `0`/`1`/`2`(창·아이콘 제목), 9, 99, 777, BEL 만 허용한다. 그 밖(CSI, OSC 8, OSC 52, OSC 1337)은 거부. 대화형 세션에서만, async 훅이 아닌 훅만. `/dev/tty` 는 훅에서 못 쓴다 |
| statusline 출력으로 제목 설정 | **미확인(권장 안 함)** | 출력은 Claude Code 가 캡처해 그린다. OSC 를 통과시키는지 문서에 없다 |
| Claude Code 자체의 제목 | 할 수 있음 | 기본은 대화에서 생성한 제목. `/rename`·`--name`·훅 `sessionTitle`(SessionStart)로 세션 이름을 정할 수 있다. `terminalTitleFromRename:false` 는 이름이 탭을 바꾸지 않게 한다. `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` 은 제목 갱신을 전부 끈다. 같은 제목을 Claude Code 도 쓰므로 **충돌**한다(우리가 쓴 제목을 Claude Code 가 덮어쓸 수 있다. 미실측) |
| 세션 헤더("with medium effort" 포함 시작 화면) 커스텀 | **없음(설정)** | 설정 키를 못 찾았다. 숨기는 것은 `CLAUDE_CODE_HIDE_CWD` 뿐 |
| mods(플러그인 `ui.render` 훅) | 할 수 있음, 단 위쪽은 아님 | plugins/mods/interface·reference. 렌더 사이트: `Pane`(오른쪽 사이드바, 좁으면 프롬프트 위), `AbovePrompt`(프롬프트 위 띠), 토스트(트랜스크립트 오른쪽 위), `Placed`(트랜스크립트 안 행), `Spinner`, `UserMessage`, `AssistantMessage`, `ToolUse*`, `TurnDuration`, `SessionMode`, `PromptHint`. 화면 맨 위 고정 헤더 사이트는 없다. 참고 문서의 "Entries cover CLI as of v2.1.290". 안정성(실험 여부)은 **미확인** |
| 전체화면에서 스크롤하면 맨 위에 최근 프롬프트 한 줄 | 동작 | fullscreen.md. 설정 아님 |

결론: 프로젝트·브랜치·한도를 위쪽에 두려면 **탭 제목**이 유일한 공식 경로다. 구현은 훅(`UserPromptSubmit`/`Stop`/`SessionStart`)이 `{"terminalSequence":"\e]2;proj (branch) 5h 20%\a"}` 를 내는 형태다. 이 훅은 정본 `hooks/` 밖의 새 파일이라 이번 범위(statusline·env·테스트·문서)에서 만들지 않고 **제안만** 한다. 한도 값은 이미 `<sid>.limits.json` 에 있어 훅이 읽을 수 있다. 터미널이 탭 제목을 보이지 않는 구성(일부 tmux, 전체화면 터미널)에서는 소용없고, Claude Code 자체 제목과 충돌할 수 있다(§4 표).

## 5. effort 표시, 테마
- **effort 표시 줄 커스텀: 설정 없음.** 세션 헤더의 "with low effort" 문구는 effort 설정에서 온다(model-config.md). 표시를 끄거나 바꾸는 키는 못 찾았다. 값은 `effortLevel`, `modelSettings`, `maxEffortLevel`, `/effort` 로 정하고, statusline 의 `effort.level` 로 우리가 따로 보여 줄 수는 있다(시제품이 한다). `effortUltra` 색 토큰은 `ultracode` 태그 색만 바꾼다.
- **사용자 정의 테마: 있음**(terminal-config.md). `/theme` → "New custom theme…" 또는 `~/.claude/themes/<slug>.json`. 필드 `name`, `base`(dark, light, *-daltonized, *-ansi), `overrides`(색 토큰). 색 값 `#rrggbb`, `#rgb`, `rgb(r,g,b)`, `ansi256(n)`, `ansi:<name>`. 잘못된 값은 무시한다. 파일을 감시하다 바로 반영한다. `settings.json` 의 `theme: "custom:<slug>"`. 플러그인이 테마를 실을 수도 있다.
- 읽기에 직접 도움 되는 토큰: `claude`(어시스턴트 라벨·스피너), `userMessageBackground`(내 메시지 배경, 기본·전체화면 둘 다), `briefLabelYou/Claude`, `inactive`, `subtle`, `success/error/warning`, `diff*`, `promptBorder`, `rate_limit_fill/empty`(`/usage` 막대 색), `*_FOR_SUBAGENTS_ONLY`. **본문 markdown 요소(제목·굵게·목록 표시)의 색 토큰은 문서에 없다(미확인)**. ui-themes 가 응답 markdown 을 칠하는 것은 함수 훅/mods 경로로 보인다.
- 설치 범위: 테마 파일은 사용자 취향이라 하네스가 넣지 않는다. 필요하면 예시 JSON 을 제안한다.

## 6. markdown 렌더링과 응답 습관
- 렌더러가 다루는 요소: 문서에서 확인된 것은 문단, 제목, 목록, 인용(`maxProseWidth` 가 이 요소들을 폭 제한하고 표·코드 블록은 전체 폭), 표, 코드 블록(구문 강조는 `syntaxHighlightingDisabled` 로 끔), 취소선(`CLAUDE_CODE_FORCE_STRIKETHROUGH`). **굵게·기울임·링크·제목 글자 색의 구체 규칙은 문서에 없다(미확인).** 사용자가 본 "`-` 와 무색"은 목록이 문자 그대로 보이는 현상으로 보이며, 이 환경에서 직접 재현해 확인하지는 않았다(미실측).
- 폭: `maxProseWidth`(40 이상, 2.1.282+)로 넓은 터미널에서 줄 길이를 제한하면 읽기 쉽다(문서 근거).
- 복사: 전체화면에서 `c`(전사 모드 등) 는 원본 markdown 복사(interactive-mode.md).
- **output style**(output-styles.md): 내장 Proactive·Concise·Explanatory·Learning, 사용자 정의 `~/.claude/output-styles/*.md`. `outputStyle` 설정.
  - 장점: 세션 전체의 형식을 한 곳에서 정하고 `/output-style` 로 켜고 끈다. Concise 는 결론을 첫 문장에 둔다.
  - 단점: 매 요청에 지시가 붙는다(캐시로 완화되나 바꾼 뒤 첫 요청은 캐시 비용). 커스텀 스타일은 `keep-coding-instructions: true` 가 없으면 코딩 지침을 뺀다. 서브에이전트에는 적용되지 않는다. 지시일 뿐 강제가 아니다.
  - 판단: 형식 선호 몇 줄은 CLAUDE.md 가 더 싸고 단순하다. output style 은 응답 전체의 톤을 바꾸고 싶을 때만.
- **CLAUDE.md 제안(정본에 넣지 않음, 3줄):**

```markdown
## 응답 형식 (터미널에서 읽기)
- 결론·요청한 답을 첫 문단에 둔다. 긴 응답은 짧은 `##` 제목과 3~7개 이하 목록으로 나누고, 비교(3열 이하)와 값 목록에만 표를 쓴다.
- 핵심 용어·경로·명령만 굵게/백틱으로 하고, 한 항목이 두 줄을 넘으면 목록 대신 문단으로 쓴다. 코드·명령은 언어를 적은 코드 블록에 둔다.
```

  CLAUDE.md 정본은 50줄 상한이라 위 2개 불릿(제목 포함 3줄)만 제안한다.

## 7. 시제품: harness-status.py

### 설정(harness.env, 접두 `HARNESS_STATUSLINE_`)
환경 변수 > 저장소 `<저장소>/.claude/harness.env` > 사용자 `~/.claude/harness.env` > 기본값. [실측] 저장소 파일이 스타일을 바꾼다(테스트).
| 키 | 값 | 기본 |
|---|---|---|
| `STYLE` | `plain` / `nerd` / `minimal` / `off` | `plain`(회사 배포: 폰트·터미널이 달라도 안전) |
| `LINES` | `1` / `2` | `1`(아래쪽이 혼잡하므로) |
| `COST` | `always`(구독 여부와 무관하게 표시) / `auto`(구독자면 숨김) / `never` | `always` (2026-11-11 사용자: 구독제와 무관한 정량적 작업량 지표라 늘 보인다) |
| `WARN_PCT`, `HOT_PCT` | 색 문턱 | 70, 90 |

사용자 본인은 `harness.env` 에서 `HARNESS_STATUSLINE_STYLE=nerd` 로 바꾸면 된다(현재 주석 처리된 한 줄이다, 사용자 선택이므로 켜지 않았다). `NO_COLOR` 가 있으면 색을 쓰지 않는다. `off` 도 한도 파일은 계속 쓴다([실측] 테스트).

### 담는 정보와 생략 순서(뒤에서부터 통째로)
1) 프로젝트명·브랜치(더러우면 `*`) 2) 모델·effort(입력에 있을 때) 3) 컨텍스트 % 4) 한도 5h·wk·가장 가까운 리셋까지 남은 시간 다음에 비용(목록가 환산, 서브에이전트 포함) 5) 실행 중 서브에이전트(0이면 숨김) 6) away 상태·예산(있을 때만). 한도·컨텍스트는 문턱에 따라 초록/노랑/빨강. 폭은 `COLUMNS-4` 기준.
`minimal` 은 모델·컨텍스트·5h 만(away 가 켜져 있으면 그것도). 기존 away·슬롯 기록, `<sid>.limits.json` 쓰기는 그대로다.

### 미리보기 (샘플 입력: Opus high, 컨텍스트 34%, 5h 78%, wk 93%, 리셋 2h05m, 저장소 claude-doctor main 더러움)
### plain

원본(ANSI, \e 는 ESC):
```text
\e[1mclaude-doctor\e[0m \e[35m(main*)\e[0m \e[2m·\e[0m \e[36mOpus\e[0m \e[2mhigh\e[0m \e[32mctx 34%\e[0m \e[2m·\e[0m \e[33mlimit 5h 78%\e[0m \e[31mwk 93%\e[0m \e[2mreset 2h05m\e[0m
```

벗긴 판:
```text
claude-doctor (main*) · Opus high ctx 34% · limit 5h 78% wk 93% reset 2h05m
```

### nerd

원본(ANSI, \e 는 ESC):
```text
\e[1m claude-doctor\e[0m \e[35m main*\e[0m \e[2m·\e[0m \e[36m Opus\e[0m \e[2mhigh\e[0m \e[32m 34%\e[0m \e[2m·\e[0m \e[33m 5h 78%\e[0m \e[31mwk 93%\e[0m \e[2m 2h05m\e[0m
```

벗긴 판:
```text
 claude-doctor  main* ·  Opus high  34% ·  5h 78% wk 93%  2h05m
```

### minimal

원본(ANSI, \e 는 ESC):
```text
\e[36mOpus\e[0m \e[32m34%\e[0m \e[2m·\e[0m \e[33m5h 78%\e[0m
```

벗긴 판:
```text
Opus 34% · 5h 78%
```

### plain, LINES=2 (벗긴 판)

```text
claude-doctor (main*) · Opus high ctx 34%
limit 5h 78% wk 93% reset 2h05m
```

### plain, 좁은 터미널 COLUMNS=50 (벗긴 판)

```text
claude-doctor (main*) · Opus high ctx 34%
```

nerd 의 글리프는 Nerd Font(Font Awesome 영역: folder f07b, branch e0a0, microchip f2db, tachometer f0e4, clock f017, bolt f0e7, users f0c0, plane f072, dollar f155)다. 폰트가 없으면 벗긴 판에서 빈 자리로 보인다. 터미널 폰트 렌더 자체는 확인하지 못했다.

### 지연 [실측]
- `python3 -I harness-status.py`, 샘플 입력, 30회: 중앙값 약 31 ms, p90 약 35 ms(맨 python 시작 약 8 ms). 한도 파일 쓰기·원장 읽기·`.git/HEAD` 읽기·더러움 캐시 조회 포함.
- git 은 브랜치를 `.git/HEAD` 직접 읽기로 얻어 프로세스를 띄우지 않는다. 더러움(`git status --porcelain -uno`)만 10초 캐시(`$TMPDIR/claude-statusline-git-<uid>/`)하고 타임아웃 1.5초다. 이 저장소에서 `git status` 는 3 ms 였다. 큰 저장소(Roblox 에셋 많은 곳)에서의 캐시 미스 비용은 **미측정**이다.
- 테스트 `statusline: fast (<150ms per run)` 통과.

### 회귀
기존 statusline 테스트 전부 통과(132/132). 바뀐 것: 테스트 `ENV` 에 `NO_COLOR=1` 추가(색 없이 문자열 비교), 프로젝트명이 입력에 있으면 줄 맨 앞에 붙는 것은 의도된 변경이다. 한도 줄은 `limit 5h 20% wk 50%` 뒤에 `reset …` 이 붙는다. 비용은 기본으로 늘 보인다(사용자 결정으로 기본값 `always`, 숨기려면 `COST=auto`).

## 8. mod 로 하단 통합 (q-ui 시제품)
CLI 2.1.316 의 `plugin-authoring` 스킬과 그 타입 파일(`claude-code.d.ts`, 22,834줄)을 읽고 만들었다. 인터랙티브 TUI 는 이 환경에서 볼 수 없어 **실제 화면에서 줄이 줄어드는지는 미확인**이다. 아래 "가능/불가"는 타입 문서와 단위 렌더 시험까지만 근거한다.

### 8.1 SessionMode 의 실체 (바로 잡을 점)
문서: "The dim mode labels at the right of the prompt footer (`focus`, `memory paused`), joined by ` & `. One instance." props 는 `modes: readonly string[]` 하나다. 즉 **푸터 오른쪽의 흐린 모드 표지** 자리다. 사용자 화면의 "auto mode on (shift+tab to cycle)" 와 "← 1 agent" 가 이 자리에 속하는지는 **미확인**이다(`modes` 에 권한 모드가 들어오는지 확인할 방법이 타입에 없다). 그래서 시제품은 두 자리를 다 준비했다.
| 자리 | 문서상 정체 | q-ui 옵션 |
|---|---|---|
| `SessionMode` | 푸터 오른쪽 모드 표지(`modes` 를 고쳐 쓰거나 자기 트리를 그림) | `site=session-mode`(기본) |
| `PromptHint` | 프롬프트 아래 힌트 줄(`? for shortcuts`, `esc to interrupt`, "the pills beside them"). `hint` 문자열을 고쳐 쓰면 줄이 **통째로 대체**된다. `tail` 은 끝에 덧붙일 뿐(터미널은 엔진 줄을 유지) | `site=prompt-hint`(실험) |
"← 1 agent" 는 이름 모를 "알약(pill)" 일 가능성이 크고, 그러면 PromptHint 쪽이다. 시험에서 어느 쪽이 사라지는지로 결정한다.

### 8.2 가능 / 불가 / 미확인
| 구분 | 내용 |
|---|---|
| 가능 | `ui.render` 가 `{component:'SessionMode'}` 에 자기 트리(Box/Text, 색·bold)를 그림. `next(e)` 를 부르면 엔진 원본. 터미널·데스크톱에서만 호출됨 |
| 가능 | 읽기: 모델 id `$.session.model()`, 컨텍스트 %·비용·한도(5h/7d, `percentUsed`, `resetsAt`) `$.session.usage()` 와 `session.measure` 이벤트(변할 때만, 한도는 1%p 단위), cwd `$.session.cwd()`, 세션 id, 에이전트 목록 `$.agent.list()`(id·type·status), 환경 변수 `$.env.get`, 파일 `$.fs.read`(4 MiB 까지), 프로세스 `$.process.run`(git) |
| 가능 | effort: `turn.step` 이벤트의 `e.effort`(요청이 나갈 때). 첫 요청 전에는 비어 있다 |
| 가능 | 갱신: `$.state`/atom 을 쓰면 읽는 그림이 다시 그려짐. `$.ui.invalidate('ui.render')` 는 초당 10회(터미널 표시 중 30) 한도 |
| 가능 | 끄기: 플러그인을 끄면 훅이 없어져 원래 푸터. 훅이 던지거나 트리가 틀리면 그 훅만 건너뛰고 엔진 원본을 그림 |
| 불가 | **권한 모드(auto/plan/default)를 읽는 `$` 메서드는 없다.** `tool.call` 등 이벤트 입력에도 현재 모드는 없다(`setMode` 는 권한 갱신 타입에만). 모드 표지는 `e.props.modes` 에 엔진이 넣어 준 것만 쓸 수 있다 |
| 불가 | 모델 표시 이름("Opus 5.5")은 주지 않는다. id 를 정규식으로 바꿈(모르는 모양이면 id 그대로) |
| 불가 | git 브랜치: `SessionRepo` 에 브랜치가 없다. `$.process.run(['git', …])` 로 직접 구한다(10초 캐시) |
| 불가(문서상) | 엔진 줄을 "숨기는" 전용 API 는 없다. 줄 수는 그 자리 트리가 비는지에 달렸다. SessionMode 가 빈 트리를 내면 사라지는지는 **미확인**(타입 문서에 "empty 면 행이 없어진다"는 말이 없다) |
| 미확인 | 푸터의 "auto mode on" 문구와 "← 1 agent" 가 SessionMode 에 속하는지, 줄 수가 실제로 줄어드는지, statusLine 출력이 비면 그 행이 사라지는지, `$.fs.read` 가 `~/.claude/harness.env` 를 허용하는지(실패하면 plain 으로 폴백), 매 렌더 비용 |
한도 파일(`$TMPDIR/claude-subagent-slots/<sid>.limits.json`)은 **읽을 필요가 없었다**: `$.session.usage().rateLimits` 가 statusline 과 같은 값을 준다. 그래서 mod 는 그 파일을 건드리지 않는다.

### 8.3 시제품 구성 (`plugins/q-ui/`)
- `.claude-plugin/plugin.json`(옵션 `style` auto|plain|nerd, `site` session-mode|prompt-hint), `hooks/hooks.json`, `hooks/register.tsx`, `types/index.d.ts`(상태 계약 `q-ui.snap`), `tests/render.test.tsx`.
- 훅: `session.start`(스타일·모델·git 읽기, 10초 타이머로 git 갱신), `session.measure`(한도·컨텍스트·비용), `turn.step`(모델·effort, 스트리밍 제너레이터), `ui.render` SessionMode / PromptHint.
- 그림: `[모드 &…] · name:branch* │ 모델 effort ctx % │ 한도 5h wk reset │ $비용`. 묶음마다 아이콘 하나(nerd, harness-status.py 와 같은 코드포인트), 흐린 색 없음, 좁으면 뒤 묶음부터 통째로 뺌(폭의 절반 기준, 푸터 왼쪽을 못 재서 보수적).
- 스타일: 옵션 `style=auto` 면 `HARNESS_STATUSLINE_STYLE`(환경 변수, 없으면 `~/.claude/harness.env`)이 `nerd` 일 때만 nerd, 그 밖(off·minimal 포함)은 plain.
- 서브에이전트·away 묶음은 옮기지 않았다(`$.agent.list()` 로 가능하나 시제품 범위 밖). "← 1 agent" 는 엔진 알약이 그대로 남는다(8.5).
- marketplace.json 에 `q-ui` 항목을 추가했다(설치는 하지 않음).

### 8.4 statusLine 중복 제거 제안
statusLine 자체를 지우면 안 된다: `harness-status.py` 가 away 훅이 읽는 `limits.json` 을 쓴다. 제안: 스크립트는 그대로 두고 사용자 harness.env 에 `HARNESS_STATUSLINE_STYLE=off`(그러면 출력은 비고 `limits.json` 만 계속 쓴다)를 넣고, q-ui 는 `pluginConfigs` 로 `style=nerd` 를 명시한다. 출력이 빈 statusLine 이 행을 없애는지는 미확인이다. 마이그레이션 초안: `plugins/q-ui/settings-migration-draft.json (적용 디렉터리 밖에 둔다: settings-migrate 는 그 디렉터리의 *.json 을 모두 적용·기록하므로, 빈 초안이 들어가면 그 번호가 고정된다)`(`draft: true`, `ops` 는 비어 있고 제안은 `proposed_ops`). 주의: `settings-migrate.py` 는 `*.json` 을 전부 읽으므로 이 파일이 있는 채로 `apply` 하면 아무 것도 안 바꾸고 id 만 기록된다. 적용 전에 지우거나 이름을 바꿀 것. 장기적으로는 mod 가 `limits.json` 을 대신 써 주면 statusLine 을 완전히 끌 수 있다(미구현).

### 8.5 "← 1 agent" 처리
1. 엔진 알약이 그대로 남는 경우(SessionMode 만 그릴 때): 줄은 줄지 않는다. 할 수 있는 것은 같은 줄에 `$.agent.list()` 로 센 "agents N" 묶음을 더해 의미 중복을 감수하는 정도.
2. `site=prompt-hint` 가 알약까지 대체하면: 우리 줄이 힌트 줄을 통째로 차지해 `esc to interrupt`·`? for shortcuts` 도 같이 사라진다. 작업 중에 힌트가 필요하면 `e.props.isWorking` 일 때 `next(e)` 로 엔진 줄을 돌려주는 분기를 넣어야 한다(미구현, 시험 결과를 보고 결정).
3. 어느 쪽도 안 되면 불가로 결론짓고, 줄을 줄이는 길은 statusLine 한 줄만 두는 현 상태다.

### 8.6 버전 위험
- 문서 자체가 "EARLY ACCESS: this surface may change between releases without notice". 이 코드는 2.1.316 타입으로 `tsc`·`claude plugin validate`·`claude plugin test` 를 통과했다.
- 깨지는 모습: (a) 트리가 틀리면 그 훅만 건너뛰고 엔진 푸터가 원래대로 나온다(그림이 안 바뀜). (b) `SessionMode` 이름이 바뀌면 훅이 한 번도 안 불려 같은 증상. (c) 호출 메서드가 없어지면 모듈 로드 실패. 어느 경우도 화면이 망가지기보다 "mod 가 안 보임" 으로 나타난다.
- 감지: `claude plugin validate plugins/q-ui`(호출한 `$` 목록 검증), 타입 검사(`.claude-plugin/types` 가 로드 때마다 새로 써지므로 `tsc -p plugins/q-ui`), `claude plugin test plugins/q-ui`, 실행 중엔 `claude --debug` 의 `q-ui: ui.render hook skipped …` 줄. 업데이트 뒤에는 세 명령을 다시 돌리고 `claude --version` 을 기록해 두면 된다.

### 8.7 검증 결과
- `claude plugin validate plugins/q-ui`: 통과(오류 0; 플러그인 디렉터리용 경고는 아이콘 없음뿐).
- `tsc`(스킬 타입 파일 기준, strict): 오류 0.
- `claude plugin test plugins/q-ui`: 2/2 통과. `$.ui.mount` 로 SessionMode 를 단위 렌더해 plain 은 `auto · claude-doctor:main* · Opus 5.5 ctx 30% · limit 5h 12% wk 31% reset 2h01m · $12.34`, nerd 는 묶음당 아이콘 하나와 ` │ ` 구분자를 확인했다. 이 시험은 트리까지만 보며 실제 터미널 그리기(줄 수)는 보지 않는다.
- 제약 확인: 훅은 `$` 를 최상위 함수 선언으로만 넘길 수 있다(validate 가 막음). 그래서 헬퍼가 `register` 밖에 있다.

### 8.8 사용자 시험 절차 (2차 갱신: 아래 8.10 이 현재 절차)
1차 절차는 8.10 으로 대체됐다.

### 8.9 2차: cc-opencode 조사, 힌트 줄 합치기, 중복 해결 (2026-11-11)
사용자 시험(1차): `site=session-mode` 에서 "auto mode on (shift+tab to cycle) · ← 1 agent" 줄은 그대로였고, statusline 이 왼쪽(원래 statusLine)과 오른쪽(mod)에 두 번 나왔다. SessionMode 는 오른쪽 모드 표지 자리였고 auto mode 줄은 PromptHint 쪽이다. 사용자 승인(2026-11-11): 코드 악의성 검사만 하고 빌드·실행하는 것까지 clone 허용.

**cc-opencode 실행 전 악의성 검사**(`/code/.cache/cc-opencode`, 커밋 `b00a7a6e99d00116e1c07ab4e5f80c94381bd0ca`, 읽기만 함, 아무것도 실행하지 않음)

| 항목 | 결과 |
|---|---|
| 규모 | 추적 파일 23개, 89.6 KB. 플러그인 2개(opencode-look, toolbox)와 테마 JSON 2개 |
| package.json, lockfile, 의존성 | 없음(`find` 로 확인). npm 설치·빌드 단계 자체가 없다. scripts/pre·post·install·prepare 해당 없음 |
| 레지스트리 외 URL, git 의존성 | 없음 |
| 네트워크 호출 | fetch·http·WebSocket·XMLHttpRequest·curl 0건(소스의 URL 문자열도 없음). 단 toolbox 는 사용자가 설정한 MCP 서버를 `$.mcp.call`(pulse `stop_timer` 는 `$.ui.ask` 확인 뒤, 캘린더 조회)로 부른다 |
| 파일 쓰기 | `$.fs.write`/writeFile 등 0건. 읽기만: `$.fs.read`/`$.fs.list` 로 `~/.claude/sessions/<pid>.json`(toolbox 의 세션 목록). 자격 증명·셸 rc·ssh 접근 0건 |
| 프로세스 실행 | `$.process.run` 2곳: `claude mcp list`(120초 제한), `/bin/ps -o pid=,lstart= -p <pid들>`. child_process·spawn·exec 직접 호출 0건 |
| eval, Function, 난독화, base64, 긴 인코딩 덩어리 | 0건. 제로폭·방향 제어 등 숨은 문자 0건 |
| 매니페스트 | plugin.json 은 이름·설명만. hooks.json 은 `{"modules":["./register.tsx"]}` 뿐(명령 훅·MCP 등록·권한 요청 없음). `.gitignore` 정상 |
| 테마 JSON | 색 값만 |
| 라이선스 | **LICENSE 파일 없음**, README 에도 명시 없음(미확인: 권리 불명). 이 저장소는 코드를 복사하지 않고 원칙만 빌린다 |
| 판정 | **깨끗함.** 읽기 중심이고, 쓰는 일은 사용자가 확인하는 MCP 호출 하나뿐. 설치할 의존성이 없어 `npm` 단계는 필요 없었다 |

주의: `types/index.d.ts`, `tsconfig.json` 이 `.claude-plugin/types`(Claude Code 가 로드 때 쓰는 타입)를 가정해서, 비설치 검증은 이 저장소에서 하지 않았다. cc-opencode 코드는 실행하지 않았다(렌더 테스트 포함). 읽은 것만으로 아래를 정리했다.

**cc-opencode 가 쓰는 자리와 API**
- opencode-look: `ui.render` 훅 — UserMessage(왼쪽 막대 `▍` + 메시지 배경 블록, 위아래 한 줄 여백), AssistantMessage(자체 마크다운: 굵게·기울임·코드·목록·제목을 테마 색 역할로 칠함, 코드블록·표는 엔진 `Markdown` 에 위임), TurnDuration(`▣  Done · Opus 5.5 · 27.5s`), **PromptHint**, ToolUse·ToolResult·ToolGroup·ToolProgress·CommandOutput·InfoNotice·Spinner(`next(e)` 결과를 좌우 여백 `Box` 로 감싸 들여쓰기만). 모델·effort 는 `$.config.list()` 를 30초마다 읽는다.
- 색은 고정값이 아니라 테마 역할 이름(`claude`, `warning`, `success`, `suggestion`, `inactive`, `userMessageBackground`)이다. 같은 모드가 어느 테마에서도 맞고, 테마 JSON 은 별도 파일(`~/.claude/themes/`)로 준다.
- toolbox: `$.ui.mount`/`open` 의 측면 Pane, `session.measure`(토큰·비용), `$.session.usage()`, `$.command.register`(`/toolbox`), `$.clock.every`.
- **auto mode 줄과 "← N agent" 는 다루지 않는다.** PromptHint 를 `<Text>Claude · 모델 · effort {hint} {tail}</Text>` 한 줄로 다시 그리는데 `hint` 문자열(엔진이 그린 줄을 그대로 읽은 것)을 통째로 뒤에 붙일 뿐이라 auto mode 문구와 알약 글자가 그대로 남는다. 즉 "줄을 없앤" 사례는 아니고, 그 줄 앞에 정보를 덧붙인 사례다. 알약 클릭성은 대체 트리라 사라진다(문서: tail 만 엔진 줄을 살림).
- 스피너: Spinner 는 건드리지 않고 들여쓰기만(위).

**빌린 디자인 원칙**(opencode 를 복제하지 않고 원칙만)
1. 정보 위계: 강조는 한 가지 색(accent)에 모으고 나머지는 흐리게 한다(cc-opencode 는 MUTED 로 부가 정보). 우리는 사용자 결정(흐린 글자 금지, 묶음마다 아이콘 하나)을 우선해 "흐림" 대신 색 역할 구분만 쓴다.
2. 한 줄에 맥락 하나: `Claude · 모델 · effort` 처럼 가장 자주 보는 것을 왼쪽에, 부가는 뒤에. 우리 줄: `모드 · 프로젝트:브랜치 │ 모델 effort ctx │ 한도 │ 비용 · N agents`.
3. 여백: 좌우 gutter(3칸)를 통일해 모든 줄이 같은 열에서 시작한다. 이번 변경에는 적용하지 않았다(엔진 줄과의 정렬을 실제 TUI 에서 봐야 한다). 후속 후보.
4. 테마 색 역할 이름 사용(고정 RGB 금지). q-ui 는 지금 색 이름(green/yellow/red/cyan/magenta/blue)을 쓴다. 후속 후보: 테마 역할(`success`/`warning`/`error`)로 바꾸면 사용자 테마에 맞는다(역할 키가 `Text color` 에서 통하는지는 cc-opencode 가 쓰므로 가능하다고 본다, 이 저장소 시험은 아직).

**q-ui 2차 변경**
- 옵션(userConfig): `site` = `prompt-hint`(기본) | `session-mode` | `off`, `hint` = `merge`(기본) | `replace` | `keep`, `style` = `auto` | `plain` | `nerd`.
- 기본(site=prompt-hint): **SessionMode 는 엔진 원래 표시로 돌려준다**(훅이 `next(e)`). 오른쪽 중복이 없어진다. `site=session-mode` 는 1차 동작(오른쪽에 그림, 힌트 줄은 엔진 그대로).
- 힌트 줄(PromptHint)에서 `hint` 문자열을 `hooks/hint.ts` 의 `parseHint` 로 읽어 모드 이름(`auto`, `plan`, …)과 알약 N(`← 1 agent`)을 뽑고 한가한지(`idle`: 모드·알약·`? for shortcuts` 외 글자가 없음) 판정한다.
  - `merge`: 한가하면 `모드 · 프로젝트 │ 모델 │ 한도 │ 비용 · N agents` 한 줄로 **대체**한다. 작업 중(`isWorking`)이거나 모르는 문구(`esc to interrupt`, 권한 대기 등)면 **엔진 줄을 살리고** 묶음을 `tail`(엔진이 dim 으로 이어 붙이고 폭에서 자름)로만 덧붙인다.
  - `keep`: 항상 엔진 줄 + `tail`. 알약이 계속 살아 있다.
  - `replace`: 항상 자기 줄, 중요한 안내가 있으면 글자를 줄 끝에 옮겨 적는다(알약 클릭 불가).
- 좁은 폭: 비용 → 한도 → 모델 순으로 뒤 묶음부터 통째로 뺀다. 프로젝트와 `N agents` 는 남긴다(폭에서 4칸 뺀 값 기준).
- **statusLine 중복 해결: (a) 표지 파일을 골랐다.** mod 가 켜지면 `$TMPDIR/claude-subagent-slots/<sid>.qui-mod` 를 30초마다 갱신하고, `harness-status.py` 는 이 파일의 mtime 이 90초 안이면 줄을 비우고 **away 표시만** 낸다(away 는 mod 가 모르는 정보). `limits.json` 기록은 그대로다. 이유: (b) `HARNESS_STATUSLINE_STYLE=off` 는 사용자 전역 설정이라 mod 를 끄거나 `--plugin-dir` 없이 연 세션에서 statusline 이 사라지고(되돌리기 잊기 쉬움), 어떤 mod 에서도 away 표시를 같이 잃는다. (a) 는 세션별이고 mod 가 멎으면 90초 뒤 statusline 이 저절로 돌아온다. 비용: 스크립트에 12줄, 테스트 4개. 이것으로 settings.json·harness.env 는 건드리지 않고 `pluginConfigs` 는 선택이다(`settings-migration-draft.json` 갱신).
- `style=auto` 는 이전과 같이 `HARNESS_STATUSLINE_STYLE`(env 또는 `~/.claude/harness.env`)이 nerd 일 때만 nerd.
- 개발 환경: `plugins/q-ui/package.json`(private, devDependency `typescript`), `.gitignore`(node_modules). `npm install --ignore-scripts` 로 설치했다. 다른 저장소 node_modules 는 쓰지 않았다.

**스피너 커스텀 가능성(제안, 미구현)**
- `ui.render` 의 `Spinner`: props `word`(`Sauteing`), `message`, `suffix`(`…`), `mode`(`requesting|responding|thinking|tool-input|tool-use`). 문서: "세 가지(word/message/suffix)를 다시 쓰거나, 모두 대체하는 트리를 그린다". 경과 시간·토큰·effort 는 엔진이 붙여 두므로 트리 대체 시 우리가 다시 그려야 한다(`$.session.usage()`, 시작 시각 필요).
- 제안 순서: (1) `word` 를 `mode` 별 짧은 글자(`thinking`/`tool`/`writing`)로 바꾸는 최소 변경(위험 낮음, 줄 폭 그대로), (2) 필요하면 `suffix` 로 `…` 대신 도형, (3) 트리 대체는 opencode 식 `▣`/막대 애니메이션이 필요할 때만. 프레임 애니메이션 API(`$.clock.every` 로 상태 atom 갱신 → 재렌더)는 있으나 재렌더 비용·깜박임은 미확인. 사용자가 스피너 형태(글자 vs 도형)를 정하면 구현한다.

**검증**(Claude Code 2.1.316 타입)
- `tsc -p plugins/q-ui`(strict + noUncheckedIndexedAccess): 오류 0.
- `claude plugin validate plugins/q-ui`: 통과(경고는 아이콘 없음뿐).
- `claude plugin test plugins/q-ui`: 11/11. 렌더 테스트: 한가함(plain 한 줄 `auto · claude-doctor:main* · Opus 5.5 ctx 30% · limit 5h 12% wk 31% reset 2h01m · $12.34 · 1 agent`), nerd, 좁은 폭(50칸: 비용 등이 빠지고 agents 는 남음), 작업 중 / 권한 대기 문구는 엔진 힌트 + tail, keep, SessionMode 기본은 엔진 그대로, site=session-mode, 표지 파일 쓰기(on/off), `parseHint` 단위.
- `python3 -I home/.claude/hooks/tests/test-subagent-slots.py`: 136/136(표지 4개 포함: 줄 비움, limits.json 유지, 90초 지나면 복귀, 표지 없음).
- 테스트의 한계: 엔진 줄은 스텁(`hint` + `tail` 을 그리는 가짜)이라 실제 줄 수·알약 위치는 TUI 에서만 보인다.

**미확인**
- 실제 `hint` 문자열이 `auto mode on (shift+tab to cycle) · ← 1 agent` 모양인지(사용자 시험 문구에서 추정, 다른 모드는 `plan mode on`, `accept edits on`, `bypass permissions on` 일 것으로 추정). 모르는 모양은 한가함이 아니라고 보고 엔진 줄을 살리므로 최악은 "합쳐지지 않음".
- `PromptHint` 대체 트리가 엔진의 알약(`← 1 agent`)을 정말 지우는지(문서는 `tail` 만 엔진 줄을 살린다고 하므로 대체 시 사라진다고 본다). 대체 트리에서 N agents 는 글자일 뿐 클릭 불가.
- 엔진 `$TMPDIR` 와 statusLine 자식 프로세스의 `$TMPDIR` 가 같은지(같은 프로세스 트리라 보지만 시험 필요). 다르면 표지가 안 보여 중복이 남는다(정보 손실은 없음).
- statusLine 출력이 비면 상태 행 자체가 사라지는지(away 가 없으면 빈 출력).
- `tail` 이 폭을 넘을 때의 모양(문서: 줄 끝에서 자름, 4칸 미만이면 생략).
- `fs.write` 가 플러그인 환경에서 `$TMPDIR` 쓰기를 거부당하는지(거부되면 조용히 실패, statusline 그대로).
- cc-opencode 라이선스(없음).

### 8.10 사용자 시험 절차 (2차)
1. 새 터미널에서 `cd /code/Projects/claude-doctor && claude --plugin-dir plugins/q-ui`(설치·settings 변경 없음, 그 세션만). nerd 는 `HARNESS_STATUSLINE_STYLE=nerd claude --plugin-dir plugins/q-ui`.
2. 볼 것(약 30초 안에 statusline 이 사라진다: 표지 파일이 써져야 하니 첫 줄 직후 한 번 갱신을 기다림):
   - 프롬프트 아래 한 줄이 `auto · claude-doctor:main* │ Opus … │ 한도 … │ $… · N agents` 로 바뀌었나(한가할 때).
   - 푸터 오른쪽에 중복이 없나(기본 site=prompt-hint 라 엔진 표시 그대로).
   - 원래 statusLine 줄이 사라졌나(away 중이면 AWAY 줄만 남는다). 사라지지 않으면 `$TMPDIR` 불일치 의심: `ls "${TMPDIR:-/tmp}"/claude-subagent-slots/*.qui-mod`.
   - 서브에이전트를 띄우면 `N agents` 가 맞게 바뀌나. 작업 중(esc to interrupt)·권한 대기에서 엔진 힌트가 보이고 묶음이 dim 으로 뒤에 붙나.
   - 창을 좁혔을 때 비용부터 사라지고 agents 는 남나. 줄 수가 하나 줄었나.
3. 옵션 바꾸기: `/plugin` 의 q-ui 설정(또는 settings.json `pluginConfigs["q-ui"].options`)에서 `hint`(merge/replace/keep), `site`(prompt-hint/session-mode/off), `style`(auto/plain/nerd). 알약을 눌러야 하면 `hint=keep`. 1차 동작은 `site=session-mode`.
4. 끄기: 세션을 닫으면 끝(`--plugin-dir` 은 그 세션만). 옵션 `site=off` 는 mod 를 로드한 채 아무것도 안 그리고 표지도 안 쓴다. 표지는 90초 안에 낡아 statusline 이 돌아온다.
5. 안 보이면 `claude --debug --plugin-dir plugins/q-ui` 로 `q-ui:` 줄. 결과(어느 줄이 어떻게 됐는지, 특히 hint 원문)를 알려 주면 `parseHint` 를 맞추고 0005 초안을 확정한다.

## 9. 사용자 결정이 필요한 것
1. `~/.claude/settings.json` 의 `statusLine`(0001 마이그레이션이 이미 넣음)은 그대로 쓰므로 새 마이그레이션은 만들지 않았다. 사용자 harness.env 에서 `nerd` 를 켤지.
2. 탭 제목 훅(§4)을 만들지. 만든다면 Claude Code 자체 제목과의 충돌을 실측해야 한다.
3. 구독자에게도 비용을 보일지(`COST=always`) — 기본은 숨김.
4. 응답 형식 3줄(§6)을 사용자 CLAUDE.md 에 넣을지, output style 로 할지.
5. 사용자 정의 테마 예시를 하네스가 제안할지(취향이라 기본은 안 넣음).
6. ui-themes 를 직접 설치해 볼지(서드파티 코드라 사용자 확인 필요).
7. q-ui mod 를 켤지, 켠다면 statusLine 을 `STYLE=off` 로 조용히 만들지(§8.4, 0005 초안).
