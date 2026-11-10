---
title: "타입 검사가 못 잡는 언어 함정"
description: "타입 검사가 못 잡는 런타임 함정: table.insert 의 nil·다중 반환 오버로드, 순회 중 키 추가·순회 순서·불안정 정렬, 가변 인자 nil 개수, %a 와 UTF-8 바이트 길이, NaN, coroutine.resume 에러 삼킴, 얕은 clone"
keywords:
  - "table.insert nil"
  - "table.insert(t, f())"
  - "No overload for function accepts 1 arguments"
  - "순회 중 변경"
  - "modify during iteration"
  - "해시 순회 순서"
  - "table.sort 안정 정렬"
  - "stable sort"
  - "select(\"#\", ...)"
  - "table.pack"
  - "다중 반환 잘림"
  - "%a 패턴"
  - "UTF-8 바이트 길이"
  - "utf8.len"
  - "string.format %q"
  - "coroutine.resume 에러 삼킴"
  - "cannot resume dead coroutine"
  - "한 번만 초기화 yield"
  - "table.clone 얕은 복사"
  - "pcall(getfenv, 1)"
kind: reference
category: luau/style/pitfalls
tags: [silent, correction, cli]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# pitfalls — 타입 검사가 못 잡는 언어 함정

## 이 파일이 답하는 질문
- `table.insert` 가 왜 엉뚱한 자리에 넣거나 아무것도 안 넣나?
- 순회 중에 키를 추가해도 되나? 순회 순서를 믿어도 되나? `table.sort` 는 안정 정렬인가?
- 가변 인자에 `nil` 이 끼면 왜 개수가 틀리나? 다중 반환이 왜 하나로 잘리나?
- `%a` 패턴이 왜 `_` 에서 끊기나? 한글 문자열의 길이는?
- `coroutine.resume` 의 에러는 어디로 가나?
- 공유 설정 테이블을 setter 로 고치면 왜 다른 곳이 바뀌나?

## 목차
- §1 테이블에 넣기
- §2 순회: 변경, 순서, 정렬
- §3 가변 인자와 다중 반환
- §4 문자열·패턴·UTF-8
- §5 숫자: NaN 과 inf
- §6 코루틴
- §7 스코프와 환경
- §8 공유되는 값

모든 절은 "에러 없이 틀린다"는 공통점이 있다. 타입 결함은 `luau-types`, 비용은 `luau-perf`, 코루틴·weak 표 의미론은 `luau-runtime`, Roblox 엔진 동작은 `roblox-engine` 이 다룬다.

---

## §1 테이블에 넣기
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-table-insert-pitfalls.luau`, `snippets/style-varargs-and-constructors.luau` · 후보 D-R32, M-14, Q-072, Q-074, X-15

- **`table.insert(t, nil)` 은 아무것도 넣지 않는다.** 병렬 배열이라면 이후 인덱스가 하나씩 밀려 다른 대상에 값이 쓰인다. 자리를 지켜야 하면 `t[i] = v` 로 채운다.
- **`table.insert(t, f())` 는 f 가 돌려주는 값 개수에 따라 뜻이 바뀐다.**
  - 2개면 `insert(t, pos, v)` 오버로드가 되어 엉뚱한 자리에 들어간다. 타입 검사도 통과한다.
  - 0개면 런타임 에러다. `--!strict` 는 이 경우만 잡는다.
  - 처방: `table.insert(t, (f()))` 처럼 괄호로 한 값으로 자른다.
- **범위 밖 `pos`(0, `#t+2` 이상, 음수)는 던지지 않는다.** `t[pos] = v` 로 넣고 `#t` 는 그대로다. `ipairs` 로는 닿지 않는 고아가 생긴다. Lua 5.3+ 의 "position out of bounds" 와 다르다.
- **테이블 생성자에서 같은 키가 두 번 나오면 마지막 값만 남는다.** 생성자는 왼쪽부터 평가한다. 가운데 원소가 던지면 앞서 만든 값(Instance 등)은 고아가 된다(described).
- **배열 판정을 `#` 로 하지 않는다.** `{[0]=…}`, `{[1.5]=…}`, `t[1],t[2],t[4]` 만 있는 표도 `#` 기반 검사를 통과한다. 키가 1..n 연속 양의 정수인지 직접 센다(described).

## §2 순회: 변경, 순서, 정렬
status: described (실측 기록) · 근거: quad `.claude/base/source-state-plan.md:1464-1484`, `.claude/base/dispatch-core-plan.md:470-477`, `.claude/base/architecture.md:623-629`, devplorer dvr:2026-10-21-settings-datastore.md:65-74, rbvm-cr:299,420-428 · 후보 Q-071, Q-073, Q-079, D-R35, R-29

- **순회 중 같은 테이블에 새 키를 넣지 않는다.** 결과가 정의되지 않는다. 구독자 8개를 돌다 첫 콜백에서 하나를 더했더니, 일부는 2회, 일부는 0회 불렸고 실행마다 달랐다(크래시 없음, luau 0.734). yield 를 끼고 순회할 때도 같다.
  - 기존 키의 값을 바꾸거나 `nil` 로 지우는 것은 안전하다.
  - 처방: 배열로 스냅샷을 떠서 순회한다.
- **해시 순회 순서를 믿지 않는다.** 일반화 `for k, v in t` 는 배열 파트를 인덱스 순으로 먼저 돌고 그다음 해시 파트를 돈다. 이것은 구현 동작이지 언어 보증이 아니다.
  - 듬성한 정수 키는 오름차순이 아니다. 같은 내용의 해시도 실행마다 순서가 달라질 수 있다(같은 입력 200회 중 172/28 로 다른 에러가 먼저 났다).
  - thread·테이블을 키로 쓰면 삽입 순서가 아니라 주소 해시 순서다.
  - 순서가 의미 있으면 배열에 둔다.
- **`table.sort` 는 안정 정렬이 아니다.** 원소를 하나 더 넣기만 해도 기존 동률 원소의 순서가 섞였다. 안정 순서가 필요하면 삽입 번호 같은 보조 키를 비교자에 넣는다.
- `for d in seen do` 같은 일반화 반복은 런타임과 `--!strict` 모두 통과한다. "테이블을 호출하려다 죽는다"는 낡은 Lua 지식이다.

## §3 가변 인자와 다중 반환
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-varargs-and-constructors.luau` · 후보 Q-076, R-25

```lua
local function count(...)
	local n = 0
	for _, _ in ipairs({ ... }) do n += 1 end   -- 나쁜 예: (1, nil, 3) 에서 1
	return n, select("#", ...), table.pack(...).n   -- 좋은 예: 3, 3
end
```
- `nil` 이 낄 수 있는 가변 인자는 `select("#", ...)` 로 세거나 `table.pack(...)` 의 `n` 을 쓴다. `table.unpack(t, 1, t.n)` 이면 구멍이 보존된다.
- **다중 반환은 목록의 마지막일 때만 펼쳐진다.** `{ f(), other }` 에서 `f()` 는 첫 값만 남는다. `{ other, f() }` 는 다 펼친다. 인자 목록도 같다.
- 인자가 많을 때 `select(i, ...)` 루프는 O(n²) 이다. 비용 비교는 `luau-perf`.

## §4 문자열·패턴·UTF-8
status: verified (①②③) / described (나머지) · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-strings-ascii-utf8.luau`, moonwave-luau `.claude/conventions.md:124-125`, devplorer dvr:2026-10-19-server-edit.md:171-187 · 후보 D-R27, D-R29, D-R26, M-11

1. **패턴 클래스 `%a`·`%w` 는 ASCII 만 본다.** `é` 는 `%a` 에 맞지 않는다. `%a` 는 `_` 와 숫자를 포함하지 않아 `"@(%a+)"` 가 `@must_use` 를 `must` 에서 끊는다. 식별자는 `[%w_]+` 로 잡는다. `%c` 는 `\0`·DEL 에 맞는다. 앵커 없는 패턴은 줄 가운데서도 맞는다.
2. **`#s` 와 `string.len` 은 바이트 수다**("한" = 3). `string.sub` 는 다바이트 글자 가운데를 자를 수 있다.
   - 잘못된 UTF-8 에서 `utf8.len` 은 `nil, 위치` 를 돌려주고 `utf8.codes` 는 던진다. 그래서 `utf8.len(s) or 0` 은 조용히 0 이 된다.
   - 바이트 한도로 자를 때는 "`utf8.len` 이 nil 인 동안 한 바이트씩 줄이기"(O(n²)) 대신, 이어짐 바이트(0x80–0xBF)를 최대 3번 거슬러 올라간다.
3. **`string.format("%q", s)` 는 개행을 "백슬래시 + 실제 개행"으로 쓴다.** 출력이 두 줄이 된다. 한 줄 로그가 필요하면 직접 이스케이프한다.
- Lua 패턴의 `+`·`*` 는 되돌아간다(backtrack). 공백 뒤가 비면 공백 하나를 내용으로 돌려받는 식이다. 되돌아가지 않는 파서(PEG)를 옮길 때 대안을 풀어 쓴다.
- 문자열 이어 붙이기와 패턴 역추적 비용은 `luau-perf` 에 있다. 로그 위조 방지(보이지 않는 문자 목록)는 `roblox-net` 담당이다(`platform-services.md` §5).

## §5 숫자: NaN 과 inf
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-nan-range-check.luau` · 후보 X-14, Q-080

- NaN 은 자기와 같지 않다. `==` 기반 중복 제거를 늘 통과하고, 경계 검사도 통과할 수 있다 → 검사 꼴은 `errors.md` §4.
- `==` 는 두 값이 같은 `__eq` 를 가질 때 메타메서드를 쓴다. Roblox 데이터타입(`UDim.new(0, 8)` 두 개)은 값으로 같다.
- 테이블 키에서 `t[0/0] = v` 는 에러이고 조회는 `nil` 이다. 맵 API 에서 NaN·`nil` 키를 어떻게 다룰지는 저장소가 정한다.

## §6 코루틴
status: verified (①) / described (나머지) · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-coroutine-resume-swallows.luau`, quad `.claude/archive/v2-initial-implementation/m8-implementation-round18.md:17`, `.claude/qa-request/post-implementation-review-round13.md:224`, `.claude/archive/context-rejected.md:28-36` · 후보 Q-066, Q-067, Q-068, Q-069

1. **`coroutine.resume` 은 에러를 던지지 않고 `(false, err)` 를 돌려준다.** 반환값을 버리면 에러가 조용히 사라진다. 전파하려면 `if not ok then error(err, 0) end`. 죽은 코루틴을 다시 resume 하면 `(false, "cannot resume dead coroutine")` 이다.
- yield 할 수 없는 문맥(메타메서드, `table.sort` 비교자 같은 C 경계)에서 yield 하면 원시 에러로 죽는다. `coroutine.isyieldable()` 로 미리 막는다. 단 luau CLI 최상위에서는 `isyieldable()` 이 참인데도 yield 가 거부된다. 대기는 직접 만든 코루틴 안에서만 한다.
- **"한 번만" 초기화 함수가 yield 하면 두 번 돈다.** 완료 표시를 성공 뒤에 세우면, 기다리는 사이 두 번째 호출이 같은 초기화를 다른 스레드에서 다시 시작한다. 진행 중 상태를 먼저 기록하고 대기자를 모은다.
- Luau 에는 thread-local 도, 비동기 문맥 전파 훅도 없다. 전역 플래그나 코루틴 키로 만든 암묵 문맥은 yield 중 끼어들기, `task.spawn` 한 새 코루틴의 문맥 상실, 재개되지 않을 때의 영구 미완료를 부른다. 문맥은 인자로 넘긴다.
- 코루틴 의미론의 정본은 `luau-runtime` `coroutines.md`, Roblox `task.*` 와 엔진 재개 동작은 `roblox-engine` 담당이다.

## §7 스코프와 환경
status: verified (전역 대입) / described (나머지) · 근거: `snippets/style-bare-function-global.luau`, quad `.claude/base/effect-plan.md:450-453`, quad `.claude/feedback/consumer-kits-studio-qa-2026-10-07.md:512`, quad `.claude/base/brand-plan.md:276-286` · 후보 Q-081, Q-119, Q-048

- `local function` 은 선언 뒤에서만 보인다. 서로 부르는 헬퍼는 사용처보다 먼저 선언하거나, `local f` 로 먼저 이름을 만든 뒤 대입한다.
- 맨 `function name()` 은 전역이다 → `idioms.md` §6.
- `pcall(getfenv, 1)` 은 호출자의 환경이 아니라 실행 중인 스레드의 전역을 돌려준다(pcall 이 C 함수라서). 주입된 환경을 찾으려면 평범한 `getfenv()` 를 쓴다. 그리고 `getfenv`/`setfenv` 를 쓰는 모듈은 `-O2` 인라인이 꺼진다(`errors.md` §2).
- 값의 종류를 duck typing(`v.Foo ~= nil`)으로 가리지 않는다. 일부 Roblox userdata 는 없는 키를 인덱싱만 해도 던진다. `typeof` 나 weak-key 브랜드 표로 가린다.

## §8 공유되는 값
status: described · 근거: quad `.claude/archive/modifier-apply-mutable-rejected.md:20-45`(사용자 결정), quad `.claude/session/2026-09-09-01-docs-polish.md:240`, rbvm-cr:213-222 · 후보 Q-084, Q-085, R-28

- **공유되는 설정·테마 테이블을 제자리 setter 로 고치지 않는다.** 형제 서브트리가 같이 바뀐다. "경계에서만 clone" 절충도 단발 setter 경로에서 샌다. 전부 immutable + clone 으로 두면 이 버그 부류가 통째로 없어진다.
- `table.clone`·`table.freeze` 는 얕다. 안쪽 표는 공유되고 여전히 바꿀 수 있다.
- 고정된 내용의 컨테이너는 배열을 새로 만들어 돌려주기보다 `__iter` 로 일반화 반복을 지원한다. 새 데이터를 만들지 않는다.
- 테이블을 변환·순회하는 함수에는 visited 집합을 둔다. `M.__index = M` 하나로도 순환이 생긴다. 공유 서브테이블이 두 번 처리되는 것도 막는다.

## 정정 (원천 서술이 재현과 다른 것, 각 저장소 세션에 전달)
- "`table.insert(t, f())` 오염은 타입 검사가 잡지 않는다"(후보 M-14, moonwave-luau `.claude/conventions.md:122-123`, mrow-rv:291-300)는 f 가 값 2개를 돌려줄 때만 맞다. 0개를 돌려주는 경우는 `--!strict` 가 `No overload for function accepts 1 arguments` 로 잡는다(`snippets/style-table-insert-pitfalls.luau`).
