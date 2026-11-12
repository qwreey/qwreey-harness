# 48. code-reuse 문구 토론 1회차, 입장 Q: 툴킷마다 실제로 먹히는가

> Snapshot 2026-11-12. 초안 `archive/research/drafts/code-quality-conventions/`(rule·스킬·hook-design·fp-strategy)를 table-sim d39499c, devplorer a0b9da9, quad 0c2eef35, coderag 0df9bc7, claude-doctor c89cddc, nekolog ba2e05c, stl-luau e77fc03 의 실제 코드에 대 보았다. 읽기 전용, 줄 번호는 이 커밋 기준. 이미 정한 결정(이름, 사본 줄 이동, N2 문구, 어긋날 때만, 80% 관문, `@copy-of: <path>[#NAME]` 하나로 통합)은 다시 열지 않는다.

## 결론
- 초안은 coderag(Rust)와 claude-doctor(Python)에서 뽑은 문장이라 거기서는 맞는 조언을 한다. **Luau 게임 저장소에서 가장 흔한 중복은 규칙에 없다**: 클라이언트와 서버가 같은 값을 따로 적고 주석에 "서버의 X 와 같게" 라고 쓴 것(아래 1·2·3). 문자열 묶음이 아니라 H1 도 못 본다. 규칙 한 줄이 필요하다.
- 사본 bullet 은 vendor 트리(잠금 파일로 관리)에 그대로 적용하면 틀린 조언이 된다. 표시 문법은 Python docstring, Rust `///`, Luau moonwave 블록, Astro 템플릿에서 자리 규정이 필요하다.
- 훅 설계에는 실측으로 확인한 범위 결함이 둘 있다: `.claude/` 아래 코드(quad 83%, stl-luau 96%)를 훑는다, 언어가 다른 짝에 "import 하라" 는 N1 을 쓴다.
- 턴 끝 보고 줄은 비프로그래머가 "무엇을 해야 하나" 를 알 수 없다. 문구를 바꾼다.

## 1. 저장소 사례 (규칙이 맞게 / 틀리게 / 못 잡는 것)

| # | 위치 | 무엇 | 초안의 조언 | 판정 |
|---|---|---|---|---|
| [비공개 프로젝트 세부 생략]
| 2 | devplorer `src/Client/App/Explorer/TreeOps.luau:155-157` `codeClasses` 표, `src/Server/Policy/Edit.luau:27-34` `codeLike` 의 `IsA(...) or IsA(...)` 사슬 | Execute 권한이 필요한 클래스 목록(보안). 클라이언트 주석 "서버 codeLike와 같은 목록". 서버는 이미 `../../Client/Shared/Limits` 를 require 한다(`Handlers/Edit.luau:11`) | 없음(서버 쪽이 묶음이 아님) | **못 잡음**. 단순화 bullet 도 `or` 사슬을 모름 |
| 3 | devplorer `Client/App/Inspect/Remotes.luau:65` `{ Visits = 400, Chars = 2000 }`, `Server/Handlers/Remotes.luau:140` 같은 값 인라인 | 보기 예산, 주석 "서버 보기와 같다" | 없음 | **못 잡음** |
| 4 | devplorer `trim` 네 벌: `Client/App/Palette/init.luau:107`, `Shared/Actions/ActionForm.luau:92`, `Shared/Explorer/Bookmarks.luau:228`(셋 다 local), `Shared/Properties/ValueText.luau:15`(내보냄). 구현이 gsub 두 번 / match 두 갈래 | Luau 에 표준 trim 이 없어 파일마다 씀 | "walker, frontmatter or TOML reader, hash, glob, ..." 목록에 문자열 도우미가 없어 모델이 해당한다고 보지 않을 수 있다 | 원칙은 맞음, **목록이 coderag 편향** |
| 5 | devplorer `Shared/Access/Capabilities.luau:7,13` 타입 `Capability` 와 `All`, `Server/Handlers/Edit.luau:227` `Needs = { "Server", "ServerValues", "Edit" }`(타입 `{ Capability }` 로 검사됨) | 어휘를 정의 한 곳에서 타입으로 참조 | "defined once and referenced everywhere" 를 문자 그대로 읽으면 `Needs` 를 상수 참조로 바꾸라는 뜻이 됨. H1 도 3개 공유로 걸 수 있음 | **틀린 조언 위험**. 타입 검사된 리터럴은 참조로 쳐야 함 |
| 6 | table-sim `<비공개>` `form: ("coin" \| "stick" \| "back")?`, `<비공개>` `type Form` + `FORMS :: { Form }` | 같은 합집합을 두 모듈에 다시 적음. Dice 는 Types 를 require 하지 않아 Types 가 `Dice.Form` 을 가져올 수 있음 | "defined once" 맞음. 훅은 타입끼리 원소 같음으로 알림 | **맞음**. Dice 의 `:: { Form }` 캐스트는 Luau 에서 쓸 수 있는 최선이라 규칙에 적을 만함 |
| 7 | quad `scripts/doc-coverage.py:32` `INJECTED`, `quad-base/src/LifetimeHandle.luau:263` 의 `native*` 목록 | Python 스크립트가 Luau 코드를 따라감(fp-strategy 의 TP) | 루트 `default.project.json` 하나라 같은 패키지로 판정 → N1 "reference that definition" | **틀린 조언**. 언어가 다르면 import 불가. 사본 표시 + 대조, 또는 Luau 소스에서 읽기 |
| 8 | coderag `crates/coderag-core/src/rules/mod.rs:20-23` `/// Copy of SKIP_DIRS in claude-doctor plugins/qwreey-conventions/hooks/rules_inject.py` | 다른 저장소, 다른 언어의 사본, 산문 표시 | `@copy-of: claude-doctor:plugins/.../rules_inject.py#SKIP_DIRS` | **맞음**. 단 표시가 `///` 안에 있으므로 훅이 doc 주석의 표시를 읽어야 함(§3 은 doc 주석 안을 묶음에서 뺀다고만 함) |
| 9 | claude-doctor `plugins/q/scripts/compact_epoch.py:2` `정본: ...`, `qwreey-conventions/hooks/memory_signals.py:3` `Canonical copy: ...`(docstring) | 바이트가 같은 파일 사본. 정본 파일 자신도 같은 머리를 가짐 | 통합 표시로 바꾸면 정본 파일에 `@copy-of: <자기 경로>` 가 생김. hook-design §7 은 `Canonical copy:` 만 읽어 `정본:` 사본을 H1 대상으로 둠 | **규정 필요**: 자기 파일을 가리키는 표시는 정본 표시, 파일 표시는 머리 바이트에서 찾음(docstring 포함) |
| 10 | claude-doctor q 플러그인 frontmatter 읽기 세 벌: `skills/doctor/scripts/scan.py:208`, `scripts/records_check.py:43`, `scripts/sllib/records_home.py:86`(`_fm` 은 `re.M` 으로 본문의 `status:` 줄도 잡음) | 같은 플러그인 안, 동작이 이미 다름 | 목록의 "frontmatter reader" 그대로. 라이브러리 bullet 은 YAML 라이브러리를 권하지만 훅은 표준 라이브러리만 | 중복 쪽 **맞음**. 라이브러리 쪽은 "설치할 수 없다" 가 이유 목록에 없어 모델이 크기·기동을 재려 듦 |
| 11 | nekolog `frontend/lingui.config.ts:7` `locales: ["en", "ko"]`, `frontend/src/middleware.ts:7` `supportedLocales = ["ko", "en"]` | 지원 언어 두 벌 | N1 + 스킬 1단계 "neither place is the right home → one module both import" | **맞음**(설정 파일을 미들웨어가 import 하면 빌드 도구가 딸려 오므로 작은 모듈로) |
| 12 | table-sim·devplorer `vendor/`(gitignore, `vendor.lock.json` 의 rev 로 다시 만듦, `scripts/vendor.sh --check`) | 통째로 받은 quad·ProfileStore | 사본 bullet 을 읽으면 파일마다 `@copy-of` + 대조 시험. 고치고 싶을 때 vendor 를 직접 고칠 위험은 어디에도 없음 | **틀린 조언**. 트리 잠금이 기록이고, 고칠 곳은 원본 저장소 |

## 2. bullet 별 툴킷 적용

| bullet | Luau/Roblox | Rust | Python 훅(독립 설치) | TS/Astro |
|---|---|---|---|---|
| 정책 판별·`DEFAULT_` | 맞음(라이브러리는 "두 소비 게임" 으로 읽힘). 게임 하나 안의 조정값은 이 시험에 안 걸리는데, 그것이 맞다 | 맞음(근거가 여기서 나옴) | 맞음 | 맞음 |
| 도우미 검색 | 목록에 Luau 흔한 것(trim·split·deep copy·Signal·cleanup) 없음(사례 4) | 맞음 | 맞음(사례 10) | 맞음 |
| 어휘 한 곳 | 타입 검사 리터럴 예외 필요(5), 엔진 클래스 이름은 바깥 어휘(devplorer `TreeOps:157` vs `Remotes:67`, probe 에서 걸림) | 맞음 | 도구 이름은 바깥 어휘 | 맞음 |
| 클라·서버 공유 | **없음**(1·2·3). Rojo 에서 import 가능 여부는 패키지가 아니라 트리 위치(ReplicatedStorage)가 정함 | 해당 없음 | 해당 없음 | 프런트·백엔드 사이(nekolog Go↔TS)는 언어가 달라 7 과 같음 |
| 사본 표시 | vendor 트리(12), moonwave 블록 | `///` 안 표시(8) | docstring 머리(9), 정본 자기 표시 | JSDoc `/** */` 안이면 알 수 없는 태그 |
| 타입 ↔ 목록 | "keep them next to each other" 는 Dice 가 이미 함. 남는 위험은 다른 모듈이 다시 적는 것(6) | 해당 적음 | 해당 없음 | `typeof LIST[number]` 맞음 |
| 라이브러리 | 엔진 서비스가 곧 라이브러리(HttpService JSON, TweenService)라는 말이 없음 | 맞음(측정 절차의 근원) | "설치 불가" 이유 없음(10) | 맞음 |
| 단순화 | `IsA` `or` 사슬(2) | 항등 match 맞음 | 맞음 | 맞음 |

## 3. 표시 문법, 주석 문법마다

| 언어 | 값 사본 | 파일 사본 | 주의 |
|---|---|---|---|
| Luau | `-- @copy-of: src/core/Shapes.luau#KINDS` | 머리 `--` 줄 | `--[=[ ]=]` moonwave 블록 안에 두면 `@` 로 시작해 문서 태그로 읽힐 수 있다. 줄 주석으로 |
| Python | `# @copy-of: ...` | 모듈 docstring 머리(지금 관행) | 렉서는 docstring 을 문자열로 보므로 파일 표시는 머리 바이트로 찾아야 한다 |
| Rust | `// @copy-of: ...` | 머리 `//!` 또는 `//` | `///` 는 rustdoc 에 실린다. 허용하되 `//` 권장 |
| TS/JS | `// @copy-of: ...` | 머리 `//` | `/** */` 안이면 tsdoc lint 가 모르는 태그로 경고할 수 있다 |
| Astro | frontmatter 안 `//` | - | 템플릿의 `<!-- -->` 는 HTML 로 나갈 수 있어 `{/* */}` 로. 알림의 `{c}` 는 위치를 보고 골라야 한다 |
| sh·TOML | `#` | `#` | rule `paths` 에 없음(훅 범위 밖, 문제 아님) |
| JSON | 불가 | 불가 | 읽는 코드 쪽이나 대조 시험에 출처를 적는다 |

`#NAME` 은 정의에 적힌 이름 그대로(Luau 반환 표의 키 `SURFACE_COLORS`, 모듈 필드 `FORMS`). 스킬 표에 "line comment, not inside a doc block" 과 "a mark naming its own file marks the source" 두 마디를 넣는다.

## 4. 훅 설계, 첫 네 언어 밖과 범위

- **`.claude/` 제외 필요.** 추적 중인 코드 파일 가운데 `.claude/` 아래가 quad 2,605/3,155, stl-luau 1,491/1,551, claude-doctor 70/342, table-sim 12/141. 감사 probe·옛 사본이라 H1 짝의 상대가 되고 5,000 파일 상한과 300 ms 예산을 먹는다. 기록 규약상 스냅샷은 고치지 않으므로 알릴 이유도 없다. `SKIP_PARTS` 에 더하거나 훅 제외 경로에 `.claude/`.
- `*-ignoreme*`(stl-luau `bench-ignoreme/old-*` 가 probe 에서 8묶음 전부)는 gitignore 라 `git ls-files` 면 빠지지만, 걷기 대체 경로에서는 들어온다. 걷기에도 gitignore 의 단순 글롭을 적용하거나 이 접미를 뺀다.
- **언어가 다른 짝은 import 불가로.** §5 조건 7 의 패키지 판정에 "확장자 계열이 다르면 다른 패키지" 를 더해 N2 를 쓴다(사례 7, nekolog Go↔TS). N2 끝에 "or generate one from the other" 를 붙이면 Python↔Luau 에 맞는다.
- pesde·wally 의존 선언도 Cargo path 처럼 import 가능으로(quad-roblox → quad-base).
- Go·Kotlin 은 rule `paths` 에 있고 훅에는 없다. 규칙만 걸리는 것은 문제 없다. `.lua` 는 Luau 렉서로 충분.
- GEN_MARK 는 `생성:`(devplorer `ClassIcons.luau:4`)을 못 잡는다. 그 파일은 키 표라 H1 과 무관하지만 패턴에 `생성:` 을 더할 만하다.
- 그림자 후보 하나(켜기 약속 아님): 정의 옆 주석의 "same as X" / "와 같게" / "같은 목록" + 다른 파일 경로. 사례 1·2·3 이 모두 이 꼴이고 H1 이 못 보는 클라·서버 사본을 잡는다. 정밀도는 재지 않았다.

## 5. 턴 끝 보고 줄, 비프로그래머가 읽을 때

초안: `손댄 파일에 기존 문제가 남아 있음: a.luau(이력 3, 기호 12), b.rs(중복 2). 정리는 요청하실 때만.`

- "중복 2" 는 무엇이 겹치는지 모른다(파일? 코드?). "정리는 요청하실 때만" 은 거절처럼 읽히고, 무엇이라 말하면 되는지, 지금 위험한지가 없다.
- `@copy-of` 사본이 정본과 어긋난 것(C1)은 버그 후보라 "정리" 와 같은 줄에 묻으면 안 된다.

제안: `손댄 파일에 전부터 있던 문제: a.luau(주석 15), b.rs(같은 목록이 두 곳 2). 고치려면 "기존 문제도 정리해줘" 라고 하시면 됩니다.` 어긋난 사본이 있으면 앞에 따로 `사본이 원본과 다름: c.py 1. 동작이 달라질 수 있습니다.`

## 6. 제안하는 전체 rule 문구

바꾼 곳: 도우미 목록, 클라·서버 공유 bullet(새), 어휘 bullet 두 마디, 사본 bullet(언어, 자리, vendor), 타입 bullet(Luau), 라이브러리 두 마디, 단순화 `or` 사슬. 나머지는 초안 그대로. 34줄 → 35줄.

```markdown
---
description: Code reuse conventions, all toolkits. Policy values vs invariants, one implementation per job, marked copies, library vs hand-written. Details in the qwreey-conventions:code-reuse skill
paths: ["**/*.{luau,lua,ts,tsx,js,jsx,mjs,astro,rs,py,go,kt}"]
---
# Code reuse: values, duplicates, libraries

> A repo's own rules win. Pairs with the PostToolUse hook `reuse-check`, which only informs.

## Policy values
- Test: could two projects reasonably want a different value, and is it a judgment about the target repo rather than about the program's correctness? Then it is policy.
- Policy (folder and extension lists, size limits, stage ladders, tool names) lives in config, a data table or a pack; code keeps only a `DEFAULT_*` fallback that config overrides.
- Values fixed by a format, a spec, an outside tool or correctness (schema versions, grammar tables, security allowlists) stay `const`.
- A list that names one ecosystem (Roblox, Wally, pesde) belongs to that ecosystem's pack, not to the core.
- Use the `DEFAULT_` prefix only when an override exists; readers take the prefix as that promise.

## One implementation
- Before writing a helper (trim or split, deep copy, walker, frontmatter or TOML reader, hash, glob, date), search the repo by name and by job and extend what you find. Copies drift apart silently, and the disagreement surfaces as a bug far from both.
- A value two sides must agree on (client and server limits, permission lists, remote names) lives in one module both require; in a Roblox place, a module under ReplicatedStorage. A comment "same as X in Y" is a copy without a check.
- A vocabulary (status names, folder kinds, level names) is defined once and referenced everywhere; a literal type-checked against its union counts as a reference. Names fixed by an outside API (Roblox classes, Claude Code tools) are not your vocabulary.
- When a copy is unavoidable (separately installed plugins, another repo, another language), mark it `@copy-of: <path>[#NAME]` in a line comment above the value, or in the file header for a whole file, and keep a test that compares them. A vendored tree pinned by a lock file is not marked or edited: change the source and re-vendor.
- A runtime list that mirrors a type union: derive one from the other where the language can (TS `typeof LIST[number]`). In Luau, define both in one module, cast the list to the union (`{ ... } :: { Form }`), and import the type elsewhere instead of retyping it.

## Libraries and hand-written code
- Prefer the library when the format is correctness-critical and the library is the reference parser (CommonMark, YAML, full_moon for Luau), or when your version would need its own test suite to be trusted. In Roblox, an engine service (HttpService JSON, TweenService) is the library.
- Hand-written is right when the runtime cannot install the library (stdlib-only hooks), when a measured size or startup budget rules it out, when behavior must match a reference implementation exactly, or when you need tolerant parsing the library rejects.
- Either way, put one line at the top of the hand-written module: `why not <library>: <reason>`. No reason, use the library.
- Claims about cost are measured: binary size delta, cold build time, dependency count.

## Simplification
- String branches on one variable: see code-structure (Data).
- A long function that chains independent steps becomes step functions run from a table. A lexer, state machine or AST visitor may stay long; its length is the shape of the work.
- An arm that maps each value to itself, or an `or` chain over fixed names (`IsA("A") or IsA("B")`), is a membership test; replace it with a set lookup over one list.

## Notices
- Marker syntax, repo settings and what to do with a hook notice: load the `qwreey-conventions:code-reuse` skill. Fix only what you added; old duplicates in edited files are reported to the user at turn end, not cleaned up unprompted.
```

P 가 줄이자고 하면 내줄 수 있는 순서: 라이브러리의 Roblox 마디 > 단순화 `or` 사슬 > 어휘의 바깥 API 마디(스킬 4단계가 덮음). 클라·서버 bullet, 사본 bullet 의 vendor·언어 마디, 타입 검사 리터럴 마디는 사례 1·2·3·5·7·12 의 틀린 행동을 막으므로 남겨야 한다.
