# type-functions — `type function`, `types.*`, `keyof`/`index`

## 이 파일이 답하는 질문
- Q1 type function 을 써도 되는가? (정책이 저장소마다 다르다. §0 참고)
- Q2 type function 으로 오용을 컴파일 타임 에러로 띄우려면 어떻게 쓰는가?
- Q3 type function 안에서 `error()`, `pcall`, `print` 는 어떻게 동작하는가?
- Q4 `StripNil` 같은 변환은 되는가?
- Q5 다른 모듈에서 `export type function` 을 썼더니 조용히 아무 일도 안 일어난다.
- Q6 `types.*` API 에서 extern(Roblox 클래스) 타입을 어떻게 다루는가?

## 목차
- §0 정책 (미정): 쓰지 않음 vs 진단 전용
- §1 진단 전용 패턴
- §2 `error()`, `print`, `pcall`
- §3 변환 타입 함수 (StripNil)
- §4 결과 타입 합성의 위험 (보고된 함정)
- §5 줄어들지 않은 타입 함수 결과
- §6 모듈 경계와 프라이밍
- §7 API 사실 메모

---

## §0 정책 (미정): 쓰지 않음 vs 진단 전용
status: described · 원천: quad/.claude/base/typing-limits.md §0 "타입 함수는 진단을 띄우는 데까지만"; stl-luau/.claude/papers/03-tuple.md §1 "type function 을 쓰지 않습니다"

> 정책: 미정 — decisions/ 참고

| 입장 | 내용 | 근거 |
|---|---|---|
| quad: **진단 전용** | 허용 범위는 타입이 못 잡는 오용을 컴파일 타임 에러로 만드는 것(버전 불일치, 예약 키 충돌)까지다. 결과 타입이나 접근 타입을 합성하는 용도로는 쓰지 않는다. 검사 결과는 원본과 섞이지 않는 별도 필드에만 싣는다 | 합성을 거친 값에서 제네릭 self 체이닝이 깨졌다(§4), 바깥 별칭을 참조할 수 없다, `keyof`/`index` 도 같은 문제를 가진 내장 type function 이다 |
| stl-luau: **쓰지 않음** | 가급적 사용을 피한다. type function 기반 설계(튜플 등)를 더 밀지 않는다 | quad 가 같은 길에서 부작용으로 대부분을 폐기했다. 체이닝이 공개 표면의 핵심이라 §4 와 정면으로 부딪힌다 |

두 입장은 **방향이 같고 강도만 다르다**(제한적 사용). 공통 분모는 "결과 타입을 합성하지 않는다"이다. 이 파일의 나머지 사실은 정책과 무관하게 참이다. 어느 정책을 택하든 아래 함정은 알고 있어야 한다.

## §1 진단 전용 패턴
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/typefn-diagnostic-only.luau`

```luau
type function MustBeSingleton(t: type): type
	if t.tag == "singleton" then
		return types.singleton(true)
	end
	print("MustBeSingleton: expected a literal type, got " .. t.tag)
	return types.never
end
type Checked<T> = { __check: MustBeSingleton<T> }
```

- 검사에 실패하면 `print(메시지)` 를 하고 `types.never` 를 돌려준다. `print` 출력이 사용 자리의 `TypeError: <메시지>` 로 보인다. 같은 줄에 "Expected this to be unreachable" 이 함께 뜬다.
- 검사 결과는 **원본 타입과 섞지 않는다**. 성공 시에도 트리비얼한 표식(`types.singleton(true)`)을 별도 필드(`__check`)에만 싣고, 원본 `T` 는 type function 을 거치지 않게 한다(quad §6 처방, described).
- 검사는 반환 타입이나 필드 타입처럼 **호출부마다 실제로 해석되는 자리**에 둔다. 함수 본문 안의 지역 타입 별칭에 두면 인스턴스화될 때마다 재평가되지 않아 진단이 뜨지 않는다(quad luau-test/done/23 머리 주석 2번, described).
- 사용 자리에서 그 필드를 참조해야 평가된다(지연 평가, described).

## §2 `error()`, `print`, `pcall`
status: verified · last-confirmed: luau 0.742 (0.734 동일), luau-lsp 1.70.1 · 근거: `snippets/typefn-stripnil-and-error.luau`, `snippets/typefn-pcall-available.luau`

- `error("boom")` 은 "'Bad' type function errored at runtime: … boom" 진단으로 보인다. 다만 결과 타입이 줄어들지 않아 사용 자리마다 `Expected 'Bad<number>'` 불일치가 덧붙는다. 메시지를 깔끔하게 보이려면 `print` + `types.never` 를 쓴다. 원천의 "error() 는 함수가 실패한 걸로 버려져 진단이 안 뜬다"는 이 버전들에서 그대로 재현되지 않는다(메시지는 보인다).
- `pcall` 은 type function 안에서 **동작한다**(0.734, 0.742, luau-lsp 1.70.1). quad 8.18 의 "pcall 은 not supported / Unknown global 'pcall'" 은 luau-lsp 1.69.0 관측이다. 그래도 안전한 호출을 원하면 `t.tag == "singleton"` 처럼 먼저 태그를 보고 `:value()` 를 부르는 쪽이 버전에 덜 민감하다.
- type function 안에서 같은 파일의 바깥 지역 변수는 참조할 수 없다(컴파일 실패, stl conventions 기록, described).

## §3 변환 타입 함수 (StripNil)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/typefn-stripnil-and-error.luau` · 원천: quad 8.14

`<U>(self: Box<U?>) -> U` 같은 제네릭으로 nil 을 벗기려 하면 두 솔버 모두 `unknown` 이 된다(described). 대신 유니온 성분에서 `nil` 을 빼고 `types.unionof` 로 다시 묶는 type function 은 동작한다: `number?` → `number`, `(number | string)?` → `number | string`, nil 없는 타입은 그대로. 새 솔버는 **type function 본문도 검사**하므로 지역 테이블에 `local comps: { type } = {}` 주석이 필요하다.

정책 메모: 이것은 결과 타입을 합성하는 용도다. §0 의 "진단 전용" 입장에서는 경계에 있다(quad 는 이 함수를 실제로 쓴다).

## §4 결과 타입 합성의 위험 (보고된 함정)
status: described · 원천: quad typing-limits §6, luau-test/done/23; quad 8.39; stl papers/03-tuple.md §1 · 반증 기록: `snippets/typefn-passthrough-minimal.luau`

- **보고**: 값의 정적 타입이 type function 을 한 번이라도 거치면(`return t` 패스스루라도), 그 뒤 제네릭 self 메소드(`<Self, P>(self: Self, …) -> Self & P`)의 체이닝이 "Expected this to be exactly 'P & Self', but got 'P & Self'" 같은 무의미한 진단으로 깨졌다.
- **이 저장소의 재현 시도**: 최소 꼴(패스스루 `Pass<Core>` 뒤 `AddPlugin`)에서는 **재현되지 않았다**. 체이닝 결과가 정상으로 검사된다. 원래 관측은 다른 패키지 타입이 얽힌 실물 코드에서 나왔다. 그래서 이 절은 described 다. 재현 파일이 생기면 verified 로 올린다.
- 메소드가 든 큰 재귀 타입(전체형)을 type function 안에서 조립하면 그 자리가 `*error-type*` 으로 깨졌다. 읽기 전용 뷰 타입으로 대신 조립했다(quad 8.39, luau-lsp 1.70.1, described).
- 제네릭 `K` 에 의존하는 type function 결과가 `any` 로 줄어드는 자리(`Box<index<P, K>>` 에서 `P[K]` 가 `any`)는 직접 쓴 `Box<any>` 와 달리 통과하지 못했다(quad 8.27, described).

## §5 줄어들지 않은 타입 함수 결과
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/typefn-unreduced-index.luau` · 원천: stl luau-solver-issues/7

제네릭 `M` 에 의존하는 `index<…, M>` 를 반환하는 함수를 다른 제네릭에 함수 **값**으로 넘기면, 결과가 줄어들지 않은 채 `string`, `{ x: string }` 등 아무 타입에나 대입된다(never 처럼 행동). 같은 값을 `number` 에 직접 넣는 대조는 잡힌다. `index`/`keyof` 결과를 고차 함수로 흘려보내지 말고, 경계에서 구체 타입 주석으로 고정한다.

## §6 모듈 경계와 프라이밍
status: described · 원천: quad 8.18 (2026-09-16 정정), 8.22

- `luau-lsp analyze` 는 옵션 없이 부르면 **모든 FFlag 를 켠 채** 돈다. 그중 `LuauDoNotExportBrokenTypeFunction=true` 때문에, 정의 모듈이 자기 `export type function` 을 **한 번도 인스턴스화하지 않으면** 그 함수가 수출되지 않는다. 그러면 소비자의 `M.Fn<…>` 이 진단 없이 `*error-type*` 이 된다. VSCode 확장과 Studio 는 `--no-flags-enabled` 와 동기화된 값으로 돌아 이 문제가 없었다.
- **규칙(프라이밍)**: `export type function F` 를 두는 모듈에는 `type _Prime = F<…>` 같은 인스턴스화를 하나 둔다. 인스턴스화 한 번이 함수 전체를 열고, 인자는 달라도 된다. 프라이밍이 빠진 오용은 소비자 쪽에서 `*error-type*` 으로 흡수되어 exit 0 이 된다. 그래서 정적 스캔(같은 파일에 `F<` 가 있는가)으로 강제하는 편이 낫다.
- cross-package 로 쓰려면 `export type function` 이어야 한다. 명시 인스턴스화 인자가 둘 이상이면 이중 꺾쇠가 필요하다(quad luau-test/done/23, described).

## §7 API 사실 메모
status: described · 원천: quad 8.22 (luau-lsp 1.69.0, VSCode, Studio 세 환경 실측)

- extern(클래스) 타입: `cls:properties()`(그 레벨만), `cls:readparent()`, `tostring(cls)` 가 클래스 이름이다. `:name()`, `:parent()` 는 없다. `readproperty` 는 테이블 전용이다. extern 멤버는 `properties()` 를 돌며 찾는다.
- `types.newtable` 의 props 인자는 `{ [type]: { read: type?, write: type? } }` 모양이다. `types.optional` 은 없다. `types.unionof(t, types.singleton(nil))` 로 만든다.
- 체커 동작(진단 문구, 테이블 키 자동완성)은 세 환경이 같았다. **다른 것은 타입 정의 데이터**였다: 클래스별 프로퍼티 수, deprecated 멤버 포함 여부, 이벤트가 테이블인지 extern 인지. 어느 환경의 타입 데이터에도 읽기 전용 표시는 없다.
- `keyof<T>` 를 `T` 가 테이블이 아닐 수도 있는 자리에 넣으면 "Type 'string' does not have keys" 로 죽는다. 조건부 타입이 없어 가릴 수 없다(quad 8.15).
