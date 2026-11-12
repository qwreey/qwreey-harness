# 스니펫 실행 결과

- 실행일: 2026-11-10
- 명령: `python3 -I tools/check_snippets.py --luau 0.734,0.742 --lsp 1.70.1 --table snippets/*.luau`
- 결과: **55개 전부 통과, rc=0**(2026-11-10 type function 재구성으로 `tf-*` 22개. 옛 `typefn-*` 5개는 `tf-*` 로 이름을 바꿈). 두 버전 모두 `luau-analyze` 새 솔버 기준(`--@solver=old` 표시한 파일만 옛 솔버)이다.
- 0.746: 이 표는 0.734·0.742 만 담는다(표 전체를 다시 뽑지 않았다). 0.746 은 `--luau 0.734,0.742,0.746` 행렬이 전부 rc=0 이고, 0.742 와 다른 파일은 위 `variance-` 둘뿐이라 해당 두 행에 괄호로 적었다.
- 칸 읽는 법: `E` = 그 버전에서 살아 있는 `expect-error` 줄 수(음성 대조군), `B` = `bug-present` 줄 수(지금 잡히지 않는 알려진 한계), `run` = 검사 뒤 `luau` 실행까지 통과.
- 마지막 열은 참고용이다. 같은 파일을 `luau-lsp analyze --platform=standard --flag:LuauSolverV2=true` 로 돌려, 진단 줄이 표식과 맞는지만 적었다. 판정에는 쓰지 않는다. 버전 조건이 붙은 줄은 luau-lsp 가 내장한 Luau 판을 하네스가 모르므로 '잡음/무진단' 관측만 괄호로 적었다(1.70.1 은 0.742 에서 고쳐진 넷 중 셋만 고쳐져 있다. `tf-limit-keyof-scale` 의 '놓침'은 0.734 전용 표식 줄이라 1.70.1 이 0.742 와 같다는 뜻이다). `—` 는 `.luaurc` 나 옛 솔버가 필요한 파일이라 건너뛰었다는 뜻이다.

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
| `tf-builtin-keyof-index.luau` | ok (E5 B0) | ok (E5 B0) | 같음 |
| `tf-builtin-unreduced-index.luau` | ok (E1 B2) | ok (E1 B2) | 같음 |
| `tf-diag-error-vs-print.luau` | ok (E6 B0) | ok (E6 B0) | 같음 |
| `tf-diag-eval-sites.luau` | ok (E4 B2) | ok (E4 B2) | 같음 |
| `tf-diag-only-pattern.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `tf-dx-alias-name-lost.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `tf-dx-hover.luau` | ok (E0 B0) | ok (E0 B0) | 같음 |
| `tf-env-outer-alias-ok.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `tf-env-outer-local.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `tf-env-pcall-available.luau` | ok (E3 B0) | ok (E3 B0) | 같음 |
| `tf-env-unsupported.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `tf-generic-scope.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `tf-limit-keyof-scale.luau` | ok (E4 B0) | ok (E3 B0) | 다름(52:놓침) |
| `tf-limit-stack-overflow.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `tf-noalt-literal-compute.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `tf-noalt-mapped-record.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `tf-noalt-merge.luau` | ok (E3 B3) | ok (E3 B3) | 같음 |
| `tf-noalt-reserved-keys.luau` | ok (E3 B1) | ok (E3 B1) | 같음 |
| `tf-noalt-stripnil.luau` | ok (E6 B0) | ok (E6 B0) | 같음 |
| `tf-passthrough-chaining.luau` | ok (E6 B0) | ok (E6 B0) | 같음 |
| `tf-rebuild-read-indexer.luau` | ok (E3 B1) | ok (E3 B1) | 같음 |
| `tf-serialize-unsupported-arg.luau` | ok (E5 B0) | ok (E5 B0) | 같음 |
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
| `variance-intersection-instantiation.luau` | ok (E3 B0) | ok (E3 B0) | 같음 (대조군 줄을 더해 E2→E3. 0.746: ok E2 B0, r3 줄은 `[<0.746]` 표식) |
| `variance-read-field.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `variance-value-phantom-nil.luau` | ok (E2 B1) | ok (E2 B1) | 같음 (0.746: ok E3 B0 — 8행이 `bug-present [<0.746] \|\| expect-error [>=0.746]`) |
| `verify-negative-control.luau` | ok (E1 B0 run) | ok (E1 B0 run) | 같음 |

## 0.734 → 0.742 사이에 바뀐 칸 (버전 조건 표식으로 고정)

| 스니펫 | 0.734 | 0.742 |
|---|---|---|
| `generics-bare-lambda-free-type` | 주석 없는 `return v` 람다의 결과가 `{ string }` 에 들어감(누수) | 잡힘 |
| `generics-covariant-args-intersection` | `Concat(nums, strs)` 가 `{ number & string }` — 양쪽 대입 통과 | `{ number \| string }` — 양쪽 대입 거부 |
| `solver-vararg-tail-call` | `f(mkStr())`, `f(1, mkStr())` 무진단 | 잡힘 |
| `unions-function-table-intersection` | `setmetatable` 형 `__call` 의 인자 무검사 | 잡힘 |

## `tf-*` 의 luau-lsp 1.69.0 참고 열

`python3 -I tools/check_snippets.py --luau 0.742 --lsp 1.69.0 --table snippets/tf-*.luau` (rc=0). 22개 중 아래 둘만 '다름'이고 나머지는 '같음'이다.

| 스니펫 | luau-lsp 1.69.0 | 뜻 |
|---|---|---|
| `tf-env-pcall-available` | 다름(11:추가, 18:추가) | 1.69.0 은 type function 안의 `pcall` 이 "Unknown global" 이고 실행도 "not supported" 다(limits E4) |
| `tf-limit-keyof-scale` | 다름(48:추가, 50:추가) | 1.69.0 은 150 키 맵의 **맞는** 호출도 too complex 다(limits L3) |

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
| `luau-analyze --help` | `--solver={new|old}` 기본값은 new. `--help` 에는 플래그 옵션이 없지만 `--fflags=이름=값` 은 받는다(0.734·0.742). 0.742 는 모르는 이름에 "Warning: unrecognized flag" 를 낸다. 2026-11-10 정정: 이전 판은 "`--fflags` 옵션이 없다"고 적었다 | 0.742 `--help`, `--fflags=LuauDoNotExportBrokenTypeFunction=true` 실행 |
| type function 모듈 경계·무한 루프 | `bash snippets/tf-cross-module.sh` rc=0, 16개 확인 전부 ok. 프라이밍 문제는 luau-lsp 1.69.0(모든 FFlag 켬)만이다. 1.70.1 에서는 `LuauDoNotExportBrokenTypeFunction` 이 "Unknown FFlag" 다. 무한 루프는 0.734·0.742·lsp 1.70.1 analyze 를 멈춘다(timeout 5초에 rc=124) | `snippets/tf-cross-module.sh` |
| type function hover·자동완성 | 1.69.0·1.70.1 같음. 시그니처 hover 는 `StripNil<T>` 를 그대로 보여 주고, 호출 결과는 `number` 다. `index<Map, K>` 무주석 콜백은 `v: unknown`, 구체 시그니처는 `number` 다. type function 이 만든 테이블은 키 자동완성이 된다 | `python3 -I tools/lsp_probe.py snippets/tf-dx-hover.luau --lsp <ver> --hover 33:16 --hover 36:7 --hover 40:8 --hover 45:8 --complete 49:19` |
| quad 실물 `Quad` 패스스루 | quad-types 패키지를 `/tmp` 로 복사해 `Pass<QuadTypes.Quad>` 뒤 `:AddPlugin` 을 불렀다. 0.742 는 "Type functions do not currently support types of the form 'CheckReservedKeys<keyof<T>>'" 를 내고 `AddPlugin` 키가 사라졌다. 0.734 는 메시지 없이 키만 사라졌다. 직접 쓴 `Quad` 는 정상 검사됐다 | 수동(quad 원본은 읽기만 함) |
| mise shim | 프로젝트 `mise.toml` 밖에서 `luau-analyze --help` 를 부르면 `mise ERROR No version is set for shim` 을 내면서도 **rc=0** 이다 | `/code/Projects/claude-doctor` 에서 실행 |
| Roblox 정의 파일 | `luau-analyze` 는 `Instance`, `game` 을 모른다(정의 파일 옵션 없음). `luau-lsp 1.70.1 analyze --platform=roblox --definitions=typedefs/globalTypes.d.luau` 는 `Instance.new("Part").Name` 을 `number` 에 넣는 줄을 잡는다. 정의 파일 없이 `--platform=roblox` 를 주면 경고 후 `Unknown global 'Instance'` | 수동 |
| `const` | `lune 0.10.5 run` 은 `const x = 1` 에서 "Incomplete statement" 로 실패한다. `luau 0.734` 는 실행한다. `luau-analyze 0.742` 는 재대입을 `SyntaxError: Variable 'x' is constant…` 로 잡는다. `stylua 2.5.2 --syntax luau --check` 는 통과한다 | 수동 |

## 강등·정정한 주장 (references 에서 `status: described` 이거나 정정됨)

| 원래 주장 | 원천 | 실측 | 처리 |
|---|---|---|---|
| type function 을 패스스루한 값은 제네릭 self 체이닝이 조용히 깨진다 | quad §6, stl conventions.md:84 ② | 다섯 꼴 × 네 판(0.734·0.742·lsp 1.69.0·1.70.1)에서 재현되지 않음(`tf-passthrough-chaining`). 실물 `Quad` 는 직렬화 실패로 키를 잃음(위 '스니펫 밖') | described |
| 제네릭 팔이 든 오버로드 교집합은 제네릭 팔이 선택되지 않는다 | quad 8.19 | 최소 꼴(인자 둘, 콜백 하나)에서는 선택됨 | described |
| type function 안에서 `pcall` 을 쓸 수 없다 | quad 8.18 (luau-lsp 1.69.0), quad Surface/init.luau:15 | 0.734, 0.742, luau-lsp 1.70.1 에서 동작하고 `types` API 에러도 잡음. 1.69.0 만 안 됨(`tf-env-pcall-available`) | 정정: 판 한정 사실로 |
| type function 안의 `error()` 는 함수가 버려져 진단이 안 뜬다(`print` + `never` 만 보인다) | quad luau-test/done/23 머리 주석 1번, quad §0, stl papers/03-tuple.md:23 | 네 판 모두 `error()` 메시지가 "errored at runtime" 진단으로 보인다. never 불일치가 덧붙고 호출마다 반복된다(`tf-diag-error-vs-print`) | 정정 |
| `f<T>(x: T): T` 에 `"bbb"` 를 주면 `string` 으로 뭉개지고 `T & string` 은 `unknown` | quad §7 표 | 두 버전 새 솔버 모두 `"bbb"` 를 보존함. 옛 솔버만 `string` | 정정(`unions-singleton-preservation`) |
| stylua 는 `syntax = "Luau"` 에서도 `f<<T>>` 를 오염시킨다 | tbox CLAUDE.md | 설정이 없을 때만 오염됨 | 정정(`tools/repro-stylua-typeargs.sh`) |
| luau-lsp 1.70.1 에서 새로 걸리는 꼴 둘(재대입되는 옵셔널 함수 업밸류를 `~= nil` 로 좁혀 호출, 제네릭 안 람다의 `return true` 가 바깥 `T` 와 대조됨) | quad 8.38 | 최소 꼴에서 재현되지 않음 | described |
| 한도 플래그와 "Code is too complex" 의 관계 | quad 8.5, 8.7, 8.9, 8.12, 8.28, 8.40, 8.41 | 수천 줄짜리 생성 타입과 `luau-lsp --flag:` 가 필요해 스니펫으로 만들지 않음 | described |
| 다른 모듈의 type function 을 쓰려면 정의 모듈에서 한 번 인스턴스화해 둬야 한다(프라이밍) | quad 8.18 정정, 8.22 | luau-lsp 1.69.0(모든 FFlag)에서만 재현. 0.734·0.742·lsp 1.70.1 은 프라이밍 없이 평가(`tf-cross-module.sh`) | 정정: 판 한정 사실로 |
| `luau-lsp analyze` 가 `luau-analyze` 보다 진단을 덜 낸다(72 대 68) | stl typing-limits "체커" 절 | 이 저장소 스니펫 35개(옛 솔버·.luaurc 파일 제외)에서 버전 조건 줄을 빼면 두 도구 판정이 같음. 큰 파일에서 한 번 관측된 결과 | described(일반화 금지) |
| 다른 호출의 인자인 테이블 리터럴 안에서 람다 파라미터가 추론되지 않는다 | quad 8.13, 8.30 | quad 기록상 luau-lsp 1.70.1 에서 사라짐. 스니펫 없음 | described(역사) |
| type function 은 바깥 타입 별칭을 참조하지 못한다, `types.optional` 은 없다 | quad typing-limits §5·8.22 | 네 판 모두 별칭·제네릭 별칭·형제 type function·`types.optional` 이 됨(`tf-env-outer-alias-ok`) | 정정 |
| `Types.Merge` 결과가 닫혀 있지 않아 모르는 키를 못 잡는다 | tbox CLAUDE.md:121 | 손으로 쓴 테이블 타입도 리터럴의 남는 키를 못 잡음. Merge 고유 아님(`tf-noalt-merge`) | 정정 |
| `<U>(self: Ref<U?>) -> U` 로는 nil 을 못 벗긴다 | quad 8.14 | 메소드 제네릭은 맞음. 자유 함수 `<U>(r: Ref<U?>): U` 는 됨(`tf-noalt-stripnil`) | 범위 좁힘 |

## style — `style-*` (luau-style 스킬, 2026-11-10)

명령: `python3 -I tools/check_snippets.py --luau 0.734,0.742 --lsp 1.70.1 --table snippets/style-*.luau` → **13개 × 2 버전 전부 ok, rc=0**. 셸 스니펫 둘은 따로 돌렸다(`bash snippets/style-require-paths.sh` rc=0, 0.734·0.742 각 8건 ok / `bash snippets/style-stylua-pitfalls.sh` rc=0, stylua 2.5.2 4건 ok).

| 스니펫 | luau 0.734 | luau 0.742 | luau-lsp 1.70.1 (참고) |
|---|---|---|---|
| `style-bare-function-global.luau` | ok (E1 B0 run) | ok (E1 B0 run) | 같음 |
| `style-const-local-const-global.luau` | ok (E1 B0 run) | ok (E1 B0 run) | 같음 |
| `style-const-reassign.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `style-coroutine-resume-swallows.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-error-level-o2.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-error-prefix-and-rethrow.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-ifexpr-vs-andor.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-metatable-shadow-inherit.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-nan-range-check.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-pcall-arg-eval.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-strings-ascii-utf8.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `style-table-insert-pitfalls.luau` | ok (E1 B0 run) | ok (E1 B0 run) | 같음 |
| `style-varargs-and-constructors.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |

- 실행 주장은 `assert` 로 고정했다. E0 인 파일은 대조군이 실행 단언 쪽에 있다(나쁜 꼴과 좋은 꼴을 같은 파일에서 둘 다 단언).
- `style-error-level-o2` 의 음성 대조: `--!optimize 2` 줄을 지운 사본을 `luau -O1` 로 돌리면 "손으로 센 level 은 사용자 줄을 못 가리킨다" 단언이 **실패**한다(-O1 에서는 `user:2` 를 정확히 가리킴). 즉 이 스니펫은 `-O2` 에서만 통과한다.
- 처음 판에서 사용자 코드를 `getfenv().loadstring` 으로 불렀더니 `-O2` 에서도 위치가 맞게 나왔다. `luau-compile --remarks -O2` 가 `inlining failed: module uses getfenv/setfenv` 를 보여 줬다. `_G.loadstring` 으로 바꿔 해결했다(같은 사실: `test-getfenv-inline-off.luau`).

### 스니펫 밖에서 관측한 것 (style 담당)
| 항목 | 결과 | 넘길 곳 |
|---|---|---|
| 한 변수 `for i in ipairs(t)` | 0.734·0.742 새 솔버가 `TypeError: Argument count mismatch. Function expects 2 arguments, but 2 are specified` 를 낸다. `for _, v in ipairs(t)`, `for k in pairs(t)`, `for _ in t` 는 깨끗하다. `utf8.codes` 도 같다 | luau-types (거짓 양성 후보, 스니펫 미작성) |
| require 경로와 정적 검사 | strict 의 luau-analyze 는 없는 경로·동적 경로를 `Unknown require: unsupported path` 로 잡는다. nonstrict 는 0건, 있는 다른 파일로 풀리는 오배선은 strict 도 0건 | `style-require-paths.sh` R3, `verify-require.sh`·`rbx-require-cli.sh` 와 결론 같음 |

### 정정 (references 의 '정정' 절에 원천 경로와 함께 있음)
| 원래 주장 | 원천 | 실측 | 처리 |
|---|---|---|---|
| `local const x = 1` 은 린트 경고만 난다 | claude-doctor `.claude/base/decisions/D-01-const.md` §2 | `--!strict` 에서는 `Unknown global 'x'` TypeError. 린트만은 nonstrict 한정 | 정정(`idioms.md`) |
| 맨 `function name()` 에 `GlobalUsedAsLocal` 린트가 난다 | quad `scripts/test.sh:33-35`(후보 Q-082) | 모듈 스코프 선언을 여러 곳에서 쓰면 진단·린트 0건 | 범위 좁힘(`idioms.md`) |
| require 경로 오류는 정적 검사가 못 잡는다 | `decisions/D-12-require-paths.md` | strict 는 없는 경로를 잡는다. 못 잡는 건 nonstrict 와 오배선 | 정정(`modules.md`) |
| 동적 require 경로는 `ambiguous` 에러 | `claude-doctor .claude/archive/research/drafts/style` 초안 `modules.md:315` | CLI 런타임은 실행, strict analyze 만 거부 | 정정(`modules.md`) |
| `tests/init.luau` 의 ambiguous 는 `src/init.luau` 와 이름이 겹쳐서 | tbox `CLAUDE.md:141-147` | 실제 함정은 `./` 가 루트를 가리키는 것. ambiguous 는 `X.luau`+`X/` 형제 | 정정(`modules.md`, 후보 X-04 판정) |
| `table.insert(t, f())` 는 타입 검사가 못 잡는다 | moonwave `conventions.md:122-123`(후보 M-14) | 값 0개 경우는 strict 가 잡는다. 2개 경우만 못 잡음 | 범위 좁힘(`pitfalls.md`) |

### rules·skill 효과 측정 (sonnet, 2026-11-10, Claude Code 2.1.316)
- 과제: 빈 패키지(`src/init.luau` 에 `local Package = {} return Package`)에 "재고 모듈 `src/Inventory.luau` 추가, `Package.Inventory` 로 내보내기, tests/ 에 테스트를 만들어 실제로 돌리기". 규칙을 언급하지 않았다. 명령: `claude -p --model sonnet --allowedTools=Read,Write,Edit,Glob,Grep,Skill,Bash`.
- 조건: 없음 / 프로젝트 `.claude/rules/luau-core.md`(복사본) / 같은 rules + 프로젝트 `.claude/skills/luau-style`(복사본). 각 2회. 사용자 홈의 다른 설정은 세 조건에 같게 걸렸다.
- 채점: 산출 `.luau` 파일을 규칙 12항목으로 자동 검사한 뒤, 정규식 거짓 양성 3건(`pcall(function(` 1건, raise 헬퍼 안의 `error(msg, level)` 2건)을 손으로 고쳤다.

| 항목 | 없음 1 | 없음 2 | rules 1 | rules 2 | +skill 1 | +skill 2 |
|---|---|---|---|---|---|---|
| 모든 새 파일 1행 `--!strict` | X (init·tests) | X (init·tests) | O | O | X (init) | O |
| `and/or` 삼항 없음, 맨 `function` 없음, `local const` 없음, const/local 혼용 없음 | O | O | O | O | O | O |
| `pcall(f(x))` 없음, require 모듈 Pascal, 에러 메시지 리터럴 | O | O | O | O | O | O |
| `init.luau` 에서 `@self/Inventory` | O (`./` 로 썼다가 런타임 실패 뒤 고침) | O (같음) | O (처음부터) | O (처음부터) | O (처음부터) | O (처음부터) |
| 테스트 엔트리가 `init.luau` 아님, 테스트 통과(재실행), analyze 0건 | O | O | O | O | O | O |
| **준수 (12항목)** | **11** | **11** | **12** | **12** | **11** | **12** |
| 손으로 센 `error(msg, 2·3)` | 3곳 | 3곳 | 0 | 0 | 0 (raise 헬퍼) | 0 (raise 헬퍼) |
| `-O2` 로도 테스트 실행 | 아니오 | 아니오 | 아니오 | 아니오 | 예 | 예 |
| 에러 줄 단언 테스트 | 아니오 | 아니오 | 아니오 | 아니오 | 예 | 예 |
| 보고에서 검증 범위 구분("Studio 실측 안 함") | 아니오 | 아니오 | 예 | 예 | 예 | 예 |
| rules 로드(stream 에 본문) / Skill 호출 | — / 0 | — / 0 | 예 / 0 | 예 / 0 | 예 / 1 | 예 / 1 |
| 비용 USD / 시간 초 | 0.11 / 23 | 0.12 / 26 | 0.13 / 31 | 0.14 / 36 | 0.24 / 46 | 0.31 / 63 |

읽는 법
- 대부분의 항목은 규칙 없이도 지켰다. **rules 가 바꾼 것**: 모든 파일의 `--!strict`, 처음부터 `@self` (없음 조건은 둘 다 `./Inventory` 로 썼다가 런타임 실패 뒤 고침), 손으로 센 level 제거, 보고의 검증 범위 구분.
- **skill 이 더한 것**: raise 헬퍼(스택 걷기), 에러 줄 단언, `-O1`·`-O2` 두 모드 실행. 비용은 rules 만일 때의 약 2배다.
- skill 조건의 결함 둘: skill 1 은 `init.luau` 에 `--!strict` 를 빠뜨렸다. skill 2 는 사용자가 정한 `add(name, count)` 를 스킬의 "새 저장소 기본값"(Pascal, 제안 D-09)에 따라 `Add`·`New` 로 바꿨다. 그래서 `naming.md` §3 과 SKILL 결정 트리에 "사용자가 정한 이름이 기본값보다 우선"을 더했다(측정 뒤 수정). 이 문구는 뒤에 "바꾸지 말고 제안"으로 다시 고쳐 재측정했다(아래 "이름 제안 원칙 재측정").
- rules 만 둔 조건에서는 링크된 references 가 프로젝트에 없어 모델이 "규칙 본문만 따랐다"고 보고했다. 사용자 홈 배포(`~/.claude/rules` + `~/.claude/skills/luau-style`)에서는 상대 링크가 풀린다.
- 표본이 조건마다 2회라 차이는 방향만 본다.
- **rules 영어화 뒤 재측정(2026-11-10)**: 본문을 영어로 바꾼 `luau-core.md` 로 rules 조건만 2회 — **12/12, 12/12**(회귀 없음), 두 번 모두 rules 로드·보고에서 검증 범위 구분. 1회는 손으로 센 `error(msg, 2)` 6곳(저장소에 raise 헬퍼가 없어 규칙 위반은 아님, 한국어 본문 때 0). 비용 0.12·0.16 USD. 토큰은 `rules/README.md`.

### 타입 하나를 여러 파일로 나누기 — `style-split-types.sh` (2026-11-10)
명령: `choom -n 1000 -- bash snippets/style-split-types.sh` (기본 0.734 0.742 0.746) → **세 버전 각 23건 ok, rc=0**. 파일이 여럿 필요해서 셸로 잰다.

| 주장 | 0.734 | 0.742 | 0.746 |
|---|---|---|---|
| S1 `Types` + 동작 묶음 + `init` 재수출: 제네릭·콜백·`<<T>>` 보존 | ok | ok | ok |
| S2a 설치자 `require(…)(Arr)` → 소비자에 `Key 'Sort' not found` (런타임은 됨) | ok | ok | ok |
| S2b 다른 모듈이 `Methods.X =` → `Cannot add property` + 소비자 `does not have key` | ok | ok | ok |
| S2c init 이 메서드 표 조립(`setmetatable<Types.Data<T>, typeof(mt)>`) → 깨끗, 어긋남 잡음 | ok | ok | ok |
| S2d 묶음 안 `self:Push` → `Key 'Push' not found in table 'Data<T>'` | ok | ok | ok |
| S2e `local o: Bag<number> = Bag.New()` 어긋남은 한 파일에서도 같음(나눈 탓 아님) | ok | ok | ok |
| S3 묶음 → init 순환 require: 진단 + 런타임 실패. `Ctor.luau` 로 빼면 깨끗 | ok (`Cyclic module dependency`) | ok (`…use 'export' syntax`) | ok (0.742 와 같음) |
| S4 타입 붙은 늦은 조회 표 `S`: 상호 재귀·시그니처·없는 이름·제네릭 필드, 등록 누락은 런타임 nil 호출 | ok | ok | ok |

- 결론: 네임스페이스 모듈(stl `Arr`)은 재수출로 나눠도 타입 손실이 없다. "다른 모듈이 같은 표에 붙이기"는 런타임만 되고 타입에서 사라진다. 메타테이블 객체는 init 이 메서드 표를 조립하는 꼴로 나눈다. → `skills/luau-style/references/splitting.md` §2–3.
- 0.742 부터 순환 진단 문구가 "export syntax" 를 언급한다. 새 export 문법이 순환을 허용하는지는 재지 않았다.

### 이름 제안 원칙 재측정 (sonnet, 2026-11-10, rules + skill 조건 2회)
위 "skill 2 가 `add` 를 `Add` 로 바꾼" 결함 뒤 문구를 바꿨다: "사용자가 정한 이름이 규칙과 어긋나면 바꾸지 말고, 이유와 함께 이름 변경을 제안한다(일괄 수정은 승인 뒤)"(`naming.md` §3, SKILL 결정 트리, rules `luau-core.md` 이름 절, 사용자 결정 D-13 의 4). 같은 과제·같은 명령·같은 채점(`/tmp/style-eval-tools/score.py`)으로 rules + skill 조건만 2회 다시 돌렸다(결과 `/tmp/style-eval2/`).

| 항목 | skill 1 | skill 2 |
|---|---|---|
| 준수 (12항목, 정규식 거짓 양성 손보정) | 11 (`init.luau` `--!strict` 빠짐) | 11 (같음) |
| 사용자 이름 `add`/`remove`/`count` 유지 | **O** | **O** |
| 응답에 이름 변경 제안 | **O**: "타입 고유 연산은 Pascal(`Add` 등)이 맞습니다 … 바꿀지 알려 주세요. 승인 전에는 고치지 않습니다." | **O**: "이름 변경 제안 (승인 전에는 바꾸지 않았습니다) … `Add`, `Remove`, `Count` 로 바꾸면 됩니다. 반대로 `New`, `List` 를 소문자로 통일할 수도 있습니다." |
| 이름을 정하지 않은 것 | `New` Pascal, `list` 소문자(사용자 이름에 맞춤) | `New`·`List` Pascal(기본값) |
| rules 로드 / Skill 호출 | 예 / 1 | 예 / 1 |
| 비용 USD / 시간 초 | 0.26 / 55 | 0.30 / 62 |

- 기대대로 2회 모두 이름을 바꾸지 않았고, 이유를 붙인 제안을 보고에 따로 적었으며, 승인 전에는 고치지 않는다고 밝혔다.
- 남은 결함은 전과 같다: 기존 `src/init.luau` 를 고칠 때 1행 `--!strict` 를 넣지 않았다.
- 조건마다 2회라 방향만 본다.

## 검증·타입·테스트 추가분 (2026-11-10, 하네스 통합 뒤)

- 명령: `python3 -I tools/check_snippets.py --luau 0.734,0.742 --lsp 1.70.1 --table <아래 파일>` → **rc=0**. 이 절의 스니펫 60개(`test-` 11, `pack-` 13, `opt-` 7, `native-` 6, `verify-` 2, 타입 행 재현 `generics-`·`solver-`·`unions-`·`variance-` 21) 전부 통과. Roblox 모드 1개는 luau-lsp 1.70.1·1.69.0 두 버전으로 검사했다.
- 전체 회귀: `snippets/*.luau` 138개 × 두 버전 rc=0, `bash snippets/tf-cross-module.sh` rc=0, `bash snippets/verify-require.sh` rc=0(34개 확인).
- 칸의 `X<n>` 은 실행 머리(`--@run-opt`, `--@run-with`, `--@compile`, `--@inline-remarks`, `--@codegen`) 검사 수다(`skills/luau-verify/references/snippet-markers.md` §2a). `solver-ipairs-single-var` 는 0.746 에서도 통과했다(위양성이 남아 있음).
- 하네스 통합: claude-doctor `.claude/archive/research/drafts/gaps/tools/check_roblox.py` 는 `--mode roblox`/`--@lsp-roblox`(+`--@sourcemap`, `--rbx-lsp`, `--defs`)로, `claude-doctor .claude/archive/research/drafts/gaps/tools/run_opt.sh` 의 29개 확인은 위 실행 머리로 옮겼다. 초안 Roblox 스니펫 13개(`roblox-*`, `parallel-*`)도 `--mode roblox` 로 26/26 ok.

| 스니펫 | luau 0.734 | luau 0.742 | luau-lsp 1.70.1 (참고) |
|---|---|---|---|
| `generics-body-probe-type.luau` | ok (E2 B4) | ok (E3 B3) | 같음 [버전 조건 줄 9:잡음] |
| `generics-callable-namespace.luau` | ok (E2 B1) | ok (E2 B1) | 같음 |
| `generics-callback-fewer-returns.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `generics-pcall-unit-return.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `native-annotation-codegen.luau` | ok (E0 B0 X3) | ok (E0 B0 X3) | 같음 |
| `native-attribute-forces-o2.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `native-attribute-nested.luau` | ok (E0 B0 X2) | ok (E0 B0 X2) | 같음 |
| `native-attribute-syntax.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `native-directive-forces-o2.luau` | ok (E0 B0 run X2) | ok (E0 B0 run X2) | 같음 |
| `native-directive-order.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `opt-cli-level-o1.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `opt-cli-level-o2.luau` | ok (E0 B0 X2) | ok (E0 B0 X2) | 같음 |
| `opt-fold-unroll.luau` | ok (E0 B0 run X4) | ok (E0 B0 run X4) | 같음 |
| `opt-inline-rules.luau` | ok (E0 B0 X1) | ok (E0 B0 X1) | 같음 |
| `opt-o1-error-level.luau` | ok (E0 B0 run X3) | ok (E0 B0 run X3) | 같음 |
| `opt-o2-error-level.luau` | ok (E0 B0 run X2) | ok (E0 B0 run X2) | 같음 |
| `opt-o2-traceback.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `pack-alias-cannot-yield-pack.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `pack-extra-args-exposure.luau` | ok (E4 B8) | ok (E4 B8) | 같음 |
| `pack-extra-args-old.luau` | ok (E5 B0) | ok (E5 B0) | — |
| `pack-extra-args.luau` | ok (E3 B2) | ok (E3 B2) | 같음 |
| `pack-function-type-variadic-syntax.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `pack-generic-forwarding.luau` | ok (E6 B0) | ok (E6 B0) | 같음 |
| `pack-pcall-failure-value.luau` | ok (E2 B1 run) | ok (E2 B1 run) | 같음 |
| `pack-return-pack-union-syntax.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `pack-store-generic-pack.luau` | ok (E4 B0 run) | ok (E4 B0 run) | 같음 |
| `pack-syntax-no-tuple-alias.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `pack-truncation.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `pack-unsound-positions.luau` | ok (E3 B3 run) | ok (E3 B3 run) | 같음 |
| `pack-variadic-select.luau` | ok (E5 B2) | ok (E5 B2) | 같음 |
| `solver-cast-overlap-only.luau` | ok (E1 B2) | ok (E1 B2) | 같음 |
| `solver-explicit-args-freeze-never.luau` | ok (E3 B0) | ok (E3 B0) | 같음 |
| `solver-generic-method-self-type.luau` | ok (E2 B2) | ok (E2 B2) | 같음 |
| `solver-ipairs-single-var.luau` | ok (E1 B0 run) | ok (E1 B0 run) | 같음 |
| `solver-pcall-builtin-overload.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `solver-table-literal-cache-poison.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `solver-table-literal-read-field-ok.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `solver-union-iter-no-indexer.luau` | ok (E1 B1) | ok (E1 B1) | 같음 |
| `test-blame-filename-only.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `test-cli-runtime-facts.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 같음 |
| `test-deferred-shim.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `test-error-shapes.luau` | ok (E0 B0 run X2) | ok (E0 B0 run X2) | 같음 |
| `test-gc-weak-probe.luau` | ok (E1 B0 run X1) | ok (E1 B0 run X1) | 같음 |
| `test-generic-eq-helper.luau` | ok (E3 B2) | ok (E3 B2) | 같음 |
| `test-getfenv-inline-off.luau` | ok (E0 B0 X2) | ok (E0 B0 X2) | 같음 |
| `test-mini-runner.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `test-o2-line-probe.luau` | ok (E0 B0 X2) | ok (E0 B0 X2) | 같음 |
| `test-user-line-assert.luau` | ok (E0 B0 run X2) | ok (E0 B0 run X2) | 같음 |
| `test-virtual-clock.luau` | ok (E0 B0 run X1) | ok (E0 B0 run X1) | 같음 |
| `unions-annotated-local-branch-narrowing.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `unions-callable-table-not-function.luau` | ok (E1 B0 run) | ok (E1 B0 run) | 같음 |
| `unions-catchall-indexer-intersection.luau` | ok (E1 B2) | ok (E1 B2) | 같음 |
| `unions-closure-loop-narrowing.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `unions-generic-union-param.luau` | ok (E4 B0) | ok (E4 B0) | 같음 |
| `unions-intersection-iter-method.luau` | ok (E2 B1) | ok (E2 B1) | 같음 |
| `unions-self-ref-optional-hole.luau` | ok (E1 B1) | ok (E1 B1) | 같음 |
| `variance-optional-generic-field.luau` | ok (E1 B0) | ok (E1 B0) | 같음 |
| `verify-engine-free-globals.luau` | ok (E2 B0) | ok (E2 B0) | 같음 |
| `verify-fflags-force-strict.luau` | ok (E1 B0) | ok (E1 B0) | — |

| 스니펫 (Roblox 모드) | luau-lsp 1.70.1 | luau-lsp 1.69.0 |
|---|---|---|
| `solver-roblox-datetime-tolocaltime.luau` | ok (E1 B0) | ok (E1 B0) |

### 0.734 → 0.742 에서 바뀐 칸 (이 절)

| 스니펫 | 0.734 | 0.742 |
|---|---|---|
| `generics-body-probe-type` | 제네릭 몸통의 `return 5`(기대 `T`) 무진단 | 잡힘(0.739 `LuauSoundGenericMismatches`). luau-lsp 1.70.1 도 잡음 |

### 하네스 실행 머리 돌연변이 (6종, 전부 실패로 잡힘)

| 돌연변이 | 결과 |
|---|---|
| `opt-o1-error-level` 의 `--@run-with -O2 => ok` 를 `fail` 로 | FAIL "기대 fail, rc=0" |
| `opt-inline-rules` 의 `[inline:variadic]` 를 `[inline:ok]` 로 | FAIL "got=variadic" |
| `native-annotation-codegen` 크기 단언 방향을 뒤집음 | FAIL "untyped*3 < typed 거짓" |
| `native-attribute-nested` 의 `names = f` 를 `f,g` 로 | FAIL "함수 목록 ['f'] ≠ ['f', 'g']" |
| `opt-fold-unroll` 의 `out!~math\.sqrt` 를 `out~` 로 | FAIL "출력에 /math\.sqrt/ 가 없음" |
| `opt-cli-level-o2` 의 기대 출력 문자열을 없는 문자열로 | FAIL "출력에 /…/ 가 없음" |
| `verify-fflags-force-strict` 에서 `--@args` 를 지움 | FAIL "expect-error 인데 0건"(플래그가 실제로 일함) |

### 스니펫 밖에서 실측한 것 (이 절)

| 항목 | 결과 | 재현 |
|---|---|---|
| `luau-analyze --fflags` | 0.734·0.742 모두 받는다(`--help` 에는 없음). 불리언만 바뀌고, 모르는 이름은 `Warning: unrecognized flag`, 정수 한도는 `Warning: unrecognized value '10'` 로 무시, rc 무영향. `DebugLuauForceStrictMode=true` 는 `.luaurc` nonstrict 를 덮는다 | `snippets/verify-fflags-force-strict.luau`, 수동 |
| luau-lsp 플래그 함정 | 1.70.1: 같은 `--flag:` 두 번이면 앞의 값이 이김(`LuauSolverV2=false` 가 먼저면 넘친 인자를 잡고 `=true` 가 먼저면 못 잡음). `--platform` 두 번이면 `Duplicate argument` | 수동 |
| require 해소 | strict 의 없는 경로 → `Unknown require`, nonstrict → 0건 rc=0. symlink: luau 런타임 실패, analyze `Unknown require`, luau-lsp 는 풂. alias 값 `./lib`·절대 경로는 런타임 동작, 접두 없는 `lib` 는 `could not jump to alias`(luau-lsp 만 풂). `luau-analyze src tests` 는 같은 진단을 두 경로로 2번 | `bash snippets/verify-require.sh` |
| `UnknownType` 린트 | 정의 파일 없는 `typeof(v) == "Instance"` 는 `UnknownType` 린트, strict 에서도 rc=0. `(typeof(v) :: string)` 캐스트로 사라짐(0.734·0.742·lsp 1.70.1) | 수동 |
| 새 솔버의 넘친 인자 | `local function f(a: number)` 에 `f(1, 2)` 무진단, require 를 넘어도 같음 | `pack-extra-args*.luau`, 수동 |

### 강등·정정한 주장 (이 절)

| 원래 주장 | 원천 | 실측 | 처리 |
|---|---|---|---|
| `luau-analyze` CLI 에는 플래그 옵션이 없다 | 이 저장소 `luau-types/references/recursion-and-limits.md:75`, `luau-verify/references/checkers.md` §1 | `--fflags=` 있음(불리언만) | 정정 |
| `--mode=strict` 로 `.luaurc` 를 못 덮으니 CLI 로 strict 를 강제할 방법이 없다 | 이 저장소 `luau-verify/references/tooling.md` §1 | `--fflags=DebugLuauForceStrictMode=true` 로 강제됨 | 정정 |
| 커스텀 `.luaurc` alias 는 luau CLI 런타임에서 실패한다(편집기 전용) | quad `.claude/base/project-setup-plan.md:339-348`, 후보 Q-104·S-125 | alias 값에 `./` 가 없을 때만 실패. `./x`·절대 경로는 0.734·0.742 런타임 동작 | 조건 추가 |
| 풀리지 않는 require 는 luau-analyze 진단 0건("거짓 클린") | quad `scripts/relink.sh:4-6`, stl `base/architecture.md:322-329`, 후보 Q-102·S-124 | nonstrict 파일에서만. strict 는 `Unknown require` | 조건 추가 |
| 타입 행 정정(교집합 원인, 모듈 필드 오타, 유니온 제네릭 조건, 클로저 좁히기 둘째 모양) | quad `research/kit-packaging-plan.md:73,91`, stl-luau-doctor `conventions.md:40`, `base/typing-limits.md:371-386`, devplorer `feedback/quad-upstream-2026-10-20.md:494` | 각 스니펫 참고 | `luau-types/references/solver-limits.md` §7 |
| quad 테스트 게이트(-O1 만, 파일 이름만 단언, 헬퍼로 기대 줄, 손으로 센 level) | quad `scripts/test.sh:81-84`, `quad-base/test/mock.luau:854-858`, `spec.errorutil.luau:21-23`, `quad-base/src/Relate.luau:28-29` | `-O2` 에서 3건 실패 | `luau-testing/references/repo-practices.md` §3 |

## rbx — `rbx-*` (2026-11-10, 처음엔 roblox-luau 스킬. 같은 날 스킬을 나눠 담당이 갈렸다)

- 담당: `rbx-gc-*`·`rbx-require-cli.sh` → luau-runtime(엔진 없이 성립), `rbx-types-*` → luau-roblox(`api-types.md`), `rbx-parallel-*` → roblox-engine(`parallel-luau.md`)·luau-roblox. 접두는 바꾸지 않았다(외부 인용 보존).

- 명령: `python3 -I tools/check_snippets.py --luau 0.734,0.742 --table snippets/rbx-*.luau` → **17개 전부 통과, rc=0**. 머리 `--@lsp-roblox` 인 14개는 하네스 Roblox 모드(luau-lsp 1.70.1·1.69.0, `--platform=roblox`, `typedefs/globalTypes.d.luau`, 새 솔버)로, 나머지 3개(`rbx-gc-*`)는 luau-analyze + `luau` 실행으로 돈다.
- 여러 파일이 필요한 require 주장: `bash snippets/rbx-require-cli.sh` → 51개 확인 전부 ok, rc=0(luau 0.734·0.742, luau-lsp 1.70.1).
- `rbx-types-*`·`rbx-parallel-*` 13개는 claude-doctor `.claude/archive/research/drafts/gaps/snippets/` 의 `roblox-*`·`parallel-*` 를 이름만 바꿔 옮겼다. `rbx-types-engine-calls.luau` 는 새로 썼다.
- Studio 런타임 동작(신호, Destroy, 트윈, 엔진 GC)은 스니펫으로 만들지 않았다. references 에서 `status: described` + 원천 Studio 실측 경로로 둔다(Studio MCP 미사용).

| 스니펫 | luau 0.734 | luau 0.742 |
|---|---|---|
| `rbx-gc-no-ephemeron.luau` | ok (E0 B0 run) | ok (E0 B0 run) |
| `rbx-gc-probe-pitfalls.luau` | ok (E0 B0 run) | ok (E0 B0 run) |
| `rbx-gc-weak-modes.luau` | ok (E0 B0 run) | ok (E0 B0 run) |

| 스니펫 (Roblox 모드) | luau-lsp 1.70.1 | luau-lsp 1.69.0 |
|---|---|---|
| `rbx-parallel-actor-messaging-types.luau` | ok (E4 B1) | ok (E4 B1) |
| `rbx-parallel-sharedtable-iter-old-solver.luau` | ok (E1 B0) | ok (E1 B0) |
| `rbx-parallel-sharedtable-types.luau` | ok (E6 B3) | ok (E6 B3) |
| `rbx-parallel-task-phase-signatures.luau` | ok (E4 B2) | ok (E4 B2) |
| `rbx-types-attributes-typeof.luau` | ok (E5 B2) | ok (E5 B2) |
| `rbx-types-constructors-services.luau` | ok (E11 B0) | ok (E11 B0) |
| `rbx-types-constructors-standard.luau` | ok (E3 B0) | ok (E3 B0) |
| `rbx-types-docs-isa-sample.luau` | ok (E1 B0) | ok (E1 B0) |
| `rbx-types-engine-calls.luau` | ok (E5 B2) | ok (E5 B2) |
| `rbx-types-enums.luau` | ok (E9 B0) | ok (E9 B0) |
| `rbx-types-find-wait-nil.luau` | ok (E3 B1) | ok (E3 B1) |
| `rbx-types-isa-refinement.luau` | ok (E7 B0) | ok (E7 B0) |
| `rbx-types-signals-datatypes.luau` | ok (E7 B1) | ok (E7 B1) |
| `rbx-types-sourcemap-children.luau` | ok (E3 B0) | ok (E3 B0) |

재현으로 정정·조건을 붙인 원천 주장(상세는 각 reference 의 "정정" 절):

| 원래 주장 | 원천 | 실측 | 처리 |
|---|---|---|---|
| 테스트 엔트리 `init.luau` 가 `src/init.luau` 와 이름이 겹쳐 ambiguous | tbox `CLAUDE.md:141-145`, 후보 X-04 | 둘만으로는 모호하지 않다. 대상의 `X.luau`+`X/`, 또는 요구 폴더 옆 같은 이름 파일일 때만(`rbx-require-cli.sh` Q4) | 정정(luau-runtime `require-by-string.md` §2) |
| `.luaurc` alias 는 CLI 런타임에서 안 된다 | stl `base/architecture.md:48-52`, quad `project-setup-plan.md:112-142` | 값에 `./` 가 없을 때만. luau-lsp 는 그 꼴과 symlink 도 푼다(Q6·Q11) | 조건 추가(§3–4) |
| 잘못된 require 를 analyze 가 0건으로 통과 | stl `base/architecture.md:322-325`, quad `relink.sh:4-6`, moonwave `conventions.md:73-74` | strict 면 `Unknown require`. 0건은 nonstrict, luau-lsp 의 symlink·alias, 다른 모듈로 풀리는 오타(Q8·Q9) | 조건 추가(§5) |
| Luau weak-key 표는 ephemeron 이다(탐사자 판정) | quad `audit/tween-completed-2026-09-21` 탐사자 기록 | 아니다. 포획 업밸류를 비운 프로브 결함(`rbx-gc-no-ephemeron`, `rbx-gc-probe-pitfalls`) | 정정(원천 REPORT 가 이미 무효 처리) |
| `TweenService:Create` 목표 표·`TweenInfo.new` 명시 nil 은 타입이 잡는다(암묵 가정) | — | 둘 다 통과한다(`rbx-types-engine-calls` bug-present). `GetPropertyChangedSignal` 리터럴 이름은 잡는다 | 새 사실(`api-types.md` §11) |

## perf — `perf-*` (luau-perf 스킬, 2026-11-10)

명령: `python3 -I tools/check_snippets.py --luau 0.734,0.742 --table snippets/perf-*.luau` → 7 개 전부 통과, rc=0. 모두 `--@run` 런타임 단언이다(타입 진단 표식 없음).

| 스니펫 | luau 0.734 | luau 0.742 | 주장 |
|---|---|---|---|
| `perf-closure-cache.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 고정 업밸류 클로저는 반복마다 같은 객체, 반복 변수 캡처는 새 객체(Q-005) |
| `perf-ctor-slots-memory.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 번호 칸 3 < 번호 2+이름 1 < 이름 3, 트리 노드 6칸도 번호 칸이 작다(S-P19·S-P20) |
| `perf-ipairs-raw.luau` | ok (E0 B0 run) | ok (E0 B0 run) | `ipairs`·일반화 for 는 `__index` 를 보지 않는다(S-P06) |
| `perf-next-from-hash-key.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 해시부 키에서 `next(t, k)` 를 시작하면 앞에 놓인 큰 키를 놓친다(S-P34) |
| `perf-nil-hole-hash-part.luau` | ok (E0 B0 run) | ok (E0 B0 run) | 구멍을 nil 로 두며 채우면 원소가 해시부로 간다(S-P17) |
| `perf-table-move-raw.luau` | ok (E0 B0 run) | ok (E0 B0 run) | `table.move` 는 메타메서드를 부르지 않는다(S-P03) |
| `perf-weak-ks-shrink.luau` | ok (E0 B0 run) | ok (E0 B0 run) | `__mode="k"` 는 비워져도 칸 배열을 붙잡고 `"ks"` 는 준다(S-P35) |

- 돌연변이 3 종(`/tmp` 사본: `"k"`→`"ks"`, 해시부 판별 단언 뒤집기, `next` 단언 뒤집기)은 모두 FAIL 로 잡혔다.
- 시간 주장은 스니펫이 아니라 `bench/*.luau`(19 개)로 쟀다. 원표는 `bench/RESULTS.md`, 원자료는 `bench/results/2026-11-10.tsv`(0.734 `-O1`, 0.742 `-O1`/`-O2`/`-O2 --codegen`, 프로세스 3 개).
- 부수 발견: `luau-analyze`(0.734·0.742)는 `collectgarbage` 를 모른다(Unknown global). 스니펫에서는 `(_G :: any).collectgarbage` 로 꺼냈다.
- luau-perf 는 ephemeron 스니펫을 따로 두지 않았다. ephemeron 의미론은 `rbx-gc-no-ephemeron.luau`(luau-runtime)가 정본이다.

### perf 재측정으로 정정한 주장

| 원래 주장 | 원천 | 재측정(0.742, 모드 셋 + 0.734 `-O1`) | 처리 |
|---|---|---|---|
| 글자마다 도는 Luau 파서는 `gmatch`+`tonumber` 보다 약 40 배 느리다 | claude-doctor .claude/audit/09 M-05 요약(원문 mrow REVIEW:809-813 은 컴비네이터 라이브러리 값) | `string.byte` 손 파서가 0.69~0.74x(인터프리터), 0.25x(native) | **방향 뒤집힘**. `strings.md` §5 |
| 정렬 병합은 해싱을 못 이긴다(Union 5.9 배 느림) | stl perf 9절, claude-doctor .claude/audit/09 S-P14·S-P47 | 이미 정렬된 배열 병합이 해시의 0.27~0.38x(비교자 함수를 거쳐도 0.39~0.57x). 정렬부터 하면 해시가 1.16~1.24 배 이김 | **방향 뒤집힘(일반화 범위)**. `algorithms-and-structures.md` §8 |
| 업밸류를 든 클로저가 지역 함수보다 5~8 ns 비싸다 | stl perf 55절, S-P27 | `-O1` 차이 없음(0.95~0.97). `-O2` 3.5x·native 6.3x 는 지역 함수 인라인 때문 | **원인 정정**. `calls-and-closures.md` §7 |
| `#` 는 O(log n), 20만에서 약 90 ns | stl perf 17절, S-P33 | 경계 캐시로 반복 호출은 필드 읽기의 0.83~1.03 배 | 조건 정정. `tables.md` §8 |
| 숫자 키 조회가 테이블 키보다 싸다(9.1 대 14.8 ns) | stl perf 39절, S-P23 | 배열부 정수만 0.49~0.76x. 해시부 정수·실수 키는 1.16~1.43x 로 더 느림 | 범위 정정. `tables.md` §8 |
| 가변 인자는 원인 아님(±2 ns) | stl perf 54절 | 고정 인자 대비 13~28%(인터프리터), 66~79%(native) | 53절 쪽 채택. `calls-and-closures.md` §7 |
| 메타테이블 부착 작은 배열 96 B | stl perf 1-부절, S-P05 | 80 B(메타테이블 유무 같음) | 수치 정정. `metatables.md` §8 |
| `-O2` 는 테이블 필드 경유 호출을 인라인하지 않는다, 위치가 "사라진다" | decisions D-10, quad 스파이크 27 | 리터럴 테이블 필드는 인라인, 틀린 줄도 가리킴(`run_opt.sh` 58/58, 2026-11-10 재실행) | D-10 정정 절과 같음. `optimizer-and-native.md` §4·§8 |
