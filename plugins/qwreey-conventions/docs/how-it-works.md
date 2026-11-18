# qwreey-conventions 동작 상세

구성: 모델이 부르는 스킬 하나(`code-reuse`), 사용자 명령 둘(`comments-cleanup`, `docs-cleanup`), 경로 한정 규칙 여섯(`rules/*.md`, 맞는 파일을 열 때 훅이 주입, 하나는 켜기 스위치가 있다), 알림 훅(`hooks/hooks.json`). 훅은 막지 않는다. 답변 언어 지키기는 [qwreey-reply-language](../../qwreey-reply-language/docs/how-it-works.md) 플러그인이 한다. `.claude/` 기록 규약은 이 플러그인에 없고 coderag 플러그인의 `coderag:agent-records` 가 맡는다.

## 스킬과 규칙
| 이름 | 다루는 것 |
|---|---|
| `/qwreey-conventions:comments-cleanup [경로]` | 사용자 명령(`disable-model-invocation`): 코드 파일의 기존 주석을 `conventions-scan.py --kind comment` 로 검사하고 `fix` 로 기계적인 것을 고친 뒤 나머지를 다시 쓴다 |
| `/qwreey-conventions:docs-cleanup [경로]` | 사용자 명령: 모델용 문서를 `conventions-scan.py --kind doc` 으로 검사하고 보이지 않는 문자를 지운 뒤 이력 줄을 지금의 사실로 다시 쓰고, 옮길 이력을 보고에 모은다 |
| `qwreey-conventions:code-reuse` | 경계를 넘는 사본의 표시(`@copy-of`, `@start-replace`), 영역과 동기화, 사본 비교 시험, 라이브러리와 직접 구현을 가르는 측정, 중복 판단 순서 |

규칙 파일: `comments`, `agent-docs`, `code-structure`, `code-reuse`, `memory`, `readable-code`. 각 파일의 `paths:` 가 대상이다. 플러그인은 `.claude/rules` 를 실을 수 없어서 훅이 같은 시점에 같은 본문을 넣는다.

`comments` 와 `agent-docs` 는 스킬 없이 규칙 하나다. 모델이 지킬 것은 모두 본문에 있고, 기계로 볼 수 있는 것(이력 표지, 스킬 description 꼴, 모델용 문서 언어, 원장 id 경로)은 훅 알림이 줄과 고치는 법을 준다. 실제 기록에서 쓰기 79번 중 comments 스킬 로드는 0번, 모델용 문서 쓰기 35번 중 agent-docs 스킬 로드는 1번이었고 알림을 받고 고친 것은 대부분 스킬 없이였다. 사람이 찾아볼 알림 표와 설정은 [comments.md](comments.md), [agent-docs.md](agent-docs.md) 에 있다.

`code-reuse` 는 규칙이 지킬 것을 말하고, 스킬은 정의를 다른 패키지나 저장소로 옮겨 적을 때의 절차와 라이브러리 선택 단계만 맡는다. 그래서 description 을 그 작업들로 좁혔고 규칙 끝의 "Before you add a `@copy-of` or `@start-replace` marker, or act on a reuse notice, load ..." 줄이 스킬을 가리킨다. 정책·불변식 표와 저장소 설정(`reuse`)은 [code-reuse.md](code-reuse.md) 에 있다.

`readable-code` 는 함수 안 문단(빈 줄), 단계 라벨, 호버에 보이는 문서 주석, 이유 주석의 자리, 선언과 이름, 분기 사다리, 되풀이 루프를 말한다. `comments` 처럼 규약 전체를 본문에 둔다(약 2.3k자): 규칙 끝의 스킬 포인터는 실제 세션에서 거의 읽히지 않았다. 언어 중립으로 쓰고, Luau 의 `---` 같은 툴킷 꼴은 툴킷 팩 규칙(luau-kb `luau-core`)이 말한다. 프론트매터 `switch: HARNESS_READABLE_CODE` 라서 그 키가 `on` 일 때(기본) 실리고 `off` 면 빠진다(아래 규칙 주입).

## 훅
| 이벤트(matcher) | 스크립트 | 하는 일 |
|---|---|---|
| PostToolUse(Read·Edit·Write·MultiEdit·NotebookEdit) | `rules_inject.py` | 규칙 주입 |
| PostToolUse(Write·Edit·MultiEdit), Stop | `conventions-check.py` | 추가한 줄의 주석·문서 검사, readable-code 를 켰으면 쓰거나 키운 함수의 layout 알림(`layout_metrics.py`), Stop 에서 남은 문제 보고 |
| PostToolUse(Write·Edit·MultiEdit) | `reuse-check.py` | 사본 검사 |
| PostToolUse(Write·Edit·Bash) | `structure-reminder.py` | 파일 길이, 세션 성장, 폴더 과밀 |
| PostToolUse(Write·Edit·MultiEdit) | `memory-placement.py` | auto memory 에 쓴 저장소 지식 |
| PreToolUse(Bash) | `bash-bypass-reminder.py` | 셸·인터프리터로 파일을 바꾸면 Edit·Write 훅과 저장소 rules 를 비껴간다는 알림, 쓰기 신호가 있으면 Bash 검사용 스냅숏 |
| PostToolUse(Bash), PostToolUseFailure(Bash) | `bash_writes.py` | 명령이 바꾼 파일의 추가 줄에 `conventions-check.py` 와 같은 검사, 사본 검사, 아직 안 보인 규칙 주입 |
| PreCompact(manual·auto) | `compact_epoch.py qwreey-conventions` | 이 플러그인의 compact 회차를 올린다. 알림 dedup 이 회차 단위라 compact 뒤 다시 알린다 |

모든 훅은 모델을 부르지 않고, 실패하면 조용히 통과한다. 메시지는 영어 `<harness-hook name="…" level="…">`.

## 규칙 주입 (`rules_inject.py`)
- 맞는 규칙 중 이 키로 아직 안 넣은 것을 `<rule plugin=… name=…>` 로 감싸 넣는다. Read 뒤에는 본문만, 그 키로 처음인 Edit·Write 뒤에는 본문과 "방금 쓴 것을 규칙에 대조하고 어긋나면 고쳐라" 한 문장.
- Bash 로 쓴 파일은 `bash_writes.py` 가 이 파일의 함수와 같은 마커로 넣는다(아래 Bash 쓰기 검사). 이 파일의 동작은 그대로라 coderag 대조와 무관하다.
- 키: (세션, 에이전트, compact 회차, 규칙). `O_EXCL` 마커라 병렬 호출에도 한 번만 들어간다.
- 넣지 않는 곳: `node_modules`, `.git`, `dist`, `build`, `.venv`, `vendor`, `__pycache__` 아래, 그리고 프로젝트 밖 Read(설정 디렉터리의 `projects/*/memory/` 는 예외). 프로젝트 밖이라도 편집은 넣는다.
- 저장소 설정 줄: `comments` 규칙을 넣을 때 편집하는 파일의 저장소(`conventions-check.py` 와 같은 `conv_edit.project_root`) `.claude/conventions.json`(없으면 `comments.json`)에 언어 코드 꼴의 `comment_language` 가 있으면 제목 아래에 `- This repo: comment_language = en. ...` 한 줄을 넣는다. 모델은 쓰기 전에 스킬을 열지 않아 스킬에만 있는 설정은 지켜지지 않기 때문이다. 키가 없거나 설정을 못 읽으면 본문 그대로이고, 다른 규칙과 팩 규칙에는 붙지 않는다.
- 도메인 팩(`packs/*`)의 규칙은 이 훅이 아니라 coderag 플러그인이 넣고, 이 파일이 그 대조 기준이다(`tools/tests/test-coderag-rules-parity.py`).
- 끄기: 옵션 `harness_conventions_rules`(= `HARNESS_CONVENTIONS_RULES=off`; 층은 사용자 harness.env < 플러그인 옵션 < 저장소 `.claude/harness.env` < 저장소 `.claude/harness.local.env` < 환경 변수, `hooks/conv_env.py` 가 옆의 `hooks/harness_env.py` 사본으로 읽는다), 규칙별로는 저장소 `.claude/conventions.json` 의 `rules_exclude`.
- 켜기 스위치: 프론트매터에 `switch: <KEY>` 가 있는 규칙은 같은 harness.env 층에서 KEY 가 `on` 일 때만 넣는다(마커를 잡기 전에 거르므로 세션 중간에 켜도 다음 맞는 파일에서 실린다). 지금은 `readable-code` 의 `HARNESS_READABLE_CODE` 하나이고 기본값은 `on`(`conv_env.py` 의 `ENV_DEFAULTS`): 플러그인을 깐 것이 쓰겠다는 뜻이라 따로 켜지 않는다. 사용자는 옵션 `harness_readable_code`(`/config`)나 자기 `~/.claude/harness.env` 에서 끄고, 저장소는 `.claude/harness.env`(공유)나 `harness.local.env`(개인)에 `off` 를 두어 끈다. `on` 이 아닌 값(`0`, `false` 포함)은 모두 꺼짐이다. 사용자 전용 키가 아니라서 저장소 층이 이긴다. `bash-bypass-reminder` 도 꺼진 규칙은 이름을 대지 않는다.
- coderag 는 팩 규칙의 `switch` 를 읽지 않는다. 팩 규칙에 `switch` 를 쓰려면 coderag 에 같은 변경이 먼저 필요하다(대조 시험은 키를 켜고 꺼도 팩 규칙 주입이 같은지만 본다).

## 주석·문서 검사 (`conventions-check.py`)
이번에 추가한 줄만 본다(Edit 는 `new_string` 에서 `old_string` 에 없던 줄, Write 는 새 파일이면 전체, 덮어쓰기면 원본과의 차이, Bash 는 아래 Bash 쓰기 검사). (세션, 에이전트, 파일, 범주)마다 한 번, level=info. 주석 알림은 범주마다 줄 번호와 고치는 법(대체 문자, 코드포인트, 옮길 곳, 써야 할 언어)을 함께 주고 "그 줄을 고치고, 오탐은 두되 보고에 한 번 적으라" 로 끝난다. 스킬을 열라고 하지 않는다: 실제 기록에서 스킬 이름을 단 알림 42건 중 로드는 1건이었고 알림만 보고 고친 것이 약 32건이었다. 모델용 문서 알림도 같은 꼴로 범주마다 고치는 법을 주고 같은 문장으로 끝난다.

코드 파일의 주석 줄(확장자별 간이 렉서라 문자열 안의 `--`, `//`, `#` 는 주석이 아니다):
- history marker: 원장 번호, 날짜, 라운드, 작업 이력 경로, 결정 문구, 변경 서술. 같은 주석 덩어리에 이유 문장이 있는 `Ref:` 꼬리는 통과.
  - 변경 서술은 정밀도 쪽으로 좁혔다. 절 머리(주석 시작, `.;:!?` 와 공백 뒤, 여는 괄호 뒤)의 `Previously`(쉼표나 낱말이 뒤따름, `Previously-seen` 은 아님)와 `It`/`This`/`We`/`They used to`, 어디서나 `예전에는`/`예전엔`, 절 머리(쉼표 뒤 포함)의 `이전에는`/`이전엔`, `기존에는`/`기존엔` 뒤 같은 문장의 과거 어미(있, 겠을 뺀 받침 ㅆ 음절 다음 `다`, `습니다`, `어요`, `죠`, `던`, `지만`, `는데`). `the previously selected item`, `the buffer it used to hold`, `초기화 이전에는`, `Start() 이전엔`, `기존엔 키가 있을 수 있다` 처럼 코드가 하는 일을 말하는 꼴은 걸리지 않는다. quad, tbox, stl-luau, coderag, claude-doctor 의 추적 파일에서 걸리는 주석 줄은 32, 20, 156, 0, 0 이고(앞 패턴은 36, 20, 156, 0, 0; 빠진 넷은 명사 뒤 `it used to` 와 `이 파일 이전엔`), 둘러본 줄은 모두 변경 서술이었다.
- non-keyboard symbol: 키보드로 치지 않는 기호(가운뎃점 포함), 곡선 따옴표, 전각, 이모지. 모든 문자 체계의 글자와 숫자는 통과.
- escaped character: 주석 안의 `\uXXXX` 류 이스케이프.
- invisible character: 보이지 않는 문자와 방향 제어 문자. 코드 줄까지 본다.
- language mismatch: 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가한 줄이 다른 체계 단어를 3개 이상 쓴다. 새 파일은 저장소 `comment_language`, 없으면 같은 폴더 형제 파일의 다수.

모델용 문서(`CLAUDE.md`, `SKILL.md`, `agents/*.md`, `.claude/rules/*.md`, `skills/**/*.md`):
- 입구 문서: 날짜, audit·session·handoff 경로, 라운드, 결정 문구, 실측 표지, 변경 서술, `.md` 경로 없는 원장 id.
- `skills/**/references/*.md`: 결정 문구, 라운드, audit 근거, 실측 표지, 정정 배너만.
- frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰, `status:` 줄은 보지 않는다.
- 꼴(`hooks/conv_docs.py` 의 `doc_shape`, 추가한 줄만. 남은 문제 보고와 `conventions-scan.py` 에는 넣지 않는다: 한국어로 쓴 기존 문서가 통째로 걸린다):
  - skill description: `SKILL.md` frontmatter 의 `description` 이 끝의 한국어 계기 문구(한국어가 라틴 낱말보다 많거나 `트리거` 로 시작하는 끝 문장들, 따옴표 안은 세지 않음)를 빼고도 한국어 낱말이 3개 이상, 언제 쓰는지(`when`, `before`, `Use for` 등)가 없음, 1·2인칭(`I can`, `you can`). `disable-model-invocation: true` 면 메뉴 줄이라 보지 않는다. description 줄을 고친 편집에서만 본다.
  - language mismatch: 본문 줄(따옴표, 인라인 코드, URL 제외)의 한국어 낱말이 3개 이상이고 라틴 낱말 이상. 고치지 않은 줄 중 한국어 줄이 3개 이상이고 10% 를 넘는 문서는 이미 한국어로 쓴 것으로 보고 따른다(luau-kb 스킬, q 의 사용자 안내 문서).
  - ledger id path: 입구 문서에서 원장 id 와 `.md` 경로가 같은 줄에 있는데, 그 경로가 문서 폴더, 플러그인 루트(`.claude-plugin` 이 있는 가장 가까운 폴더, 없으면 저장소), 저장소 루트 어디에서 풀어도 플러그인 안의 있는 파일이 아님.
  - 이 저장소와 coderag 의 추적 파일 전체를 한 줄씩 추가한 것으로 놓고 돌린 결과: claude-doctor 는 description 5(모두 `.claude/` 초안), 언어 8줄(4파일; 살아 있는 파일은 `q` doctor 의 사용자용 표 머리 1줄), 원장 경로 0. coderag 는 description 10(모두 `experiments/team-audit/corpus/` 시험 자료), 언어 0, 원장 경로 0.

제외: 확장자 표 밖, 생성 파일(머리 6줄 표시), 픽스처, testdata, `node_modules`, 설정의 `exclude`.

단계 라벨 예외(늘 켜짐): 본문 안에 들여쓴 한 줄 주석이고, 위 줄은 주석만 있는 줄이 아니고 아래 줄은 코드이며, `label_language`(기본 `en`) 글자의 낱말 2~10개, 72자 이하, 마침표와 이유 접속어(`because`, `since`, `so`, `otherwise`, `unless`, `must`, `never`, `in order to`, `to avoid`, `due to`, `workaround`)가 없는 줄은 language mismatch 판정과 파일 다수 계산에서 뺀다. 한국어 주석 파일에 영어 라벨을 다는 것이 readable-code 규약이라서다. `label_language: null` 이면 끈다.

## layout 알림 (readable-code)
`HARNESS_READABLE_CODE` 가 `on`(기본)이고 확장자가 `.luau .lua .py .ts .tsx .js .jsx .mjs .rs .go .kt` 일 때만. 함수 범위와 지표는 `hooks/layout_metrics.py`(가장 바깥 함수만: Lua 계열은 `function`/`do`/`then`/`repeat` 와 `end`/`until`, Luau `if` 식은 블록이 아님(`<`/`>` 뒤는 같은 줄일 때만 식: 줄 끝 제네릭이나 캐스트 다음 줄의 `if` 는 문); Python 은 `def` 와 들여쓰기(한 줄 `def` 포함, 머리는 50줄까지만 찾음); C 계열은 함수 머리 뒤 깊이 0 의 첫 `{`, 매개변수·제네릭·반환 타입 안의 중괄호는 본문이 아님).
- 대상 함수: 이번 편집이 함수 줄(빈 줄 제외)의 절반 이상을 더했거나(`mostly`) 15줄 이상 더한(`grow`) 함수. 키운 함수는 함수 전체를 보고 알림에 `[grown by N lines]` 를 붙인다.
- layout: 본문 15줄 이상이고 빈 줄이 없거나 빈 줄 없이 20줄 넘게 이어짐. 사용자 손 코드(본문 15줄 이상)는 3/26, 에이전트 코드는 68/75 가 걸리는 선이다.
- interleaved comment: 본문 안에서 바로 위와 아래가 코드인 2줄 이상 주석 덩어리.
- doc summary: 공개 함수에 호버 꼴 문서 주석이 없음(Luau `---`/`--[=[`, Python docstring, TS/JS·Kotlin `/** */`, Rust `///`, Go `//`; 함수 바로 위에서 가장 가까운 주석이 문서 꼴이어야 하고, 그 위의 이유 주석과 `--#region` 같은 접기 표지는 상관없음), 또는 문서 첫 줄 100자 초과, 또는 첫 문장이 첫 줄에서 안 끝남(첫 줄이 `.?!:` 나 한국어 종결 어미 없이 끝나고 다음 문서 줄이 이어짐). 메타메서드(`__x`)는 빼고, 문서가 있는 함수는 공개 여부와 무관하게 첫 줄을 본다. 공개: Luau `function M.x`/`M:x`/`M.x = function`, Python 은 `__main__` 블록이 없는 모듈의 맨 위 함수와 공개 클래스 메서드(`_` 시작 제외), TS/JS `export`, Rust `pub`, Go 대문자, Kotlin `private`/`internal`/`protected` 가 아닌 것. 알림 문구에 그 언어의 문서 꼴을 적는다.
- dedup: (세션, 에이전트, compact 회차, 파일, 범주, 함수)마다 한 번. 함수는 이름으로 가리고, 같은 파일에 같은 이름이 또 있으면 두 번째부터 `이름#순번`이다. doc summary 를 알린 함수는 다음 편집(같은 파일) 뒤 한 번 더 보고, 그대로면 `(still so after your last edit)` 로 다시 알린다.
- 주석 알림과 같은 level(info)이라 한 태그로 합친다. 범주당 함수 이름은 8개까지. Stop 보고에는 넣지 않는다.
- 기준: `.claude/conventions.json` 의 `"layout": {"min_lines": 15, "max_run": 20, "doc_first_max": 100, "grow": 15, "mostly": 0.5}`.
- Bash 로 고친 파일도 `bash_writes.py` 가 같은 함수로 본다(아래 Bash 쓰기 검사).
- 비용: 1,520줄 Luau 파일에 25줄 함수를 더하는 Edit 에서 훅 전체 중앙값이 키 off 69.8 ms, on 71.6 ms(1,440줄 Python 49.7, 51.0 ms).

## Bash 쓰기 검사 (`bash_writes.py`)
heredoc, `sed -i`, `python3 - <<`, `tee`, 리다이렉트로 쓰면 Edit·Write 매처의 훅이 돌지 않는다. 실제 기록에서 규약이 걸린 쓰기 173번 중 69번이 이 경로라 알림도 규칙 주입도 없었다. 그래서 명령 전후를 비교해 Edit·Write 와 같은 검사를 돌린다.
- 명령 전(PreToolUse, `bash-bypass-reminder.py` 가 `bash_writes.snapshot` 을 부름): 쓰기 신호(제자리 편집 `sed -i`·`perl -pi`·`patch`·`git apply`, 쓰는 인터프리터 스크립트, 저장소나 cwd 안으로의 리다이렉트·`tee`)가 있을 때만. 명령 첫 낱말이 `git`·`gh` 면 하지 않는다(리마인더와 같은 조건). 저장소는 명령 cwd 의 git 최상위(git 이 아니면 프로젝트 폴더)이고 그 밖의 경로, 줄바꿈이 든 경로는 보지 않는다. 적는 것: 명령에 든 경로(named)의 지금 내용(없으면 null, 파일당 1 MB)과 (mtime, 크기), git 이면 HEAD, `git --no-optional-locks status --porcelain -z -uall` 의 파일별 (mtime, 크기)(400개까지), 그중 검사 대상 확장자 파일의 지금 내용(파일당 256 KiB). 내용은 named 를 포함해 모두 4 MiB 까지다. 일반 파일만 읽는다(O_NONBLOCK 으로 열어 fstat 로 확인하므로 FIFO 에 멈추지 않는다).
- 저장 위치: `$TMPDIR/claude-conventions/bash/<세션>.<main|agent>.<tool_use_id>.json`, TMPDIR(TEMP, TMP)가 없으면 공유 `/tmp` 대신 `/tmp/claude-conventions-<uid>/bash/`. 폴더는 0700 으로 만들고 이 사용자 것이 아니거나 심볼릭 링크면 스냅숏을 쓰지 않는다. 파일은 0600. Post 가 지우고, 1시간 넘은 것은 모든 PreToolUse(Bash) 가 지운다(폴더 하나 읽기).
- 명령 뒤(PostToolUse, 0 아닌 종료면 PostToolUseFailure, 둘 다 `bash_writes.py`. 입력의 `tool_name`, `tool_input`, `tool_use_id` 가 같고 출력 `hookEventName` 은 받은 이벤트 이름): 스냅숏이 없으면 바로 끝난다. 바뀐 파일과 전 내용은 이렇게 정한다. 내용을 적어 둔 파일은 지금과 다르면 바뀜, 명령 전에 깨끗했는데 지금 porcelain 에 나온 파일은 명령 전 HEAD 의 blob(`git cat-file --batch` 한 번), 명령이 커밋까지 했으면 두 HEAD 사이(`git diff --name-only`)의 파일도 같다. 내용을 적지 못한 파일(크기 한도 밖)은 바뀌어도 검사하지 않고 규칙 주입에만 쓴다.
- porcelain 이 400개를 넘으면(overflow) 명령 전 상태를 모르는 항목은 바뀐 것으로 보지 않는다. named 와 (mtime, 크기)를 적어 둔 400개만 보고, 두 HEAD 사이 비교도 하지 않는다. untracked 가 많은 저장소에서 남의 파일 전체를 새로 쓴 것으로 알리지 않으려는 것이다.
- Post 의 읽기는 1.5초, 4 MiB, 200개 파일에서 끊는다. 한도로 못 읽은 검사 대상 파일은 아래 `N more files` 줄로 넘기고, 적어 둔 파일은 (mtime, 크기)가 바뀌었으면 규칙 주입에만 쓴다. 바뀐 경로는 규칙 맞춤에 500개까지 넘긴다. 측정(coderag 사본): untracked `.js` 6만 개가 있는 저장소에서 `echo 'w = 1' >> b.py` 의 Post 가 1.8~1.9 s(그 파일들을 새로 쓴 것으로 알림)에서 0.33 s(알림 없음)로, 명령이 `.js` 2만 개를 만들 때 Post 0.6 s(알림 10개, 규칙 주입, scan 줄).
- 명령 전에 없던 파일(새 파일, untracked, HEAD 에 없는 경로)의 전 내용은 named 의 적어 둔 내용과 그 경로들의 HEAD blob 을 합친 것이다. `mv a.py c.py && sed ...`, `cp a.py b.py; echo ... >> b.py` 에서 옮기거나 베낀 옛 줄을 새로 쓴 줄로 세지 않는다.
- 추가 줄은 Write 덮어쓰기와 같은 셈(`conv_edit.added_set`: 지금 줄 중 전 내용에 없던 줄)이고, `conventions-check.py` 의 `file_notice` 를 그대로 부른다. 그래서 알림 글, 범주, layout 알림, 남은 문제 기록, 상태 파일과 중복 거르기가 Edit 경로와 같다(Bash 로 알린 범주는 뒤의 Edit 에서 다시 알리지 않고, 반대도 같다). 상태 파일의 읽기, 알림, 쓰기는 `fcntl` 잠금(`<상태>.lock`, 3초 기다림, 없거나 못 잡으면 잠그지 않음) 안에서 해서 나란히 끝난 Bash 둘이 같은 알림을 두 번 내지 않는다. Edit 경로도 같은 잠금을 쓴다.
- 코드 파일은 `reuse-check.py` 를 Write 꼴 입력(전 내용을 `originalFile` 로)으로 4개까지 나란히 돌려 사본 알림을 합친다.
- 규칙: 바뀐 모든 파일(검사 확장자 밖 포함, 의존성 폴더 제외)에 맞는 이 플러그인의 규칙 중 이 맥락에 아직 안 넣은 것을 `rules_inject.py` 의 함수와 마커로 넣는다(Edit·Write 뒤와 같은 "대조하고 고쳐라" 문장).
- 출력 하나(`additionalContext`)를 9,000자 안에 둔다. 알림을 파일 순서로 넣다가 안 드는 파일에서 멈추고 ``N more files: run `python3 -I <scan> scan <경로...>` `` 한 줄로 넘긴다(담지 못한 파일의 알림은 알린 것으로 적지 않는다). 사본 알림은 남은 자리에 드는 것만, 규칙은 그 뒤 남은 자리에 드는 것만 마커를 잡고 나머지는 다음 Read·Edit 에 맡긴다.
- 같은 명령에 worktree 를 다시 쓰는 git 하위 명령(`checkout`, `switch`, `stash`, `reset`, `merge`, `rebase`, `pull`, `cherry-pick`, `revert`, `restore`, `am`; `git -c k=v`, `git -C dir`, `git --no-pager` 같은 전역 옵션 뒤도, 그리고 `gh pr checkout`)이 있으면 porcelain 비교를 하지 않고 named 만 본다. 그중 지금 내용이 이미 git 객체로 있는 파일(`git hash-object --stdin-paths` 와 `cat-file --batch-check`, 객체를 쓰지 않음)은 git 이 되돌리거나 꺼낸 것으로 보고 건너뛰고, 나머지는 명령 전 HEAD 와 지금 HEAD 의 blob 줄도 전 내용으로 친다. 되돌린 줄을 새로 쓴 줄로 오인하지 않으려는 것이다.
- 같은 세션(서브에이전트 포함)의 다른 스냅숏이 10분 안에 만들어져 아직 남아 있으면(다른 Bash 가 도는 중) Pre 와 Post 어느 쪽에서 보든 named 만 본다. 그 Bash 가 바꾼 파일을 이 명령의 것으로 세지 않으려는 것이다.
- 한도: 알림을 낸 파일 10개, 분석 2.5초, 출력 9,000자에서 끊고, 남은 파일은 `conventions-scan.py scan <파일...>` 을 안내한다.
- 끄기: `CONVENTIONS_CHECK=off`(검사, 사본), `HARNESS_CONVENTIONS_RULES=off`(규칙). 둘 다 꺼지면 스냅숏도 만들지 않는다.
- 못 보는 것:
  - 거절되거나 사용자가 취소한 명령(Post 가 오지 않는다. 스냅숏은 1시간 뒤 지워지고, 그 전 10분 동안은 같은 세션의 다음 Bash 가 named 만 본다), `run_in_background` 명령(Post 가 명령을 띄운 직후에 와서 그 뒤의 쓰기를 못 본다), 첫 낱말이 `git`·`gh` 인 명령, 쓰기 신호가 없는 명령(예: 저장소 스크립트 실행 `python3 tools/gen.py`, `cp`, `mv` 만 있는 명령).
  - 명령에 경로가 없고 git 저장소도 아닌 곳의 쓰기, 크기 한도 밖의 파일, porcelain 이 400개를 넘는 저장소에서 named 가 아닌 파일과 적지 못한 항목.
  - git rewrite 가 든 명령에서 HEAD 가 아닌 곳(다른 브랜치, `stash pop`, `restore --source`)에서 꺼낸 줄을 다시 고친 named 파일: 그 줄도 추가로 셀 수 있다.
  - 다른 프로세스의 쓰기: 명령이 도는 동안 포매터, 파일 감시 도구, 다른 세션이 바꾼 파일은 이 명령의 것으로 센다. 같은 세션의 나란한 Bash 는 위처럼 named 로 줄이지만, named 파일을 둘이 함께 바꾸면 둘 다 그 줄을 본다(같은 범주 알림은 잠금으로 한 번).
- 비용(중앙값, 프로세스 기동 포함): 쓰기 신호가 없는 명령은 Post 25~29 ms(스냅숏 유무만 본다), Pre 는 원래 리마인더 30 ms 그대로(스냅숏 폴더 읽기 포함). 쓰기 신호가 있으면 Pre 45~62 ms, Post 90~130 ms(규칙 주입 포함, 사본 색인이 데워진 뒤). 실제 quad, coderag 에서 쓰지 않고 잰 값(Pre 쓰기 신호, 바뀐 것 없는 Post)은 quad 60, 48 ms, coderag 51, 41 ms 이고, 쓰기는 `git clone --shared` 사본에서 quad Post 129 ms, coderag 114 ms 다. 측정은 임시 저장소, coderag 사본(338 파일), quad 사본(6,193 파일, 15 GB 작업 트리)에서 했고 quad 의 첫 Post 는 사본 색인을 처음 만들어 400 ms 였다. 같은 이벤트의 훅은 나란히 돌므로 Post 의 25 ms 는 structure-reminder 와 겹친다. `tests/test-bash-writes.py` 의 `Timing`(`BIG_REPO=<사본>`)이 같은 숫자를 낸다.

## 남은 문제 보고
- 같은 PostToolUse 에서 편집한 파일의 "이번에 추가하지 않은 줄" 문제를 범주별로 세어 `$TMPDIR/claude-conventions/<session>.left.<main|agent_id>.json` 에 조용히 쌓는다(파일마다 마지막 편집 기준, 고치면 사라진다).
- Stop 이 모든 호출자 기록과 reuse-check 의 기록(`<session>.reuse.<who>.json`)을 합쳐 사용자에게 한 줄을 `systemMessage` 로 보인다. 코드 파일의 주석 문제가 있으면 `/qwreey-conventions:comments-cleanup` 을, 모델용 문서의 문제가 있으면 `/qwreey-conventions:docs-cleanup` 을, 같은 목록 중복만 있으면 "기존 문제도 정리해줘" 를 안내한다. 직전 보고와 같으면 보이지 않는다. 파일은 5개까지. 사본이 원본과 다르면 둘째 줄이 붙는다.
- `systemMessage` 를 쓰는 이유: 모델을 거치지 않아 비용이 없고 빠지지 않는다. Stop 의 `additionalContext` 나 `decision` 은 턴을 이어 가게 해 매번 모델 호출과 보고 재작성 비용이 든다.

## 파일 전체 검사, 기계적 고치기 (`scripts/conventions-scan.py`)
훅이 아니라 명령이다. 사용자 명령 `/qwreey-conventions:comments-cleanup`(`--kind comment`)과 `/qwreey-conventions:docs-cleanup`(`--kind doc`)이 이것을 부른다: 훅은 추가한 줄만 보고 남은 문제는 세기만 한다.
```bash
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py scan [경로...] [--json] [--category symbol ...] [--kind comment|doc] [--summary] [--top N] [--budget S] [--exit-zero]
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py fix [경로...] --dry-run   # unified diff 만, 쓰지 않는다
python3 -I plugins/qwreey-conventions/scripts/conventions-scan.py fix [경로...]
```
- 검사: `conventions-check.py` 의 함수를 불러 모든 줄에 돌린다. 확장자 표, 제외, 생성 파일 표시, `.claude/conventions.json` 이 훅과 같다. 경로를 안 주면 저장소 전체, git 이면 `git ls-files -co --exclude-standard` 라 무시 파일은 보지 않는다. 주석 언어 기준은 파일 전체 다수(없으면 `comment_language`, 형제 파일). `--kind comment` 는 코드 파일의 주석만, `--kind doc` 는 모델용 문서만 본다.
- 출력: `경로:줄: 범주: 내용`, 범주별, 파일별 수, `--fix` 로 고칠 수 있는 추정. `--json` 은 `findings`, `needs_judgment`, `diffs`, `summary`. 종료 코드 0 = 남은 문제 없음, 1 = 있음, 2 = 사용법 오류.
- `--budget S`: S 초가 지나면 파일 읽기를 멈추고 요약에 `partial:` 줄(멈춘 자리, 전체 파일 수, 전체 검사 명령)을 낸다. `--exit-zero`: 찾은 것이 있어도, 사용법 오류나 예외여도 0 으로 끝난다. 두 정리 명령의 `!` 미리 실행이 `--kind <종류> --summary --top 15 --budget 30 --exit-zero` 로 부른다: `!` 명령이 0 이 아니면 Claude Code 가 명령 전체를 멈추고, 2분 한도가 있기 때문이다(quad 전체 검사 56 s, 30초에서 6,194 중 3,575 번째 파일에서 멈춤, coderag 2.3 s). 요약이 `partial` 이면 모델이 그 줄의 명령을 Bash 로 다시 돌린다.
- 고치는 것: 코드 파일 주석 안의 non-keyboard symbol 과 invisible character, 모델용 문서 본문의 invisible character(훅이 문서의 기호는 보지 않으므로 고치지도 않는다). 주석 안의 인라인 코드와 URL, 따옴표로 감싼 한 글자, 지시자 줄, 문서의 frontmatter, 코드 펜스, 인라인 코드, URL, 경로 토큰은 그대로 둔다.
- 대체: 대시는 ` - `(숫자 사이 en dash, minus 는 `-`), 가운뎃점은 `, `(조각 맨 앞이면 `-`; `/` 는 곱을 나눗셈으로 바꿀 수 있어 쓰지 않는다), `…` 는 `...`, 화살표는 `->` `<-` `<->` `=>`, 곡선 따옴표는 곧은 따옴표, `§` 는 지운다, 동그라미 숫자는 `1)`, 전각은 ASCII, NBSP 는 공백, 그 밖의 보이지 않는 문자는 지운다(이모지 옆 ZWJ 와 파일 맨 앞 BOM 은 둔다). 규칙 전체는 스크립트 머리 주석.
- 사본(머리의 `@copy-of:` 로 다른 파일을 가리키는 파일, 정본이 아닌 `@start-replace` 영역)은 고치지 않고 `copies left unfixed` 로 알린다. 정본을 고치고 `tools/sync-copies.py --apply` 로 옮긴다. 사본을 따로 고치면 `--check` 가 깨진다.
- 판단이 필요한 것(이력, Ref 꼬리, 이스케이프, 언어, 이모지, 상자 그림, 표에 없는 기호, 코드 줄의 보이지 않는 문자)은 고치지 않고 "needs judgment" 로 남긴다.
- 토큰 가드: 고친 뒤 렉서로 다시 읽어 주석 밖 글자와 줄마다 주석 조각 수가 원본과 같아야 쓴다. 문서는 frontmatter, 펜스 줄, 보호 토큰이 같아야 한다. 다르면 쓰지 않고, 쓴 뒤 다시 읽어 어긋나면 원본 바이트로 되돌린다(`rejected`). 예: HTML 주석의 `-→` 를 `->` 로 바꾸면 `-->` 가 되어 주석이 일찍 닫히므로 거절된다.
- 렉서(`hooks/conv_lex.py`)는 주석 조각마다 열 위치(`s`)도 돌려준다. 고치기와 가드가 이것으로 주석 안만 바꾼다. `keep_code=True` 면 줄마다 주석을 지우고 문자열을 `""` 로 줄인 코드(`k`)와 여러 줄 주석·문자열 안에서 시작하는 줄 표시(`in`)도 준다(layout 지표용).
- `layout [경로...] [--json] [--summary]`: 함수마다 줄 수, 빈 줄, 문단, 최장 이어짐, 라벨, 끼운 여러 줄 주석, 한 줄 여러 선언(여러 반환 받기 `local ok, err = pcall(f)` 는 세지 않음), 한 글자 지역, 문서 주석 상태와 layout 알림 범주를 모든 함수에 대해 내고 요약(15줄 이상 함수 중 한 덩어리 수, 본문 100줄당 끼운 주석, 공개 함수 문서 범위)을 붙인다. 고치지 않는다. 키와 무관하게 돈다. 종료 코드 0 = 걸린 함수 없음, 1 = 있음.

## 사본 검사 (`reuse-check.py`)
- C1: `@copy-of: <경로>[#이름]` 사본이 원본과 같은가(파일은 바이트, 값은 문자열 묶음). 풀리지 않거나 다르면 알린다.
  - `<저장소>:<경로>`: 지금 저장소(worktree 면 본 저장소) 옆의 같은 이름 폴더, 없으면 `hooks/known_repos.py`(lib 정본의 사본)의 저장소 목록(세션 기록의 cwd, qwreey-workspace 옵션 `harness_workspace_extra`·`harness_workspace_exclude`)에서 폴더 이름이 같은 것. 프로젝트를 두는 곳이 사람과 OS 마다 달라 작업공간 폴더를 정하게 하지 않는다. 같은 이름이 여럿이면 그 경로가 있는 첫 후보(경로순)와 비교하고 알림 끝에 어느 것인지 적는다. 못 찾으면 비교하지 않고 그림자 기록(`sibling`)만 남긴다.
- C2: 원본을 고치면 그것을 가리키는 사본 목록을 알린다.
- M1: 추가한 줄의 표시(`@copy-of`, `@start-replace`, `@end-replace`, 주석 본문의 맨 앞에 온 것만; 설명 글 중간이나 문서 블록 안에 인용한 `// @copy-of` 예는 아니다)가 놓인 자리와 꼴. 줄마다 회차당 한 번, 고친 꼴을 함께 준다.
  - 문서 주석: Rust `///`·`/** */`·`/*! */`, JS·TS·Kotlin `/** */`, Luau `---`·`--[=[ ]=]`. 문서 도구가 표시를 싣거나 태그로 읽는다. `//!`, `////`, `/* */`, `--[[ ]]` 는 통과.
  - Astro 의 `<!-- -->` 안 `@copy-of`(빌드된 페이지에 남을 수 있다): 템플릿은 `{/* */}`, frontmatter 는 `//`.
  - 영역 표시가 `copy_regions.MARK` 꼴(혼자 있는 줄 주석)이 아님: 읽히지 않는다.
  - 파이썬 머리 10줄 밖 독스트링의 `@copy-of`: 읽히지 않는다.
  - 형제 저장소 꼴이 섞임: `@copy-of: ../repo:path`(→ `repo:path`), `@start-replace: repo:path` 나 `../repo:path`(→ `../repo/path`). 저장소를 찾았는지와 무관하게 알리고, 같은 줄의 "does not resolve" 알림은 내지 않는다.
  - `.json`, `.jsonc` 의 추가 줄에 경로 꼴 표시가 있음: JSON 은 표시를 둘 주석이 없고 아무도 읽지 않는다(파일당 한 번). Edit·Write 만 본다(Bash 경로는 코드 파일만 reuse-check 에 넘긴다).
  - 이 저장소와 coderag 의 추적 파일 전체를 한 줄씩 추가한 것으로 놓고 돌린 결과: 둘 다 0(검사 대상 코드 파일에서 표시 낱말이 든 줄 claude-doctor 114, coderag 4).
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
- 분리 계획기: hard 를 넘은 `.luau`/`.lua` 에는 luau-kb 팩의 `skills/luau-style/scripts/split-plan.py` 명령을 붙인다. 팩은 사용자 harness.env 의 `HARNESS_LUAU_KB`(팩 폴더, 저장소 층은 못 바꾼다), 없으면 설치된 luau-kb 플러그인(`hooks/conv_plugins.py`: `installed_plugins.json` 과 마켓 위치, `bash-bypass-reminder` 와 같은 찾기)에서 찾는다. 둘 다 없으면 그 줄만 조용히 뺀다.
- 끄기: `STRUCTURE_REMINDER=off`.

## 메모 배치 (`memory-placement.py`)
auto memory 디렉터리(`<config>/projects/*/memory/` 또는 `autoMemoryDirectory`)에 쓴 `MEMORY.md` 가 아닌 파일을 `memory_signals.py` 로 분류해, 경로·빌드 명령·규약·함정 같은 저장소 지식으로 보이면 저장소로 옮기라고 알린다(level=warn). `type: user` 는 알리지 않는다. 같은 파일은 (세션, 호출자, compact 회차)당 한 번. 끄기: `MEMORY_PLACEMENT=off`.

## 저장소 설정
`<프로젝트>/.claude/conventions.json`(없으면 예전 이름 `.claude/comments.json`): `comment_language`, `allow_chars`, `public_ids`, `exclude`, `patterns`, `allow_ref_tail`, `min_reason_words`, `label_language`, `layout`(형식은 [comments.md](comments.md)), `reuse`(`mode`, `allow`, `vocab_ok`, `min_shared`, 형식은 [code-reuse.md](code-reuse.md)), `rules_exclude`. 파일 길이는 `.claude/structure.json`. 사용자 설정 위치는 `$CLAUDE_CONFIG_DIR`(기본 `~/.claude`).

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
python3 -I plugins/qwreey-conventions/tests/test-bash-bypass-reminder.py
python3 -I plugins/qwreey-conventions/tests/test-bash-writes.py
```
모델을 부르지 않는다.
