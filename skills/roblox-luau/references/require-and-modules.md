# require-and-modules — require-by-string 규칙(CLI·Studio), 정적 검사가 잡는 조건, 모듈 캐시와 사본

## 이 파일이 답하는 질문
- Q1 `init.luau` 안의 `./X` 와 `@self/X` 는 각각 어디를 가리키나?
- Q2 "could not resolve child component … (ambiguous)", "could not reset to requiring context (ambiguous)" 는 왜 나나?
- Q3 `.luaurc` 의 alias 는 런타임 require 에서 동작하나?
- Q4 심볼릭 링크로 연결한 패키지를 require 할 수 있나?
- Q5 require 경로가 틀렸는데 `luau-analyze` 가 0건이다. 정적 검사는 무엇을 잡고 무엇을 못 잡나?
- Q6 Studio 의 문자열 require 는 CLI 와 무엇이 다른가? 대상이 아직 없으면 기다리나?
- Q7 Rojo 로 고친 모듈이 Studio 에서 옛 본문을 돌려준다. 왜?
- Q8 같은 패키지 사본이 둘이면? 타입만 쓰려는 require 는 안전한가?
- Q9 require 경로 표기 규칙(D-12)은 정해졌나?

## 목차
- §1 luau CLI 의 경로 규칙
- §2 모호성(ambiguous) 에러 두 가지
- §3 `.luaurc` alias
- §4 심볼릭 링크
- §5 정적 검사가 잡는 것과 못 잡는 것
- §6 Studio 의 문자열 require
- §7 require 캐시, VM 경계, 사본
- §8 모듈 설계 함정
- §9 D-12 (require 경로 표기) 상태
- 모순 판정 · 정정 · 미판정

---

## §1 luau CLI 의 경로 규칙
status: verified · last-confirmed: luau 0.734, 0.742 · 근거: `snippets/rbx-require-cli.sh` Q1·Q2·Q3·Q5 (rc=0); RFC `abstract-module-paths-and-init-dot-luau`; stl-luau-doctor `.claude/base/architecture.md:37-57,312-335`; quad `.claude/base/project-setup-plan.md:144-167`; tbox `CLAUDE.md:95-117`; mrow `review/REVIEW.md:1159-1187` · 후보: Q-101, S-123, X-02, X-04, D-C01

| 어디서 | 폴더 **안** 파일 | 폴더 **밖** 형제 |
|---|---|---|
| `Foo/init.luau` | **`@self/Bar`** | **`./Types`** |
| `Foo/Bar.luau` | `./Baz` | `../Types` |

- **`init.luau` 는 자기가 든 폴더 자신이다.** 그래서 그 안의 `./` 는 폴더의 형제를 가리킨다. 같은 폴더 안 파일은 `@self/` 로 부른다. `@self` 는 `.luaurc` 없이 동작하는 예약 alias 다.
- 일반 파일의 `@self/x` 는 항상 실패한다(일반 파일에는 자식이 없다).
- `require("./Foo")` 는 `Foo/init.luau` 를 싣는다. 그래서 `X.luau` 를 `X/init.luau` 로 바꿔도 바깥의 기존 경로는 그대로 유효하다. 새 형제 파일만 `@self/` 로 부르면 된다.
- **테스트 엔트리를 `tests/init.luau` 로 지으면** 그 파일의 `./` 가 저장소 루트가 된다(`./src` 는 되고 `../src` 는 실패). 다른 파일과 규칙이 달라 헷갈리므로 엔트리는 `tests/run.luau` 로 짓는다.
- 패키지 이름이 바뀌는 배포에서 깨지는 꼴: `src/init.luau` 안의 `require("./src/x")` 는 폴더 이름이 우연히 `src` 일 때만 동작한다. pesde·Wally 가 폴더 이름을 바꾸면 깨진다. `@self/x` 로 쓴다.
- 위치가 바뀌는 코드(클라이언트 번들이 PlayerGui 로 복제되는 경우 등)는 `@game/...` 절대 경로 대신 상대 경로와 `@self` 를 쓴다(devplorer, luau-lsp 실측 2026-10-19).
- lune 0.8.9 는 이 규칙과 반대로 동작했다는 기록이 있다(luau-verify `tooling.md`). 기본 러너는 `luau` 다(D-03).

mock 흉내: 해당 없음(CLI 가 실물이다). Studio 는 §6.

## §2 모호성(ambiguous) 에러 두 가지
status: verified · last-confirmed: luau 0.734, 0.742 · 근거: `snippets/rbx-require-cli.sh` Q4; mrow `review/REVIEW.md:1183-1187`; tbox `CLAUDE.md:141-145` · 후보: X-04

| 조건 | 에러 |
|---|---|
| **대상**에 `X.luau` 와 `X/` 가 같이 있다 | `could not resolve child component "X" (ambiguous)` |
| **요구하는 파일의 폴더**에 같은 이름의 형제 파일이 있다(`tests/` 옆에 `tests.luau`) | 그 폴더 안의 **모든** require 가 `could not reset to requiring context (ambiguous)` |
| `src/init.luau` 와 `tests/init.luau` 가 둘 다 있다 | **모호하지 않다**(에러 없음) |

- 처방: 같은 이름의 파일과 폴더를 형제로 두지 않는다.
- 관련 에러: require 된 파일이 값을 돌려주지 않으면 `module must return a single value`(Q10). 테스트 엔트리처럼 실행만 하는 파일을 require 하지 않는다.

## §3 `.luaurc` alias
status: verified (CLI) / described (Studio) · last-confirmed: luau 0.734, 0.742 (CLI), Studio 0.738·0.742 (원천) · 근거: `snippets/rbx-require-cli.sh` Q6·Q11, `snippets/verify-require.sh` R4; rbvm `.claude/design/engine-behavior.md:68-83`; quad `.claude/audit/studio-docs-2026-09-10.md:227-290`, `.claude/base/project-setup-plan.md:112-142,339-348` · 후보: Q-104, S-125, R-40, M-09

- **luau CLI 런타임에서 `.luaurc` 의 일반 alias 는 값이 `./` 로 시작하면(또는 절대 경로면) 동작한다.** `{"aliases": {"lib": "./lib"}}` 뒤 `require("@lib/x")` 가 0.734·0.742 모두 성공했고, `luau-analyze` 도 같은 alias 로 타입을 푼다.
- **값에 `./` 가 없으면**(`"lib": "lib"`, `"quad-base": "quad-base/src"` 꼴) luau 런타임은 `could not jump to alias "lib"`, `luau-analyze` 는 `Unknown require` 로 실패하고 **luau-lsp 만 푼다.** 그래서 "alias 는 편집기 전용이라 런타임에서 실패한다"로 보였다. 원천 기록(2026-08)의 관측은 이 조건에서 맞다(정정 표는 조건을 붙인다).
- Studio(원천 실측): 모르는 alias 는 `@foo is not a valid alias`, alias 는 대소문자를 가리지 않는다(`@Self/Child` 성공). `@game/...` 은 절대 경로다.
- darklua 0.19.0 `convert_require` 는 `@self`/`@game` 은 건드리지 않고 커스텀 alias 만 Rojo sourcemap 기준으로 바꾼다(quad, described).

mock 흉내: rbvm 은 미지원 alias 에서 무한 대기한다(엔진은 즉시 에러, rbvm S6).

## §4 심볼릭 링크
status: verified (CLI 런타임·analyze·luau-lsp) / described (Rojo) · last-confirmed: luau 0.734, 0.742, luau-lsp 1.70.1 · 근거: `snippets/rbx-require-cli.sh` Q7·Q8·Q11, `snippets/verify-require.sh` R3; quad `scripts/relink.sh:4-18`, `.claude/base/project-setup-plan.md:184-246`; moonwave-luau `.claude/conventions.md:72` · 후보: Q-103

- luau CLI 의 require 는 **디렉터리·파일 심볼릭 링크를 따라가지 않는다**(`could not resolve child component "linked"`). 의도된 설계로 기록돼 있다. `luau-analyze`(strict)는 `Unknown require` 를 낸다.
- **luau-lsp 는 symlink 를 따라가 모듈을 푼다.** 에디터는 깨끗한데 `luau` 실행은 실패하는 상황이 여기서 생긴다.
- pesde 워크스페이스 링크는 전부 디렉터리 링크다. CLI 테스트 전에 실제 복사로 바꾼다. 이때 `cp -r` 는 링크를 링크 그대로 복사하므로 **`cp -rL`** 을 쓴다. pesde 레지스트리 설치(소비자 쪽)는 하드 링크 일반 파일이라 링크가 없다(quad 2026-09-21).
- `rojo sourcemap`/`rojo build` 는 링크를 투명하게 통과한다(quad, Rojo 7.7.0, described).

## §5 정적 검사가 잡는 것과 못 잡는 것
status: verified · last-confirmed: luau 0.734, 0.742, luau-lsp 1.70.1 · 근거: `snippets/rbx-require-cli.sh` Q8·Q9 · 후보: Q-102, S-124, X-02

판정표(런타임 × `luau-analyze` × `luau-lsp`)의 정본은 luau-verify 스킬 `references/checkers.md` §7 이다. 요지:
- strict 에서는 풀리지 않는 경로(없는 파일, `init.luau` 의 `./` 오용, symlink, `./` 없는 alias 값)를 `luau-analyze` 가 `Unknown require: unsupported path`(rc=1)로 잡는다. nonstrict 는 0건이다.
- **있는 다른 모듈로 풀리는 오타**는 모드와 무관하게 못 잡는다. luau-lsp 는 symlink 와 `./` 없는 alias 를 풀어 버려 에디터만 보면 놓친다. Roblox 인스턴스 경로(`script.Parent.X`)는 sourcemap 이 있어야 푼다(`typedefs.md` §4).
- 그래서 "정적 검사가 require 오류를 **절대** 못 잡는다"는 strict 에서 틀렸고, 처방은 (1) 모든 파일 strict, (2) require 를 고친 변경은 실제로 require 하는 런타임 게이트다.
- Studio 에서도 같은 꼴이 있다: 이름이 바뀐 패키지의 `require("./src/...")` 가 옆의 다른 `src` 모듈을 **에러 없이** 싣는다(mrow, Studio 0.740).

mock 흉내: 해당 없음.

## §6 Studio 의 문자열 require
status: described (Studio 열) / verified (CLI 열) · last-confirmed: Studio 0.742.0.7421053(rbvm, 2026-10-13, Edit, `rbvm-test`), Studio 0.738(quad, 2026-09-10), luau 0.734·0.742(CLI 열, `rbx-require-cli.sh` Q10) · 근거: rbvm `.claude/design/engine-behavior.md:68-83`; quad `.claude/audit/studio-docs-2026-09-10.md:227-290`, `.claude/archive/question-resolved.md:1649` · 후보: R-39, R-40, Q-105

| 경로(ModuleScript `Caller` 안, 형제 `Sibling`, 자식 `Child`) | Studio | luau CLI 대응 |
|---|---|---|
| `"./Sibling"`, `"../X/Sibling"`, `"@self/Child"`, `"@game/ReplicatedStorage/…"` | 성공 | `./`·`../`·`@self` 같음. `@game` 은 CLI 에 없음 |
| `"Sibling"`(접두 없음), `""` | `require path must start with a valid prefix: ./, ../, or @` | 같은 규칙 |
| `"./Missing"` | **즉시** `could not resolve child component "Missing"` (0.00초, 기다리지 않음) | 같음 |
| `"./"` | `Unable to require module from given path './'` | 실패(`no module present at resolved path`) |
| `"./Sibling/"`(끝 슬래시), `".//Sibling"`(빈 세그먼트) | **성공** | 성공(0.734·0.742) |
| `"@foo/X"` / `"@Self/Child"` | `@foo is not a valid alias` / 성공(대소문자 무시) | `@Self`·`@SELF` 성공(대소문자 무시) |

- **문자열 require 는 대상이 생길 때까지 기다리지 않는다.** 그래서 클라이언트 진입점은 require 전에 `if not game:IsLoaded() then game.Loaded:Wait() end` 를 둔다. Play Solo 에서는 첫 줄에 이미 `IsLoaded() == true` 였다. 실서버 접속 순서는 재지 않았다.
- 위치가 바뀌는 트리(복제되는 번들)는 `@game` 대신 상대 경로를 쓴다(§1).

mock 흉내: rbvm 은 **아니오**. 없는 모듈·빈 세그먼트·미지원 alias 에서 무한 대기하고 접두 없는 이름을 받아 준다(rbvm S6, D7).

## §7 require 캐시, VM 경계, 사본
status: described · last-confirmed: quad 2026-09-02·09-08·09-10 Studio, table-sim·devplorer 관용구 · 근거: quad `.claude/audit/sugar-studio-2026-09-08.md:8-10`, `.claude/audit/m5-unit5-first-render-2026-09-02.md:26-30`, `.claude/research/debug-tooling-plan.md:66-71`; table-sim `.claude/conventions.md:139`; devplorer `.claude/conventions.md:93`; rbvm `.claude/review/2026-10-05-sibling-repos.md:135-136` · 후보: Q-106, T-55, Q-057

- **이미 require 된 ModuleScript 는 캐시된다.** Rojo 가 `Source` 를 바꿔도 같은 세션의 `require` 는 옛 본문을 돌려준다. 처방: Play 를 다시 시작하거나, 단일 모듈은 `require(ms:Clone())`, 상대 require 가 있는 패키지는 폴더째 `:Clone()` 해 임시 폴더에 두고 사본을 require 한다. 복제 전에 자식 수가 디스크와 같은지 확인한다(스트리밍 중 부분 트리).
- 콘솔·`execute_luau` 에서 require 한 모듈은 게임 스크립트의 모듈과 **상태를 공유하지 않는다.**
- 플러그인과 Play 중 게임은 별도 VM 이라 `_G`, `shared`, require 캐시가 공유되지 않는다. 같은 DataModel 의 `BindableEvent`/`BindableFunction` 은 그 경계를 넘는다(quad 2026-08-06, 원시값만 확인).
- Actor 마다 VM 이 따로라 모듈 수준 상태도 Actor 별로 갈라진다(`parallel-luau.md` §7).

mock 흉내: 해당 없음(Studio 세션 동작).

## §8 모듈 설계 함정
status: described · 근거: quad `scripts/relink.sh:97-103`, `.claude/base/module-lifecycle-plan.md:164-172`, `.claude/base/quad-types-plan.md:22-37`; rbvm `.claude/review/2026-10-05-sibling-repos.md:224-227`; devplorer `.claude/research/feature-proposals-2.md:77,265-266`; tbox `CLAUDE.md:11-13,34-37` · 후보: Q-107, R-45, Q-108, D-F27, X-07, Q-109

- **같은 패키지 사본이 둘이면 모듈 수준 상태가 둘로 갈린다**(캐시, 함수 신원 가드, weak-key 레지스트리). luau-lsp 도 두 사본을 다른 모듈로 봐 같은 이름의 타입이 서로 맞지 않는다. 라이브러리는 코어를 직접 require 하지 말고 게임이 넘긴 인스턴스를 팩토리 인자로 받는다.
- **require 는 모듈 코드를 실행한다.** 타입만 쓰려는 require 도 실행된다. 게시 패키지의 dev-dependency 는 소비자에게 전파되지 않으므로, 타입 전용 require 가 소비자 환경에서 크래시한다. 가벼운 types 패키지를 일반 의존성으로 둔다. 도구가 임의 모듈을 require 하는 것은 사실상 코드 실행이다.
- pesde 로 설치한 패키지 폴더 이름은 소문자라, 이름으로 루트를 찾지 말고 `script.Parent` 를 보관해 쓴다.
- require 할 때 Instance 를 만들어 모듈 변수에 쥐지 않는다(`instance-lifecycle.md` §7).
- 순환 require 가 "미완성 exports 를 돌려준다"는 quad 서술은 근거가 의심스러워 옮기지 않았다(audit/08 보류).

mock 흉내: 해당 없음(설계 지침). rbvm 의 require 대체는 §6 표 참고.

## §9 D-12 (require 경로 표기) 상태
status: described · 근거: claude-doctor `decisions/D-12-require-paths.md`, `decisions/README.md` "사용자 결정 현황"(2026-11-10)

> 정책: 미정. D-12 는 **제안** 상태다(사용자 미확인). 한쪽을 강제하지 말고 양쪽을 전한다.

- 제안(안 A): 공통 규칙 다섯 — `init.luau` 안 자기 폴더는 `@self/`, require 대상은 문자열 리터럴, 테스트 엔트리를 `init.luau` 로 짓지 않음, 새 모듈은 실제로 require 하는 테스트, symlink 를 따르지 않으므로 스테이징은 복사. 조건부 — 위치가 바뀌는 번들에서만 `@game/` 금지.
- 저장소 실태: devplorer 는 `@game` 0곳(금지), table-sim 은 `@game/ReplicatedStorage/…` 72곳(고정 위치라 문제없음).
- 이 파일의 재현이 제안에 보탤 것: 규칙 4 의 근거("정적 검사가 못 잡는다")는 **nonstrict 와 다른 모듈로 풀리는 오타에 한정**된다(§5). 규칙 자체(런타임 require 테스트)는 Q9 꼴 때문에 여전히 필요하다.

---

## 모순 판정

| # | 내용 | 판정 |
|---|---|---|
| audit/09 §6 #6 | 테스트 엔트리 `init.luau` 의 "ambiguous" 원인: tbox "src/init.luau 와 이름 겹침" 대 mrow "`X.luau`·`X/` 형제일 때만, 진짜 함정은 `./` 가 루트" | **판정(재현)**: mrow 가 맞다. 둘만 있으면 모호하지 않다. 모호성은 대상의 `X.luau`+`X/`, 또는 요구하는 폴더 옆 같은 이름 파일일 때 난다(§2) |
| audit/09 §6 #15 / audit/08 M-09 | `.luaurc` alias: stl·quad "CLI 런타임에서 실패" 대 Studio "알려진 alias 는 동작" | **판정(재현)**: CLI 대 Studio 의 차이가 아니라 **alias 값의 모양** 차이다. 값이 `./lib` 면 CLI 런타임도 동작하고, `lib`·`quad-base/src` 처럼 `./` 가 없으면 CLI 런타임·analyze 는 실패하고 luau-lsp 만 푼다(quad `.luaurc` 가 이 꼴). §3 |
| audit/08 Q-102 / audit/09 S-124 | "잘못된 require 를 luau-analyze 가 진단 0건으로 통과" | **판정(재현, 조건부)**: strict 에서는 `Unknown require` 로 잡힌다. 0건은 nonstrict 와 "다른 모듈로 풀리는 오타"일 때만이다(§5). 원천 당시의 정확한 조건(버전·설정)은 기록이 없다 |

## 정정

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| stl-luau-doctor `.claude/base/architecture.md:48-52` | `.luaurc` 일반 alias 는 편집기 전용, 런타임 require 에서 동작 안 함 | 값이 `./` 로 시작하면 런타임에서 동작한다. `./` 가 없을 때만 실패한다 | `rbx-require-cli.sh` Q6·Q11 |
| quad `.claude/base/project-setup-plan.md:112-142` | 커스텀 alias 는 luau CLI 런타임에서 `could not jump to alias` | 관측은 맞다. 원인은 alias 값에 `./` 가 없는 것(`quad/.luaurc:6-9`)이고, `./quad-base/src` 로 쓰면 동작한다 | 같음 |
| stl-luau-doctor `.claude/base/architecture.md:322-325` | `@self` 대신 `./` 를 쓰면 `luau-analyze` 는 진단 0건 | strict 에서는 `Unknown require: unsupported path`. 0건은 nonstrict 이거나 다른 모듈로 풀릴 때 | `rbx-require-cli.sh` Q8·Q9 |
| quad `.claude/base/project-setup-plan.md:171-176`, `scripts/relink.sh:4-6` | 잘못된 경로·symlink 를 analyze 가 any 로 떨궈 0 진단 | strict 면 `Unknown require`. 0 진단은 nonstrict 또는 luau-lsp(symlink 를 따라감) | `rbx-require-cli.sh` Q8·Q11 |
| moonwave-luau `.claude/conventions.md:73-74` | 정적 검사는 require 경로 오류를 런타임만큼 못 잡는다 | strict 면 풀리지 않는 경로는 잡는다. 다른 모듈로 풀리는 오타는 못 잡는다(처방은 같음) | 같음 |
| tbox `CLAUDE.md:141-145` | 엔트리 `init.luau` 가 `src/init.luau` 와 이름이 겹쳐 ambiguous | 그 조합만으로는 모호하지 않다. 같은 이름 파일·폴더 형제일 때 난다 | `rbx-require-cli.sh` Q4 |
| claude-doctor `decisions/D-12-require-paths.md` §2 둘째 줄 | 정적 검사가 require 경로 오류를 잡지 못한다 | strict 조건을 붙인다(§9) | 같음 |

## 미판정
- **실서버에서 클라이언트 첫 require 시점의 `IsLoaded`.** 절차: 게시한 플레이스에서 LocalScript 첫 줄에 `game:IsLoaded()` 와 `os.clock()` 을 기록하고 Developer Console 로 읽는다.
