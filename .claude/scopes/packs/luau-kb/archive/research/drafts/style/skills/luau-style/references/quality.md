# quality.md — 에러·주석·포맷·테스트·검증·마커·성능 주장

목차
- §1 에러: 메시지 모양, raise 방식, `-O2` 와 error level
- §2 주석과 문서화: 언어, "왜", `---`, `Ref:`, `--#region`, `stylua: ignore`
- §3 포맷: stylua 를 안전하게 돌리는 법
- §4 테스트 관용
- §5 검증과 보고
- §6 코드 `TODO` 마커
- §7 성능 주장

이 파일에서 답하는 질문
- `error(msg, 2)` 를 쓰면 왜 사용자 줄이 안 찍히나?
- 주석은 한국어로? 영어로?
- stylua 를 돌렸더니 `f<<T>>` 가 `f << T >>` 가 됐다.
- 테스트 프레임워크 없이 무엇을 어떻게 단언하나?
- "통과"라고 보고해도 되나?

---

## §1 에러

status: 공통 원칙과 저장소별 형식(D-10). `-O2` 위치 소실은 [실행] `/tmp/cd-exp/syn/o2.luau`(0.742).

**공통**
- 메시지는 영어로 쓰고, raise 줄에 **리터럴 그대로** 둔다. 메시지로 grep 하면 그 자리가 나와야 한다. quad 는 이 이유로 포맷 헬퍼를 기각했다(`architecture.md:462-469`).
- 내부 불변식 위반(자기 버그)은 `error(msg, 1)` 로 쓴다. 터진 자리를 가리켜야 리포트가 쓸모 있다.
- **라이브러리에서 사용자 호출부를 가리켜야 하는 에러에 손으로 센 level 을 쓰지 않는다.**
  ```lua
  -- 나쁜 예: 로컬 헬퍼가 -O2 에서 인라인되면 level 2 가 엉뚱한 프레임이 된다
  local function check(x: any)
  	if type(x) ~= "number" then error("check: expected number", 2) end
  end
  local function user() check("a") end   -- 7행
  -- luau -O1: "./o2.luau:7: check: expected number"
  -- luau -O2: "check: expected number"      ← 위치가 사라짐 (라이브 Roblox 는 -O2 기본)

  -- 좋은 예: 저장소의 raise 헬퍼(스택에서 첫 비라이브러리 프레임을 찾는다)
  return Common.raise("Arr: index must be a number")                     -- stl
  Err.errorBeforeNearest(`Quad0017 Blocker: Policy emit must be a function (got {typeof(emit)})`, SURFACE)  -- quad
  ```
- 헬퍼에 프레임 태그를 단다면 **테이블 필드 경유로 호출되는 함수에만** 단다. 로컬 직접 호출은 인라인돼 태그가 사라진다(quad 스파이크 27). [기록]

**라이브러리 테스트**: 새 raise 자리마다 메시지와 **정확한 사용자 줄**을 같이 단언한다. 메시지만 보면 level 이 틀려도 통과한다.
```lua
local where = debug.info(1, "l") + 1        -- 헬퍼로 재지 않는다(-O2 인라인)
local ok, e = pcall(function() Arr.At(a, 0 / 0) end)
assert(not ok and string.find(e, `:{where}:`, 1, true) and string.find(e, "Arr:", 1, true))
```
(`pcall(Arr.At, …)` 처럼 C 가 직접 부르면 위치가 없다. 사용자 함수로 감싼다.)

**형식은 저장소 것을 따른다**: quad `QuadNNNN Subject: reason (got X)`(ASCII, 부연은 ` - `), stl `Module: 설명`(접두 `stl:`), tbox 소문자 시작(`number too big. maximum allowed value is …`).

## §2 주석과 문서화

- **언어**: 그 파일에 이미 쓰인 언어를 따른다. 새 파일은 저장소 규칙을 따른다(quad 영어, stl·tbox·table-sim·devplorer 한국어, rbvm "짧은 건 영어·긴 이유는 한국어"). 식별자와 에러 메시지는 언제나 영어다(D-08).
- **"왜"를 쓴다.** 코드가 말하는 "무엇"을 반복하지 않는다. 버린 대안과 그 이유, 의도적인 이상한 코드에 대한 경고를 쓴다.
  ```lua
  -- 나쁜 예
  nop(gcHold) -- call nop
  -- 좋은 예 (rbvm 의 실제 의도를 요약)
  nop(gcHold) -- 클로저가 gcHold{proxy, inst, conn} 를 업밸류로 잡아, 실 Instance 가 살아 있는 동안 Proxy 도 살아 있게 한다(Destroy 가 연결을 끊으면 풀림). 지우지 말 것 — design/gc-and-lifecycle.md §2
  ```
- **선언 문서는 `---` 로 쓴다.** luau-lsp 호버에 뜬다. 연속된 `---` 줄만 그 선언의 문서가 된다. 그래서 원장 추적 줄 `-- Ref: 2026-11-10 H-973 typing-limits 8.43` 은 `---` 블록 **위**에 둔다(quad `conventions.md:345`).
- **공개 소스에 원장 번호만 남기지 않는다.** 외부 기여자에게 `H-231` 은 뜻이 없다. 이유 문장 + `Ref:` 꼬리를 쓴다. 번호를 지우지는 않는다(추적용).
- 큰 파일은 `--#region 이름` / `--#endregion 이름` 으로 접는다.
- `-- stylua: ignore` 는 **정확히 그 글자**여야 먹는다. 정렬해 둔 네임스페이스 표에만 쓴다(stl).
- 지금 동작을 고정한 서술에는 **"관측 — 계약 아님"** 을 붙인다(stl·quad). 나중에 바꿔도 BREAKING 이 아니게 하려는 것이다.

## §3 포맷

status: [실행] stylua 2.5.2, `/tmp/cd-exp/syn/g1,g2.luau`, `root/sub`. 설정 값 차이는 D-02.

- 손으로 정렬하지 않는다. 저장소 `stylua.toml` 이 정본이고 `stylua --check` 가 게이트다.
- **저장소 루트에서 실행한다.** 하위 폴더에서 `stylua file.luau` 를 돌리면 상위 설정을 찾지 않는다. 기본 설정(`syntax = All`)이 적용되고, **exit 0 으로** 다음처럼 바뀐다.
  ```lua
  local a = id<<number>>(1)              -- 원본
  local a = id << number >> 1            -- 하위 폴더에서 포맷한 결과 (의미가 깨짐)
  ```
  하위 폴더에서 돌려야 하면 `stylua --search-parent-directories <파일>` 을 쓴다.
- `stylua.toml` 에 `syntax = "Luau"` 가 있는지 본다. 있으면 `f<<T>>`, `f<<A, B>>`, `Box<Box<T>>`, `f<<T>> {…}` 모두 안전했다.
- `<<` 가 든 파일을 포맷한 뒤에는 diff 에서 `<<`/`>>` 를 확인한다.
- quad 에는 `stylua.toml` 이 없다(손 포맷, 탭). 그 저장소에서는 stylua 를 돌리지 않는다.

## §4 테스트 관용

공통(stl·moonwave·tbox·quad):
- 프레임워크 없이 `assert(cond, "메시지")` + `print`/`error` 로 쓴다. 엔트리는 `tests/run.luau`(또는 `test/run.luau`), 파일마다 `spec.<주제>.luau` 다. 파일 끝에서 값을 `return` 한다.
- 실행기는 `luau` CLI 다. lune 은 `const` 를 못 읽는다(D-03).
- **경계 케이스를 고정한다**: 빈 것 / 한 개 / 뒤집힌 구간 / 범위 초과 / 음수 인덱스. 조용히 clamp 하는 API 는 테스트가 없으면 "아무것도 안 함"과 "망가짐"을 가리지 못한다.
- **눈에 안 보이는 것은 오라클과 대조한다**: 이분 탐색은 선형 탐색과, 힙은 정렬 결과와, 무작위 수백 회.
- **테스트 데이터가 우연히 맞지 않게 고른다.**
  ```lua
  -- 나쁜 예: 키가 1,2,3 이면 "키를 인덱스로 쓰는" 버그가 통과
  local m = Map.FromTable({ [1] = 1, [2] = 2, [3] = 3 })
  -- 좋은 예: 키·값·위치를 서로 다른 값으로
  local m = Map.FromTable({ [10] = "x", [20] = "y", [30] = "z" })
  ```
- **새 타입 계약에는 음성 대조군을 만든다.** 일부러 틀린 사용이 정말 에러를 내는지 보는 스파이크와 기대 건수 tsv 다. 진단 0건은 검사가 죽어도 나온다. 절차는 `luau-verify`.
- 특성화 테스트(지금 동작 고정)에는 "옳아서가 아니라 조용히 바뀌지 않게"라고 주석에 적는다(moonwave).

## §5 검증과 보고

- 판정은 저장소 게이트(`scripts/check.sh`, `scripts/test.sh`, `mise run check`)의 **exit code** 로 한다. "ALL PASS" 줄을 세지 않는다. quad 는 실제로 다섯 커밋 동안 exit 1 인 것을 놓친 적이 있다.
- 진단은 **stderr** 로 나온다. `2>/dev/null` 로 버리면 "0건"으로 착각한다.
- `luau` 를 직접 돌릴 땐 상한을 같이 건다: `( ulimit -v 1048576; timeout 60 luau … )`. 무한 고리 돌연변이가 12GB 를 채운 사고가 있었다(stl 2026-10-13). 돌연변이는 작업 트리가 아니라 사본에서 한다. 출력이 비었다고 "생존"으로 세지 않는다. 124·134·137·143 은 "잡힘"이다.
- 보고에서 범위를 구분한다: **"타입·포맷만 통과" / "스펙 통과" / "Studio Play 실측"**. 돌려 보지 않은 것을 "동작 확인"이라고 쓰지 않는다(rbvm·table-sim·devplorer).
- 게이트를 고쳤으면 일부러 한 번 깨뜨려 실패하는지 본다(moonwave).

## §6 코드 `TODO` 마커

```lua
-- 나쁜 예: 추적처 없음, 이유 없음
error("Connection already disposed") -- TODO: fix error message
-- 좋은 예
-- TODO: 메시지에 시그널 이름을 싣는다 — 지금은 어느 연결인지 모름. Ref: todos.md #4
```
- 이유와 추적처(`todos.md` 항목, 원장·이슈 번호)를 붙인다. 끝나면 마커를 지운다.
- 공개 패키지 소스에 원장 번호만 있는 마커를 남기지 않는다(§2).

## §7 성능 주장

- 성능 주장은 **실측으로** 한다. 숫자는 저장소의 한 문서에 모으고(stl `base/perf-measurements.md`) 측정한 Luau 버전과 모드(`-O2`)를 적는다.
- 벤치는 실제 호출 형태로 짠다. 래퍼 클로저 없이 루프에서 직접 부르고, 여러 번 재서 최소값을 쓴다.
- 편의 기능이 기본 경로를 느리게 만들지 않게 한다. 편의는 별도 이름으로 옆에 둔다(stl `PushBack` / `PushBackMany` — 합치면 8~13% 느림).
- 구조(메커니즘, 필드, 경로)는 관측된 문제에만 더한다. 입구 한 줄 검사처럼 싼 품질 개선은 예외다(quad `conventions.md:50-58`).
- 측정 방법과 수치는 `luau-perf` 에 있다.
