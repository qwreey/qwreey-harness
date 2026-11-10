# 스니펫 실행 결과

- 실행일: 2026-11-10
- 명령: `python3 -I tools/check_snippets.py --luau 0.734,0.742 --lsp 1.70.1 --table snippets/*.luau`
- 결과: **38개 전부 통과, rc=0**. 두 버전 모두 `luau-analyze` 새 솔버 기준(`--@solver=old` 표시한 파일만 옛 솔버)이다.
- 칸 읽는 법: `E` = 그 버전에서 살아 있는 `expect-error` 줄 수(음성 대조군), `B` = `bug-present` 줄 수(지금 잡히지 않는 알려진 한계), `run` = 검사 뒤 `luau` 실행까지 통과.
- 마지막 열은 참고용이다. 같은 파일을 `luau-lsp analyze --platform=standard --flag:LuauSolverV2=true` 로 돌려, 진단 줄이 표식과 맞는지만 적었다. 판정에는 쓰지 않는다. 버전 조건이 붙은 줄은 luau-lsp 가 내장한 Luau 판을 하네스가 모르므로 '잡음/무진단' 관측만 괄호로 적었다(1.70.1 은 0.742 에서 고쳐진 넷 중 셋만 고쳐져 있다). `—` 는 `.luaurc` 나 옛 솔버가 필요한 파일이라 건너뛰었다는 뜻이다.

| 스니펫 | luau 0.734 | luau 0.742 | luau-lsp 1.70.1 (참고) |
|---|---|---|---|
| `generics-annotation-does-not-flow.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `generics-bare-lambda-free-type.luau` | ok (E1 B1 run) | ok (E2 B0 run) | 같음 [버전 조건 줄 13:무진단] |
| `generics-body-unchecked.luau` | ok (E1 B3 run) | ok (E1 B3 run) | 같음 |
| `generics-callback-bound-lost.luau` | ok (E3 B1 run) | ok (E3 B1 run) | 같음 |
| `generics-covariant-args-intersection.luau` | ok (E1 B2) | ok (E3 B0) | 같음 [버전 조건 줄 12:잡음,13:잡음] |
| `generics-lambda-context.luau` | ok (E3 B0) | ok (E3 B0) | 같음 |
| `generics-literal-to-indexer-unknown.luau` | ok (E2 B2 run) | ok (E2 B2 run) | 같음 |
| `generics-pack-explicit-args.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `generics-string-key-literal-indexer.luau` | ok (E1 B1 run) | ok (E1 B1 run) | 같음 |
| `modes-luaurc-nonstrict-silences.luau` | ok (E0 B2) | ok (E0 B2) | — |
| `modes-strict-directive-wins.luau` | ok (E2 B0) | ok (E2 B0) | — |
| `recursion-declaration-order.luau` | ok (E1 B2) | ok (E1 B2) | 같음 |
| `recursion-nonuniform-return.luau` | ok (E2 B1) | ok (E2 B1) | 같음 |
| `recursion-old-solver-rejects.luau` | ok (E2 B0) | ok (E2 B0) | — |
| `solver-declared-generic-field.luau` | ok (E2 B1) | ok (E2 B1) | 같음 |
| `solver-generic-intersection-return.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `solver-vararg-tail-call.luau` | ok (E2 B2) | ok (E4 B0) | 같음 [버전 조건 줄 7:잡음,9:잡음] |
| `typefn-diagnostic-only.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `typefn-passthrough-minimal.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `typefn-pcall-available.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `typefn-stripnil-and-error.luau` | ok (E3 B0) | ok (E3 B0) | 같음 |
| `typefn-unreduced-index.luau` | ok (E1 B2) | ok (E1 B2) | 같음 |
| `unions-any-index-nonnil.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `unions-function-narrowing.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `unions-function-table-intersection.luau` | ok (E2 B2) | ok (E3 B1) | 같음 [버전 조건 줄 13:잡음] |
| `unions-keyof-index-param.luau` | ok (E3 B0) | ok (E3 B0) | 같음 |
| `unions-recursive-in-optional.luau` | ok (E3 B3 run) | ok (E3 B3 run) | 같음 |
| `unions-same-name-method-hole.luau` | ok (E2 B1) | ok (E2 B1) | 같음 |
| `unions-singleton-preservation.luau` | ok (E3 B0) | ok (E3 B0) | 같음 |
| `unions-tagged-narrowing.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `variance-covariant-generic-widening.luau` | ok (E1 B1 run) | ok (E1 B1 run) | 같음 |
| `variance-function-arity.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `variance-function-phantom.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `variance-generic-method-contravariance.luau` | ok (E1 B1) | ok (E1 B1) | 같음 |
| `variance-intersection-instantiation.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `variance-read-field.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `variance-value-phantom-nil.luau` | ok (E2 B1) | ok (E2 B1) | 같음 |
| `verify-negative-control.luau` | ok (E1 B0 run) | ok (E1 B0 run) | 같음 |

## 0.734 → 0.742 사이에 바뀐 칸 (버전 조건 표식으로 고정)

| 스니펫 | 0.734 | 0.742 |
|---|---|---|
| `generics-bare-lambda-free-type` | 주석 없는 `return v` 람다의 결과가 `{ string }` 에 들어감(누수) | 잡힘 |
| `generics-covariant-args-intersection` | `Concat(nums, strs)` 가 `{ number & string }` — 양쪽 대입 통과 | `{ number \| string }` — 양쪽 대입 거부 |
| `solver-vararg-tail-call` | `f(mkStr())`, `f(1, mkStr())` 무진단 | 잡힘 |
| `unions-function-table-intersection` | `setmetatable` 형 `__call` 의 인자 무검사 | 잡힘 |

## 하네스 자체 검증 (돌연변이 4종, 전부 실패로 잡힘)

`/tmp` 사본에서 실행했다. 저장소 파일은 건드리지 않았다.

| 변이 | 결과 |
|---|---|
| `expect-error: number` → `expect-error: banana` | FAIL: "메시지에 'banana' 없음" |
| 대조군 줄을 맞는 코드로 고침(`v: number` → `v: string`) | FAIL: "expect-error 인데 0건" |
| 버전 조건을 떼고 `bug-present` 만 남김 | 0.742 에서 FAIL: "bug-present 인데 진단 발생 -> 동작이 바뀜" |
| `bug-present` 파일에서 `expect-error` 줄을 모두 지움 | FAIL: "살아 있는 expect-error 대조군이 없음" |

## 스니펫 밖에서 실측한 것

| 항목 | 결과 | 재현 |
|---|---|---|
| stylua 2.5.2 와 `f<<T>>(...)` | 설정 파일이 없으면(기본 문법) `id<<number>>(1)` 이 `id << number >> 1` 로 **rc=0 인 채** 바뀐다. `syntax = "Luau"` 가 있으면 그대로 둔다. 인자가 여럿인 `two<<number, string>>(…)` 은 기본 문법에서 파싱 에러로 멈춘다 | `tools/repro-stylua-typeargs.sh` (rc=0) |
| 진단 출력 위치 | `luau-analyze`, `luau-lsp analyze` 모두 진단을 **stderr** 로 낸다. 진단이 있으면 rc=1, 린트(`LocalUnused` 등)만 있으면 rc=0 | 수동 |
| `luau-analyze --help` | `--solver={new|old}` 기본값은 new. `--fflags` 같은 플래그 옵션이 없다(한도 플래그는 `luau-lsp analyze --flag:` 로만 줄 수 있다) | 0.742 `--help` |
| mise shim | 프로젝트 `mise.toml` 밖에서 `luau-analyze --help` 를 부르면 `mise ERROR No version is set for shim` 을 내면서도 **rc=0** 이다 | `/code/Projects/claude-doctor` 에서 실행 |
| Roblox 정의 파일 | `luau-analyze` 는 `Instance`, `game` 을 모른다(정의 파일 옵션 없음). `luau-lsp 1.70.1 analyze --platform=roblox --definitions=typedefs/globalTypes.d.luau` 는 `Instance.new("Part").Name` 을 `number` 에 넣는 줄을 잡는다. 정의 파일 없이 `--platform=roblox` 를 주면 경고 후 `Unknown global 'Instance'` | 수동 |
| `const` | `lune 0.10.5 run` 은 `const x = 1` 에서 "Incomplete statement" 로 실패한다. `luau 0.734` 는 실행한다. `luau-analyze 0.742` 는 재대입을 `SyntaxError: Variable 'x' is constant…` 로 잡는다. `stylua 2.5.2 --syntax luau --check` 는 통과한다 | 수동 |

## 강등·정정한 주장 (references 에서 `status: described` 이거나 정정됨)

| 원래 주장 | 원천 | 실측 | 처리 |
|---|---|---|---|
| type function 을 패스스루한 값은 제네릭 self 체이닝이 조용히 깨진다 | quad §6 | 최소 꼴에서 재현되지 않음(`typefn-passthrough-minimal`) | described |
| 제네릭 팔이 든 오버로드 교집합은 제네릭 팔이 선택되지 않는다 | quad 8.19 | 최소 꼴(인자 둘, 콜백 하나)에서는 선택됨 | described |
| type function 안에서 `pcall` 을 쓸 수 없다 | quad 8.18 (luau-lsp 1.69.0) | 0.734, 0.742, luau-lsp 1.70.1 에서 동작함(`typefn-pcall-available`) | 정정: 반대 사실이 verified |
| type function 안의 `error()` 는 함수가 버려져 진단이 안 뜬다(`print` + `never` 만 보인다) | quad luau-test/done/23 머리 주석 1번 | `error()` 메시지가 "errored at runtime" 진단으로 보인다. 다만 결과 타입이 줄지 않아 사용 자리 불일치가 덧붙는다(`typefn-stripnil-and-error`) | 정정 |
| `f<T>(x: T): T` 에 `"bbb"` 를 주면 `string` 으로 뭉개지고 `T & string` 은 `unknown` | quad §7 표 | 두 버전 새 솔버 모두 `"bbb"` 를 보존함. 옛 솔버만 `string` | 정정(`unions-singleton-preservation`) |
| stylua 는 `syntax = "Luau"` 에서도 `f<<T>>` 를 오염시킨다 | tbox CLAUDE.md | 설정이 없을 때만 오염됨 | 정정(`tools/repro-stylua-typeargs.sh`) |
| luau-lsp 1.70.1 에서 새로 걸리는 꼴 둘(재대입되는 옵셔널 함수 업밸류를 `~= nil` 로 좁혀 호출, 제네릭 안 람다의 `return true` 가 바깥 `T` 와 대조됨) | quad 8.38 | 최소 꼴에서 재현되지 않음 | described |
| 한도 플래그와 "Code is too complex" 의 관계 | quad 8.5, 8.7, 8.9, 8.12, 8.28, 8.40, 8.41 | 수천 줄짜리 생성 타입과 `luau-lsp --flag:` 가 필요해 스니펫으로 만들지 않음 | described |
| 다른 모듈의 type function 을 쓰려면 정의 모듈에서 한 번 인스턴스화해 둬야 한다(프라이밍) | quad 8.18 정정, 8.22 | 파일 여러 개와 luau-lsp 플래그 조합이 필요해 만들지 않음 | described |
| `luau-lsp analyze` 가 `luau-analyze` 보다 진단을 덜 낸다(72 대 68) | stl typing-limits "체커" 절 | 이 저장소 스니펫 35개(옛 솔버·.luaurc 파일 제외)에서 버전 조건 줄을 빼면 두 도구 판정이 같음. 큰 파일에서 한 번 관측된 결과 | described(일반화 금지) |
| 다른 호출의 인자인 테이블 리터럴 안에서 람다 파라미터가 추론되지 않는다 | quad 8.13, 8.30 | quad 기록상 luau-lsp 1.70.1 에서 사라짐. 스니펫 없음 | described(역사) |
