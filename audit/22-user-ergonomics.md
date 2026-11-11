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
| `COST` | `auto`(구독자가 아니면) / `always` / `never` | `auto` |
| `WARN_PCT`, `HOT_PCT` | 색 문턱 | 70, 90 |

사용자 본인은 `harness.env` 에서 `HARNESS_STATUSLINE_STYLE=nerd` 로 바꾸면 된다(현재 주석 처리된 한 줄이다, 사용자 선택이므로 켜지 않았다). `NO_COLOR` 가 있으면 색을 쓰지 않는다. `off` 도 한도 파일은 계속 쓴다([실측] 테스트).

### 담는 정보와 생략 순서(뒤에서부터 통째로)
1) 프로젝트명·브랜치(더러우면 `*`) 2) 모델·effort(입력에 있을 때) 3) 컨텍스트 % 4) 한도 5h·wk·가장 가까운 리셋까지 남은 시간(구독자가 아니면 비용) 5) 실행 중 서브에이전트(0이면 숨김) 6) away 상태·예산(있을 때만). 한도·컨텍스트는 문턱에 따라 초록/노랑/빨강. 폭은 `COLUMNS-4` 기준.
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
기존 statusline 테스트 전부 통과(132/132). 바뀐 것: 테스트 `ENV` 에 `NO_COLOR=1` 추가(색 없이 문자열 비교), 프로젝트명이 입력에 있으면 줄 맨 앞에 붙는 것은 의도된 변경이다. 한도 줄은 `limit 5h 20% wk 50%` 뒤에 `reset …` 이 붙는다. 구독자(rate_limits 있음)에게는 비용이 숨겨진다(`COST=always` 로 복원).

## 8. 사용자 결정이 필요한 것
1. `~/.claude/settings.json` 의 `statusLine`(0001 마이그레이션이 이미 넣음)은 그대로 쓰므로 새 마이그레이션은 만들지 않았다. 사용자 harness.env 에서 `nerd` 를 켤지.
2. 탭 제목 훅(§4)을 만들지. 만든다면 Claude Code 자체 제목과의 충돌을 실측해야 한다.
3. 구독자에게도 비용을 보일지(`COST=always`) — 기본은 숨김.
4. 응답 형식 3줄(§6)을 사용자 CLAUDE.md 에 넣을지, output style 로 할지.
5. 사용자 정의 테마 예시를 하네스가 제안할지(취향이라 기본은 안 넣음).
6. ui-themes 를 직접 설치해 볼지(서드파티 코드라 사용자 확인 필요).
