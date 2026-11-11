---
title: "에러를 던지고, 잡고, 테스트하기"
description: "에러 메시지는 영어 리터럴로, 되던지기는 error(e, 0). -O2 인라인으로 손으로 센 error level 이 위치를 잃는 문제와 스택을 걷는 raise 헬퍼, pcall(f(x)) 함정, NaN 경계 검사, 에러 테스트 단언"
keywords:
  - "raise 헬퍼"
  - "raise helper"
  - "error(msg, 2)"
  - "error level"
  - "되던지기"
  - "rethrow"
  - "error(e, 0)"
  - "pcall(f(x))"
  - "xpcall traceback"
  - "attempt to call a string value"
  - "inlining failed: module uses getfenv/setfenv"
  - "NaN 경계 검사"
  - "NaN range check"
  - "믿을 수 없는 값 검증"
  - "rawlen"
  - "에러 메시지 형식"
  - "사용자 줄 가리키기"
kind: reference
category: luau/style/errors
tags: [o2, policy, cli]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# errors — 에러를 던지고, 잡고, 테스트하기

## 이 파일이 답하는 질문
- 에러 메시지는 어떤 모양으로, 어디에 쓰나?
- `error(msg, 2)` 를 썼는데 왜 사용자 줄이 안 찍히거나 엉뚱한 줄이 찍히나?
- 받은 에러를 다시 던지면 왜 `파일:줄:` 이 두 번 붙나? pcall 의 err 는 언제나 문자열인가?
- `pcall(f(x))` 는 왜 에러를 못 잡나?
- 믿을 수 없는 값을 검증할 때 `tostring`·`#`·비교가 왜 위험한가?
- 에러 테스트는 무엇을 단언해야 하나?

## 목차
- §1 메시지 모양과 던지는 값
- §2 level 과 `-O2` 인라인
- §3 pcall·xpcall 함정
- §4 믿을 수 없는 값을 검증할 때
- §5 에러 테스트
- §6 저장소별 형식 (제안 D-10)

---

## §1 메시지 모양과 던지는 값
status: verified (①–④) / described (리터럴 원칙) · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-error-prefix-and-rethrow.luau`, quad `docs/quadnomicon/11-static-grepability-and-error-architecture.md:21-56`, `.claude/base/architecture.md:462-482` · 후보 Q-095, Q-099, R-11

- **메시지는 영어로 쓰고, 던지는 줄에 리터럴로 통째로 둔다.** 메시지로 grep 하면 그 자리가 나와야 한다. 고정 접두를 만드는 포맷 헬퍼를 다른 파일에 두면 grep 단위가 흩어진다.
  - 보간은 된다: `` error(`Lib: index must be a number (got {typeof(i)})`) `` — 고정 부분이 그 줄에 있다.
  - 일곱 저장소 모두 에러 메시지는 영어다. 참고로 조사한 Luau 라이브러리 다섯의 에러 101건도 전부 ASCII 였다.
- 던지는 값과 접두:
  1. `error(msg)` 는 level 1 이라 `"파일:줄: "` 접두가 붙는다. `error(msg, 0)` 은 붙지 않는다.
  2. `error` 는 아무 값이나 던진다. 테이블은 pcall 을 지나도 같은 값이다. **err 를 `string` 으로 가정하지 않는다**(`err: any` 또는 `unknown`).
  3. 받은 에러를 `error(e)` 로 되던지면 접두가 한 번 더 붙는다. **되던질 때는 `error(e, 0)`.**
- 내부 불변식 위반(자기 버그)은 `error(msg, 1)` 로 그 자리를 가리킨다. 인라인돼도 throw 한 줄이 맞게 찍힌다(§2).

## §2 level 과 `-O2` 인라인
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-error-level-o2.luau`, `snippets/opt-o2-error-level.luau`·`snippets/opt-o1-error-level.luau`(인라인 경우별, 최적화 담당), `snippets/test-o2-line-probe.luau` · 결정 문서: claude-doctor `decisions/D-10-error-handling.md` §2 와 정정 · 후보 S-116, Q-097, Q-088

`error(msg, n)` 의 n 은 "error 를 부른 함수에서 몇 프레임 위인가"다. 인라인된 함수에는 프레임이 없어서 n 이 밀린다.

경우별 표(`-O1`/`-O2` 결과: 위치 없음, 틀린 줄, 리터럴 필드 인라인, 대입 필드는 안전)의 정본은 luau-testing `../../luau-testing/references/optimize-levels.md` §2 다. 여기서는 표를 되풀이하지 않는다. 요지는 둘이다.
- 로컬 함수·테이블 **리터럴** 필드 함수는 `-O2` 에서 인라인되어 손으로 센 level 이 위치를 잃거나 틀린 줄을 가리킨다.
- 대입으로 만든 필드 함수(`function M.f`)는 인라인되지 않는다.

- `-O2` 는 라이브 Roblox 게임의 기본이다(described — Roblox 문서 `luau/comments.md` 가 `--!optimize` 기본값을 Studio 테스트 1, 라이브 게임 2 로 적는다. 엔진 안 실측은 없다: luau-testing `optimize-levels.md` §1, roblox-engine `perf.md` §6). `--!native`·`@native` 도 최적화 수준 2 를 강제한다(CLI 실측). 그래서 **`-O1` 로만 도는 테스트는 이 문제를 영원히 못 본다.**
- 같은 모듈에서 `getfenv`/`setfenv` 를 쓰면 모듈 전체의 인라인이 꺼진다(`luau-compile --remarks -O2`: `inlining failed: module uses getfenv/setfenv`, `snippets/test-getfenv-inline-off.luau`). 에러 위치 테스트를 짤 때 이것 때문에 문제가 가려질 수 있다.

**처방**
- 라이브러리가 사용자 호출부를 가리켜야 하는 에러에는 **손으로 센 level 을 쓰지 않는다.**
- 대신 스택을 걸어 "라이브러리 소스가 아닌 첫 프레임"에서 던지는 raise 헬퍼를 쓴다. 모듈마다 자기 소스를 `debug.info(1, "s")` 로 등록해 둔다.
  ```lua
  local LIB_SOURCE = debug.info(1, "s")
  local function raise(msg: string): never
  	local level = 1
  	while true do
  		local s = debug.info(level, "s")
  		if s == nil then break end
  		if s ~= LIB_SOURCE and s ~= "[C]" then error(msg, level) end
  		level += 1
  	end
  	error(msg, 0)
  end
  ```
  `debug.info(level)` 과 `error(msg, level)` 은 같은 프레임을 기준으로 센다. 그래서 `raise` 자신이 인라인돼도 결과가 맞는다(스니펫에서 `-O1`·`-O2` 모두 확인).
- 공개 함수에 층 태그를 달고 태그 프레임을 찾는 방식도 있다. 이때 태그는 **대입으로 만든 필드 함수**(`function M.f`)에만 단다. 로컬 함수와 테이블 리터럴 필드는 인라인돼 태그가 사라진다.

> 정책: 제안(D-10) — 사용자 확인 전. "라이브러리 코드에서는 손으로 센 `error(msg, 2)` 대신 저장소 raise 헬퍼를 쓴다"를 공통 의무로 할지, 앱 코드에도 적용할지는 아직 묻는 중이다. 공통 rules 에는 "저장소에 raise 헬퍼가 있으면 그것을 쓴다"만 두었다.

## §3 pcall·xpcall 함정
status: verified (①②④) / described (③) · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-pcall-arg-eval.luau`, `snippets/style-error-prefix-and-rethrow.luau`, quad `.claude/audit/fallback-xpcall-verification.md:16-27`, moonwave-luau `.claude/known-issues.md:117-127` · 후보 D-R38, D-R39, Q-096, Q-098, S-117

1. **`pcall(f(x))` 는 `f(x)` 를 pcall 밖에서 먼저 부른다.** 성공해도 그 반환값을 호출하려다 실패하고(`attempt to call a string value`), f 의 에러는 잡지 못한다. `pcall(obj.Method, obj)` 의 인덱싱도 pcall 밖이다.
   ```lua
   pcall(work(x))                         -- 나쁜 예
   pcall(work, x)                         -- 좋은 예
   pcall(function() return obj:Method() end)  -- 인덱싱까지 감싸려면
   ```
2. **`local ok = pcall(...)` 는 성공 여부만 담는다.** 결과는 둘째 값이다.
3. traceback 이 필요하면 **핸들러 안에서** 뜬다: `xpcall(f, function(err) trace = debug.traceback(nil, 2); return err end, ...)`. level 2 가 핸들러 프레임을 건너뛴다. traceback 이 필요 없으면 `pcall` 로 충분하다.
4. **C 가 바로 부른 함수의 level 2 는 위치가 없다.** `pcall(f, …)`, `task.spawn(f)`, `coroutine.create(f)` 의 최상단 프레임이 그렇다. 위치 접두가 필요하면 클로저로 한 번 감싼다.
- `coroutine.resume` 은 에러를 던지지 않고 `(false, err)` 를 돌려준다 → `pitfalls.md` §6.

## §4 믿을 수 없는 값을 검증할 때
status: verified (NaN) / described (메타메서드·패턴) · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/style-nan-range-check.luau`, tbox tbox-cr:54-58,111-115,175-179, devplorer dvr:2026-10-20-actions-security.md:30,106-111 · 후보 X-14, D-R37, X-19

- **NaN 과의 비교는 모두 거짓이다.** `if v < min or v > max then reject end` 를 NaN 이 통과한다.
  ```lua
  if v < 0 or v > 1 then return false end          -- 나쁜 예: NaN 통과
  if not (v >= 0 and v <= 1) then return false end  -- 좋은 예
  ```
  하한만 있는 검사(`v >= 0`)는 `math.huge` 를 통과시킨다. inf 는 따로 막는다.
- **믿을 수 없는 값에 `tostring`·`#`·일반화 반복을 쓰면 메타메서드가 돈다.** `__tostring`·`__len`·`__iter` 가 던지거나, yield 하거나, 내용을 속일 수 있다.
  - 검증기는 `pcall(tostring, v)`, `rawlen`, `rawget`, `next` 로 실제 필드만 본다.
  - xpcall 핸들러 안의 `tostring` 이 던지면 핸들러 결과 대신 그 에러가 돌아온다.
  - Roblox 원격 호출은 메타테이블을 벗기지만, 같은 프로세스 안에서 온 값은 해당된다.
- **사용자가 준 Lua 패턴은 생성 시점에 확인한다**(`pcall(string.match, "", p)`). 매칭 때 터지면 에러 자리가 엉뚱하다.

## §5 에러 테스트
status: described (규칙) / verified (줄 측정: `snippets/test-user-line-assert.luau`, `snippets/test-o2-line-probe.luau`) · 근거: stl-luau `.claude/conventions.md:138`, claude-doctor `decisions/D-10-error-handling.md` §2 · 후보 S-118

- 라이브러리의 새 raise 자리마다 **메시지와 정확한 사용자 줄**을 같이 단언한다. 메시지만 보면 level 이 틀려도 통과한다.
  ```lua
  local where = debug.info(1, "l") + 1     -- 줄은 헬퍼로 재지 않는다(-O2 에서 헬퍼가 인라인된다)
  local ok, e = pcall(function() Arr.At(a, 0 / 0) end)
  assert(not ok and string.find(e, `:{where}:`, 1, true) and string.find(e, "Arr:", 1, true))
  ```
- `pcall(Arr.At, …)` 처럼 C 가 직접 부르면 위치가 없다(§3-4). 사용자 함수로 감싼다.
- 에러 위치 테스트는 `-O1` 과 `-O2` 두 모드로 돌린다. 방법은 `luau-testing` 의 optimize-levels, 단언 헬퍼는 assertions 에 있다.

## §6 저장소별 형식 (제안 D-10)
status: described · 근거: claude-doctor `decisions/D-10-error-handling.md` §1
> 정책: 제안(D-10) — 사용자 확인 전. 메시지 형식(번호, 접두, 대소문자)은 각 저장소의 공개 계약이라 맞추지 않자는 제안이다. 저장소 rules 가 정한다.

- 저장소 rules 에 형식이 있으면 그대로 따른다. 예: `Subject: reason (got X)` 꼴, `Module: 설명` 꼴, 소문자로 시작하는 문장 꼴.
- 형식에 오류 번호를 넣는 저장소는 그 번호가 공개 계약이다. 번호를 바꾸거나 재사용하지 않는다.
- 저장소에 규칙이 없으면 §1 의 공통 원칙(영어, 리터럴, `Subject: reason`)만 지킨다.
