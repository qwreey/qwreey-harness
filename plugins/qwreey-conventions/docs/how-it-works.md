# qwreey-conventions 동작 상세

구성: 스킬 셋("어떻게 쓰나"), 경로 한정 규칙 여섯(`rules/*.md`, 맞는 파일을 열 때 훅이 주입, 하나는 켜기 스위치가 있다), 알림 훅(`hooks/hooks.json`). 훅은 막지 않는다. 예외는 답변 언어 이탈의 Stop `decision: block` 하나다. `.claude/` 기록 규약은 이 플러그인에 없고 coderag 플러그인의 `coderag:agent-records` 가 맡는다.

## 스킬과 규칙
| 이름 | 다루는 것 |
|---|---|
| `qwreey-conventions:comments` | 코드 주석: 지금의 이유만, 이력은 커밋·CHANGELOG·원장으로, `Ref:` 꼬리, 키보드로 치는 문자, 파일의 주석 언어, 저장소 설정 형식, layout 알림에 답하는 법 |
| `qwreey-conventions:agent-docs` | CLAUDE.md, SKILL.md, references, agents, rules: 둘 것과 옮길 것, 입구 문서와 references 의 차이, 원장 id |
| `qwreey-conventions:code-reuse` | 값(정책/불변식), 한 사실 한 정의, `@copy-of` 사본 표시, 라이브러리와 직접 구현의 기준, 저장소 설정(`reuse`) |

규칙 파일: `comments`, `agent-docs`, `code-structure`, `code-reuse`, `memory`, `readable-code`. 각 파일의 `paths:` 가 대상이다. 플러그인은 `.claude/rules` 를 실을 수 없어서 훅이 같은 시점에 같은 본문을 넣는다.

`readable-code` 는 함수 안 문단(빈 줄), 단계 라벨, 호버에 보이는 문서 주석, 이유 주석의 자리, 선언과 이름, 분기 사다리, 되풀이 루프를 말한다. 다른 규칙과 달리 스킬로 미루지 않고 규약 전체를 본문에 둔다(약 2.3k자): 규칙 끝의 스킬 포인터는 실제 세션에서 거의 읽히지 않았다. 언어 중립으로 쓰고, Luau 의 `---` 같은 툴킷 꼴은 툴킷 팩 규칙(luau-kb `luau-core`)이 말한다. 프론트매터 `switch: HARNESS_READABLE_CODE` 라서 그 키가 `on` 일 때만 실린다(아래 규칙 주입).

## 훅
| 이벤트(matcher) | 스크립트 | 하는 일 |
|---|---|---|
| PostToolUse(Read·Edit·Write·MultiEdit·NotebookEdit) | `rules_inject.py` | 규칙 주입 |
| PostToolUse(Write·Edit·MultiEdit), Stop | `conventions-check.py` | 추가한 줄의 주석·문서 검사, readable-code 를 켰으면 쓰거나 키운 함수의 layout 알림(`layout_metrics.py`), Stop 에서 남은 문제 보고 |
| PostToolUse(Write·Edit·MultiEdit) | `reuse-check.py` | 사본 검사 |
| PostToolUse(Write·Edit·Bash) | `structure-reminder.py` | 파일 길이, 세션 성장, 폴더 과밀 |
| PostToolUse(Write·Edit·MultiEdit) | `memory-placement.py` | auto memory 에 쓴 저장소 지식 |
| PreToolUse(Bash) | `bash-bypass-reminder.py` | 셸·인터프리터로 파일을 바꾸면 Edit·Write 훅과 rules 를 비껴간다는 알림 |
| UserPromptSubmit, Stop, PostToolBatch | `reply_language.py` | 답변 언어 이탈 |
| PreCompact(manual·auto) | `compact_epoch.py qwreey-conventions` | 이 플러그인의 compact 회차를 올린다. 알림 dedup 이 회차 단위라 compact 뒤 다시 알린다 |

모든 훅은 모델을 부르지 않고, 실패하면 조용히 통과한다. 메시지는 영어 `<harness-hook name="…" level="…">`.

## 규칙 주입 (`rules_inject.py`)
- 맞는 규칙 중 이 키로 아직 안 넣은 것을 `<rule plugin=… name=…>` 로 감싸 넣는다. Read 뒤에는 본문만, 그 키로 처음인 Edit·Write 뒤에는 본문과 "방금 쓴 것을 규칙에 대조하고 어긋나면 고쳐라" 한 문장.
- 키: (세션, 에이전트, compact 회차, 규칙). `O_EXCL` 마커라 병렬 호출에도 한 번만 들어간다.
- 넣지 않는 곳: `node_modules`, `.git`, `dist`, `build`, `.venv`, `vendor`, `__pycache__` 아래, 그리고 프로젝트 밖 Read(설정 디렉터리의 `projects/*/memory/` 는 예외). 프로젝트 밖이라도 편집은 넣는다.
- 도메인 팩(`packs/*`)의 규칙은 이 훅이 아니라 coderag 플러그인이 넣고, 이 파일이 그 대조 기준이다(`tools/tests/test-coderag-rules-parity.py`).
- 끄기: `HARNESS_CONVENTIONS_RULES=off`(환경 변수 또는 harness.env 층: 사용자 < 저장소 `.claude/harness.env` < 저장소 `.claude/harness.local.env`, `hooks/conv_env.py` 가 옆의 `hooks/harness_env.py` 사본으로 읽는다), 규칙별로는 저장소 `.claude/conventions.json` 의 `rules_exclude`.
- 켜기 스위치: 프론트매터에 `switch: <KEY>` 가 있는 규칙은 같은 harness.env 층에서 KEY 가 `on` 일 때만 넣는다(마커를 잡기 전에 거르므로 세션 중간에 켜도 다음 맞는 파일에서 실린다). 지금은 `readable-code` 의 `HARNESS_READABLE_CODE` 하나이고 기본값은 `off`(`conv_env.py` 의 `ENV_DEFAULTS`). 개인 취향이 동료 배포로 퍼지지 않게 사용자가 자기 `~/.claude/harness.env` 에서 켜고, 저장소는 `.claude/harness.env`(공유)나 `harness.local.env`(개인)에 `off` 를 두어 끈다. 사용자 전용 키가 아니라서 저장소 층이 이긴다. `bash-bypass-reminder` 도 꺼진 규칙은 이름을 대지 않는다.
- coderag 는 팩 규칙의 `switch` 를 읽지 않는다. 팩 규칙에 `switch` 를 쓰려면 coderag 에 같은 변경이 먼저 필요하다(대조 시험은 키를 켜고 꺼도 팩 규칙 주입이 같은지만 본다).

## 주석·문서 검사 (`conventions-check.py`)
이번에 추가한 줄만 본다(Edit 는 `new_string` 에서 `old_string` 에 없던 줄, Write 는 새 파일이면 전체, 덮어쓰기면 원본과의 차이). (세션, 에이전트, 파일, 범주)마다 한 번, level=info.

코드 파일의 주석 줄(확장자별 간이 렉서라 문자열 안의 `--`, `//`, `#` 는 주석이 아니다):
- history marker: 원장 번호, 날짜, 라운드, 작업 이력 경로, 결정 문구. 같은 주석 덩어리에 이유 문장이 있는 `Ref:` 꼬리는 통과.
- non-keyboard symbol: 키보드로 치지 않는 기호(가운뎃점 포함), 곡선 따옴표, 전각, 이모지. 모든 문자 체계의 글자와 숫자는 통과.
- escaped character: 주석 안의 `\uXXXX` 류 이스케이프.
- invisible character: 보이지 않는 문자와 방향 제어 문자. 코드 줄까지 본다.
- language mismatch: 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가한 줄이 다른 체계 단어를 3개 이상 쓴다. 새 파일은 저장소 `comment_language`, 없으면 같은 폴더 형제 파일의 다수.

모델용 문서(`CLAUDE.md`, `SKILL.md`, `agents/*.md`, `.claude/rules/*.md`, `skills/**/*.md`):
- 입구 문서: 날짜, audit·session·handoff 경로, 라운드, 결정 문구, 실측 표지, 변경 서술, `.md` 경로 없는 원장 id.
- `skills/**/references/*.md`: 결정 문구, 라운드, audit 근거, 실측 표지, 정정 배너만.
- frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰, `status:` 줄은 보지 않는다.

제외: 확장자 표 밖, 생성 파일(머리 6줄 표시), 픽스처, testdata, `node_modules`, 설정의 `exclude`.

단계 라벨 예외(늘 켜짐): 본문 안에 들여쓴 한 줄 주석이고, 위 줄은 주석만 있는 줄이 아니고 아래 줄은 코드이며, `label_language`(기본 `en`) 글자의 낱말 1~10개, 72자 이하, 마침표와 이유 접속어(`because`, `since`, `so`, `otherwise`, `unless`, `must`, `never`, `in order to`, `to avoid`)가 없는 줄은 language mismatch 판정과 파일 다수 계산에서 뺀다. 한국어 주석 파일에 영어 라벨을 다는 것이 readable-code 규약이라서다. `label_language: null` 이면 끈다.

## layout 알림 (readable-code)
`HARNESS_READABLE_CODE=on` 이고 확장자가 `.luau .lua .py .ts .tsx .js .jsx .mjs .rs .go .kt` 일 때만. 함수 범위와 지표는 `hooks/layout_metrics.py`(가장 바깥 함수만: Lua 계열은 `function`/`do`/`then`/`repeat` 와 `end`/`until`, Luau `if` 식은 블록이 아님; Python 은 `def` 와 들여쓰기; C 계열은 함수 머리 뒤 중괄호).
- 대상 함수: 이번 편집이 함수 줄(빈 줄 제외)의 절반 이상을 더했거나(`mostly`) 15줄 이상 더한(`grow`) 함수. 키운 함수는 함수 전체를 보고 알림에 `[grown by N lines]` 를 붙인다.
- layout: 본문 15줄 이상이고 빈 줄이 없거나 빈 줄 없이 20줄 넘게 이어짐. 사용자 손 코드(본문 15줄 이상)는 3/26, 에이전트 코드는 68/75 가 걸리는 선이다.
- interleaved comment: 본문 안에서 바로 위와 아래가 코드인 2줄 이상 주석 덩어리.
- doc summary: 공개 함수에 호버 꼴 문서 주석이 없음(Luau `---`/`--[=[`, Python docstring, TS/JS·Kotlin `/** */`, Rust `///`, Go `//`), 또는 문서 첫 줄 100자 초과, 또는 첫 문장이 첫 줄에서 안 끝남(첫 줄이 `.?!:` 나 한국어 종결 어미 없이 끝나고 다음 문서 줄이 이어짐). 메타메서드(`__x`)는 빼고, 문서가 있는 함수는 공개 여부와 무관하게 첫 줄을 본다. 공개: Luau `function M.x`/`M:x`/`M.x = function`, Python 은 `__main__` 블록이 없는 모듈의 맨 위 함수와 공개 클래스 메서드(`_` 시작 제외), TS/JS `export`, Rust `pub`, Go 대문자, Kotlin `private`/`internal`/`protected` 가 아닌 것. 알림 문구에 그 언어의 문서 꼴을 적는다.
- dedup: (세션, 에이전트, compact 회차, 파일, 범주, 함수)마다 한 번. doc summary 를 알린 함수는 다음 편집(같은 파일) 뒤 한 번 더 보고, 그대로면 `(still so after your last edit)` 로 다시 알린다.
- 주석 알림과 같은 level(info)이라 한 태그로 합친다. 범주당 함수 이름은 8개까지. Stop 보고에는 넣지 않는다.
- 기준: `.claude/conventions.json` 의 `"layout": {"min_lines": 15, "max_run": 20, "doc_first_max": 100, "grow": 15, "mostly": 0.5}`.
- Bash 로 고친 파일은 이 훅이 못 본다. `bash-bypass-reminder` 가 쓰기 신호가 있는 명령의 코드 파일마다 한 번 `conventions-scan.py layout <file>` 을 안내한다(키가 켜졌을 때만, level warn).
- 비용: 1,520줄 Luau 파일에 25줄 함수를 더하는 Edit 에서 훅 전체 중앙값이 키 off 69.8 ms, on 71.6 ms(1,440줄 Python 49.7, 51.0 ms).

## 남은 문제 보고
- 같은 PostToolUse 에서 편집한 파일의 "이번에 추가하지 않은 줄" 문제를 범주별로 세어 `$TMPDIR/claude-conventions/<session>.left.<main|agent_id>.json` 에 조용히 쌓는다(파일마다 마지막 편집 기준, 고치면 사라진다).
- Stop 이 모든 호출자 기록과 reuse-check 의 기록(`<session>.reuse.<who>.json`)을 합쳐 사용자에게 한 줄을 `systemMessage` 로 보인다. 직전 보고와 같으면 보이지 않는다. 파일은 5개까지. 사본이 원본과 다르면 둘째 줄이 붙는다.
- `systemMessage` 를 쓰는 이유: 모델을 거치지 않아 비용이 없고 빠지지 않는다. Stop 의 `additionalContext` 나 `decision` 은 턴을 이어 가게 해 매번 모델 호출과 보고 재작성 비용이 든다.

## 파일 전체 검사, 기계적 고치기 (`scripts/conventions-scan.py`)
훅이 아니라 사람이나 모델이 부르는 명령이다. "기존 문제도 정리해줘" 를 실제로 하려고 있다: 훅은 추가한 줄만 보고 남은 문제는 세기만 한다.
```bash
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py scan [경로...] [--json] [--category symbol ...] [--summary]
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py fix [경로...] --dry-run   # unified diff 만, 쓰지 않는다
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py fix [경로...]
```
- 검사: `conventions-check.py` 의 함수를 불러 모든 줄에 돌린다. 확장자 표, 제외, 생성 파일 표시, `.claude/conventions.json` 이 훅과 같다. 경로를 안 주면 저장소 전체, git 이면 `git ls-files -co --exclude-standard` 라 무시 파일은 보지 않는다. 주석 언어 기준은 파일 전체 다수(없으면 `comment_language`, 형제 파일).
- 출력: `경로:줄: 범주: 내용`, 범주별, 파일별 수, `--fix` 로 고칠 수 있는 추정. `--json` 은 `findings`, `needs_judgment`, `diffs`, `summary`. 종료 코드 0 = 남은 문제 없음, 1 = 있음, 2 = 사용법 오류.
- 고치는 것: 코드 파일 주석 안의 non-keyboard symbol 과 invisible character, 모델용 문서 본문의 invisible character(훅이 문서의 기호는 보지 않으므로 고치지도 않는다). 주석 안의 인라인 코드와 URL, 따옴표로 감싼 한 글자, 지시자 줄, 문서의 frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰은 그대로 둔다.
- 대체: 대시는 ` - `(숫자 사이 en dash, minus 는 `-`), 가운뎃점은 `, `(조각 맨 앞이면 `-`; `/` 는 곱을 나눗셈으로 바꿀 수 있어 쓰지 않는다), `…` 는 `...`, 화살표는 `->` `<-` `<->` `=>`, 곡선 따옴표는 곧은 따옴표, `§` 는 지운다, 동그라미 숫자는 `1)`, 전각은 ASCII, NBSP 는 공백, 그 밖의 보이지 않는 문자는 지운다(이모지 옆 ZWJ 와 파일 맨 앞 BOM 은 둔다). 규칙 전체는 스크립트 머리 주석.
- 사본(머리의 `@copy-of:` 로 다른 파일을 가리키는 파일, 정본이 아닌 `@start-replace` 영역)은 고치지 않고 `copies left unfixed` 로 알린다. 정본을 고치고 `tools/sync-copies.py --apply` 로 옮긴다. 사본을 따로 고치면 `--check` 가 깨진다.
- 판단이 필요한 것(이력, Ref 꼬리, 이스케이프, 언어, 이모지, 상자 그림, 표에 없는 기호, 코드 줄의 보이지 않는 문자)은 고치지 않고 "needs judgment" 로 남긴다.
- 토큰 가드: 고친 뒤 렉서로 다시 읽어 주석 밖 글자와 줄마다 주석 조각 수가 원본과 같아야 쓴다. 문서는 frontmatter, 펜스 줄, 보호 토큰이 같아야 한다. 다르면 쓰지 않고, 쓴 뒤 다시 읽어 어긋나면 원본 바이트로 되돌린다(`rejected`). 예: HTML 주석의 `-→` 를 `->` 로 바꾸면 `-->` 가 되어 주석이 일찍 닫히므로 거절된다.
- 렉서(`hooks/conv_lex.py`)는 주석 조각마다 열 위치(`s`)도 돌려준다. 고치기와 가드가 이것으로 주석 안만 바꾼다. `keep_code=True` 면 줄마다 주석을 지우고 문자열을 `""` 로 줄인 코드(`k`)와 여러 줄 주석·문자열 안에서 시작하는 줄 표시(`in`)도 준다(layout 지표용).
- `layout [경로...] [--json] [--summary]`: 함수마다 줄 수, 빈 줄, 문단, 최장 이어짐, 라벨, 끼운 여러 줄 주석, 한 줄 여러 선언(여러 반환 받기 `local ok, err = pcall(f)` 는 세지 않음), 한 글자 지역, 문서 주석 상태와 layout 알림 범주를 모든 함수에 대해 내고 요약(15줄 이상 함수 중 한 덩어리 수, 본문 100줄당 끼운 주석, 공개 함수 문서 범위)을 붙인다. 고치지 않는다. 키와 무관하게 돈다. 종료 코드 0 = 걸린 함수 없음, 1 = 있음.

## 사본 검사 (`reuse-check.py`)
- C1: `@copy-of: <경로>[#이름]` 사본이 원본과 같은가(파일은 바이트, 값은 문자열 묶음). 풀리지 않거나 다르면 알린다.
- C2: 원본을 고치면 그것을 가리키는 사본 목록을 알린다.
- H1: 추가한 문자열 묶음(따옴표 문자열 3개 이상의 목록이나 `"a" | "b"` 합집합)이 저장소의 다른 정의와 겹침. 기본은 그림자 모드라 알리지 않고 `${CLAUDE_PLUGIN_DATA}/reuse-shadow.jsonl`(없으면 `$TMPDIR/claude-qwreey-reuse/shadow.jsonl`)에 남긴다.
- 모드: `REUSE_CHECK=off|shadow|on` 이 저장소 `.claude/conventions.json` 의 `reuse.mode` 를 이긴다. 기본 `shadow`. `CONVENTIONS_CHECK=off` 도 이 훅을 끈다.
- 색인: `$TMPDIR/claude-qwreey-reuse/<저장소 해시>.json`, 바뀐 파일만 다시 읽는다. 첫 색인은 300ms 에서 끊고 다음 편집에서 이어 만든다.
- 제외: `.claude/`, `*-ignoreme*`, 벤더 트리, 생성 파일, 시험·stories·examples.
- conventions-check 와 프로세스를 나눈 이유: 같은 이벤트의 훅은 병렬이라 합치면 둘의 시간이 더해지고, 공유할 상태가 거의 없다.

## 파일 길이 (`structure-reminder.py`)
- warn: 경고 기준(기본 800줄) 초과. hard: 강제 기준(기본 1,500줄) 초과, 더 덧붙이기 전에 분리안을 사용자에게 묻게 한다. grow: 이번 세션에 300줄 넘게 늘고 경고 기준 이상. flat: 새 파일을 만든 폴더에 소스 15개 이상, 하위 폴더 2개 이하. family: 같은 PascalCase 접두 파일이 셋 이상. 모두 세션당 한 번.
- 대상 확장자는 툴킷 표(luau, web, rust, python, go, jvm). `HARNESS_TOOLKITS` 가 있으면 그 툴킷만. 테스트 파일은 기준 두 배.
- Bash 는 파일을 바꿨을 법한 명령(`sed -i`, 리다이렉트, `tee`, `patch`, 인터프리터)에 든 소스 경로만 본다.
- 예외: 파일 머리 10줄 안 `--@structure-exempt: <사유>`(언어별 주석 표식) 또는 `structure.json` 의 `exempt`. 사유가 비었거나 "나중에", "TODO" 같은 말이면 무효.
- 저장소 설정: `.claude/structure.json` 의 `warn`, `hard`, `grow`, `flat`, `ignore`, `exempt`, `toolkits`. 형식은 스크립트 머리 주석.
- 끄기: `STRUCTURE_REMINDER=off`.

## 메모 배치 (`memory-placement.py`)
auto memory 디렉터리(`<config>/projects/*/memory/` 또는 `autoMemoryDirectory`)에 쓴 `MEMORY.md` 가 아닌 파일을 `memory_signals.py` 로 분류해, 경로·빌드 명령·규약·함정 같은 저장소 지식으로 보이면 저장소로 옮기라고 알린다(level=warn). `type: user` 는 알리지 않는다. 같은 파일은 (세션, 호출자, compact 회차)당 한 번. 끄기: `MEMORY_PLACEMENT=off`.

## 답변 언어 (`reply_language.py`)
메인 대화만 본다.
- 언어 출처(좁은 쪽이 이김): 프로젝트 `.claude/settings.local.json` > `.claude/settings.json` > 사용자 `settings.json` 의 `language`, 없으면 `${CLAUDE_PLUGIN_DATA}/language.json`. 둘 다 없으면 UserPromptSubmit 이 세션당 한 번 "요청에 먼저 답하고 끝에서 언어를 물어 `reply_language.py set <language>` 로 저장하라" 고 알린다.
- Stop: 마지막 답의 목표 문자 비율이 0.25 미만이고 라틴 글자가 20자 이상이면 `decision: block` 으로 다시 쓰게 한다. 사용자가 이번 턴에 영어로만 썼으면 통과하고, `stop_hook_active` 면 통과한다(루프 방지). 라틴 문자 언어는 감지하지 않는다.
- PostToolBatch: 도구 호출 사이 텍스트가 이탈이면 info(쿨다운), 한 요청의 도구 호출이 10회, 이후 15회마다 info 한 줄.
- 기록: `${CLAUDE_PLUGIN_DATA}/drift.jsonl`(본문 없음). 끄기: `HARNESS_REPLY_LANGUAGE=off`(환경 변수 또는 harness.env).

## 저장소 설정
`<프로젝트>/.claude/conventions.json`(없으면 예전 이름 `.claude/comments.json`): `comment_language`, `allow_chars`, `public_ids`, `exclude`, `patterns`, `allow_ref_tail`, `min_reason_words`, `label_language`, `layout`(형식은 `comments` 스킬), `reuse`(`mode`, `allow`, `vocab_ok`, `min_shared`, 형식은 `code-reuse` 스킬), `rules_exclude`. 파일 길이는 `.claude/structure.json`. 사용자 설정 위치는 `$CLAUDE_CONFIG_DIR`(기본 `~/.claude`).

## 플랫폼
훅은 표준 라이브러리 Python 3 이다. 상태는 `tempfile.gettempdir()` 아래에 둔다.

## 테스트
```bash
python3 -I plugins/qwreey-conventions/tests/test-conventions-check.py
python3 -I plugins/qwreey-conventions/tests/test-conventions-scan.py
python3 -I plugins/qwreey-conventions/tests/test-structure-reminder.py
python3 -I plugins/qwreey-conventions/tests/test-reuse-check.py
python3 -I plugins/qwreey-conventions/tests/test-memory-placement.py
python3 -I plugins/qwreey-conventions/tests/test-rules-inject.py
python3 -I plugins/qwreey-conventions/tests/test-reply-language.py
python3 -I plugins/qwreey-conventions/tests/test-bash-bypass-reminder.py
```
모델을 부르지 않는다.
