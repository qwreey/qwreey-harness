# 22. 사용자 가시성(statusline, 위쪽 배치, 테마, 응답 표시)

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

### 8.8 사용자 시험 절차
1. 새 터미널에서 `cd /code/Projects/claude-doctor && claude --plugin-dir plugins/q-ui`(설치·settings 변경 없음, 그 세션만). nerd 를 보려면 `HARNESS_STATUSLINE_STYLE=nerd claude --plugin-dir plugins/q-ui`.
2. 볼 것: (1) 푸터 오른쪽(또는 모드 표지 자리)에 `name:branch* │ 모델 … │ 한도 … │ $` 가 나오는가. (2) "auto mode on (shift+tab…)" 와 "← 1 agent" 가 그대로인가, 사라졌는가. (3) 하단 줄 수가 줄었는가(statusLine 을 끄지 않은 상태에서는 오히려 중복이니, 비교하려면 `HARNESS_STATUSLINE_STYLE=off` 를 환경에 주고 `style` 옵션으로 nerd 를 고정: `claude --plugin-dir plugins/q-ui` 후 `/plugin` 설정에서 style=nerd). (4) 서브에이전트를 하나 띄웠을 때 푸터가 어떻게 되는지. (5) 줄이 너무 길어 잘리는지(좁은 창).
3. 안 보이면 `claude --debug --plugin-dir plugins/q-ui` 로 `q-ui:` 줄을 본다. `site=prompt-hint` 도 같은 방식으로 시험(옵션은 `/plugin` 의 q-ui 설정).
4. 끄기: 세션을 닫으면 그만이다(`--plugin-dir` 은 그 세션만). 설치했다면 `/plugin` 에서 q-ui 를 끄거나 `enabledPlugins` 의 `q-ui@claude-doctor-market` 을 false 로. 훅이 깨져도 엔진 푸터로 돌아간다.
5. 결과(어느 줄이 어떻게 됐는지)를 알려 주면 8.5 의 갈림길과 0005 초안의 `proposed_ops` 를 확정한다.

## 9. 사용자 결정이 필요한 것
1. `~/.claude/settings.json` 의 `statusLine`(0001 마이그레이션이 이미 넣음)은 그대로 쓰므로 새 마이그레이션은 만들지 않았다. 사용자 harness.env 에서 `nerd` 를 켤지.
2. 탭 제목 훅(§4)을 만들지. 만든다면 Claude Code 자체 제목과의 충돌을 실측해야 한다.
3. 구독자에게도 비용을 보일지(`COST=always`) — 기본은 숨김.
4. 응답 형식 3줄(§6)을 사용자 CLAUDE.md 에 넣을지, output style 로 할지.
5. 사용자 정의 테마 예시를 하네스가 제안할지(취향이라 기본은 안 넣음).
6. ui-themes 를 직접 설치해 볼지(서드파티 코드라 사용자 확인 필요).
7. q-ui mod 를 켤지, 켠다면 statusLine 을 `STYLE=off` 로 조용히 만들지(§8.4, 0005 초안).
