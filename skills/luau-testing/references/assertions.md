# assertions — 테스트 구조와 단언 패턴, 에러 메시지와 사용자 줄 단언

## 이 파일이 답하는 질문
- Q1 프레임워크 없이 테스트 케이스와 단언을 어떤 모양으로 짜나?
- Q2 `pcall` 로 잡은 에러 값은 던진 방식마다 어떻게 생겼나? 메시지를 어떻게 단언하나?
- Q3 "에러가 사용자 줄을 가리킨다"를 어떻게 단언해야 `-O2` 에서도 맞나?
- Q4 파일 이름만 보는 blame 단언은 왜 부족한가?
- Q5 손으로 만든 `eq<T>` 단언 헬퍼가 타입 불일치를 못 잡는 이유는? 타입 회귀 테스트는 어떻게 짜나?
- Q6 테스트 데이터는 어떻게 골라야 우연한 통과를 피하나?

## 목차
- §1 케이스 구조와 단언 메시지
- §2 에러 값의 모양
- §3 사용자 줄 단언 (`-O2` 에서도 맞는 모양)
- §4 파일 이름만 보는 단언의 구멍
- §5 단언 헬퍼의 타입과 타입 회귀 테스트
- §6 데이터 고르기: 경계 케이스, 서로 다른 값, 비교 횟수

---

## §1 케이스 구조와 단언 메시지
status: described (관례) / verified (러너 모양) · 근거: `snippets/test-mini-runner.luau`, `stl-luau/.claude/conventions.md:155`, `table-sim/<비공개>`, 후보 S-119

- 케이스 하나 = 함수 하나. 러너가 `pcall` 로 감싸 실패를 모은다(`runners.md` §3).
- `assert(조건, 메시지)` 의 메시지에 **기대값과 실제값**을 넣는다(`` `passed={passed} failed={#failures}` ``). 실패 출력만 보고 원인을 알 수 있어야 한다.
- 즉시 실패형 스펙은 절마다 `do … end` 로 지역을 가둔다. 앞 절의 지역이 뒤 절의 단언을 우연히 통과시키는 일을 막는다.
- Luau 의 `assert(false, msg)` 는 Lua 5.1 과 달리 메시지 앞에 `파일:줄:` 위치를 붙인다(§2). 메시지를 `==` 로 비교하지 말고 부분 문자열로 찾는다.

## §2 에러 값의 모양
status: verified · last-confirmed: luau 0.742 (0.734 동일, `-O0/-O1/-O2` 같음) · 근거: `snippets/test-error-shapes.luau`(`--@run-opt=0,2`)

| 던진 방식 | `pcall` 이 돌려준 값 |
|---|---|
| `assert(false, "boom")` | `"<파일>:<줄>: boom"` |
| `assert(false)` | `"<파일>:<줄>: assertion failed!"` |
| `assert(nil, 테이블)` | 테이블을 던지지 않는다. `"invalid argument #2 to 'assert' (string expected, got table)"`. 타입 검사기도 `string?` 자리라고 잡는다 |
| `error("m", 0)` | `"m"` (위치 없음) |
| `error("m", 2)` 를 **`pcall` 이 직접 부른 함수**에서 | `"m"` (level 2 가 C 함수 `pcall` 이라 위치 없음). `pcall(Lib.f, x)` 꼴도 같다 |
| `error(테이블)` | 그 테이블 자체(동일성 유지) |

- 구조화된 에러(코드, 필드)를 단언하려면 `error(테이블)` 로 던지고 `assert(err == payload)` 나 필드를 본다. `assert` 로는 테이블을 던질 수 없다.

## §3 사용자 줄 단언 (`-O2` 에서도 맞는 모양)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/test-user-line-assert.luau`(`--@run`, `--@run-opt=0,2`), `snippets/test-o2-line-probe.luau`, `stl-luau/tests/spec.common.luau:99-130`, `stl-luau/.claude/conventions.md:138`, 후보 S-118, D-10

라이브러리가 "사용자 호출부"를 가리켜야 하는 에러는 메시지와 **정확한 사용자 줄**을 같이 단언한다. 네 규칙을 같이 지킨다.
1. 기대 줄은 단언할 자리에서 `where = debug.info(1, "l") + 1` 로 잰다. **헬퍼 함수로 빼지 않는다.** `curline()` = `debug.info(2, "l")` 같은 헬퍼는 `-O2` 에서 인라인되어 level 2 가 `pcall` 이 되고 `-1` 을 돌려준다(`test-o2-line-probe.luau` 의 `helper=lost`).
2. 메시지만이 아니라 `":{where}: "` 까지 찾는다(§4).
3. 라이브러리 함수는 **사용자 함수 안에서** 부른다: `pcall(function() where = …; Lib.f(x) end)`. `pcall(Lib.f, x)` 는 위치가 없다(§2).
4. 같은 스위트를 `luau -O2` 로도 돌린다. 이유와 실측은 `optimize-levels.md`.

라이브러리 쪽에서 손으로 센 `error(msg, 2|3)` 이 `-O2` 에서 틀리는 문제와 대안(스택을 걸어 첫 비라이브러리 프레임에서 던지기)은 luau-style 스킬의 에러 주제이고, 이 파일은 그것을 **테스트로 잡는 법**만 다룬다.

## §4 파일 이름만 보는 단언의 구멍
status: verified · last-confirmed: luau 0.742 (0.734 동일, `-O2` 같음) · 근거: `snippets/test-blame-filename-only.luau`, `quad/quad-base/test/mock.luau:854-858`, `stl-luau/.claude/conventions.md:138`, 후보 S-118

- `string.find(msg, "spec.x.luau")` 처럼 파일 이름만 보는 blame 단언은, 라이브러리가 level 을 잘못 세서 **같은 파일의 다른 줄**(또는 테스트 파일 안의 헬퍼 줄)을 가리켜도 통과한다. 스니펫은 `error(msg, 1)` 돌연변이가 파일 이름 단언을 통과하고 줄 단언에서만 걸리는 것을 보인다.
- "라이브러리 내부(`/src/`)를 가리키지 않는다"를 추가로 봐도, 테스트 쪽 헬퍼 줄을 가리키는 오류는 남는다.
- stl-luau 는 raise 자리를 돌연변이로 하나씩 바꿔 보고 "메시지만 보면 level 이 틀려도 통과한다"를 확인한 뒤 줄 단언을 규칙으로 정했다(described).

## §5 단언 헬퍼의 타입과 타입 회귀 테스트
status: verified · last-confirmed: luau 0.742 (0.734 동일, luau-lsp 1.70.1 새 솔버 동일) · 근거: `snippets/test-generic-eq-helper.luau`

- `local function eq<T>(actual: T, expected: T)` 에 `eq(n, "1")`(`n: number`)을 넘겨도 진단이 없다. `T` 가 `number | string` 으로 풀린다.
- 정적으로 잡으려면 `eq<<number>>(n, "1")` 처럼 명시 타입 인자를 주거나 타입이 고정된 헬퍼(`eqNumber`)를 쓴다. 둘 다 "Expected this to be 'number', but got 'string'".
- `pcall` 이 돌려주는 에러 값은 `any` 다. `local s: number = err` 도 검사되지 않는다. `tostring(err)` 로 받는다.
- 런타임 판정은 그대로 동작하므로(`==` 가 false) 테스트는 실패해 드러난다. 하지만 이 헬퍼로 "타입 테스트"를 하면 아무것도 검사하지 않는다. **타입 회귀 테스트는 실행이 아니라 `luau-analyze` 의 기대 진단으로** 짠다. 표식 문법과 음성 대조군은 luau-verify 스킬(`snippet-markers.md`, `negative-controls.md`).
- 이 사용자 저장소의 실례: table-sim 은 게이트에 "반드시 타입 에러가 나야 하는 파일" 3개와 린트 대조군 1개를 둔다(`table-sim/<비공개>`), devplorer 는 `tests/negative/` 에 같은 용도의 파일을 둔다, tbox 는 `test/static` 을 luau-lsp 로 검사한다(`tbox/mise.toml:46`).

## §6 데이터 고르기: 경계 케이스, 서로 다른 값, 비교 횟수
status: described · 근거: `stl-luau/.claude/conventions.md:156-158`, `stl-luau/.claude/papers/05-quad-survey.md:241-246`, `VideoSync/CLAUDE.md:103-105`, 후보 S-121·O-05

- 경계 케이스를 모두 고정한다: 빈 것, 한 개, 뒤집힌 구간, 범위 초과, 음수 인덱스. Luau 표준 함수 다수가 범위를 조용히 잘라 내므로(clamp) 테스트가 없으면 "아무것도 안 함"과 "망가짐"을 구별할 수 없다.
- 키·값·위치가 **서로 다른 값**이 되게 고른다(`10, 20, 30`, `"x", "y"`). 키가 `1, 2, 3` 이면 키를 인덱스로 잘못 쓰는 버그가 통과한다.
- 눈으로 안 보이는 성질은 **참조 구현과 대조**한다(이분 탐색 ↔ 선형 탐색, 힙 ↔ 정렬 결과)를 무작위 입력 수백 회로. 차등 시험 일반은 `negative-controls.md` §4.
- 복잡도 주장은 시간이 아니라 **비교 횟수 카운터**로 고정한다. 시간은 기계와 부하에 따라 흔들린다.
- 무작위 입력의 결과에 "정확히 0" 같은 정확값을 한 시드로 단언하지 않는다. 운 좋게 통과한 시드일 수 있다. 성질(부등식, 비교)을 단언하고, 여러 시드로 돌리고, 대조군을 둔다(VideoSync 의 사례: 정확값 단언 둘이 시드의 약 1/3 에서 거짓이었다).
