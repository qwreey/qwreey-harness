# negative-controls — "진단 0건"을 믿을 수 있게 만드는 방법

## 이 파일이 답하는 질문
- Q1 타입 검사가 0건으로 통과했다. 정말 맞는 코드라는 뜻인가?
- Q2 음성 대조군은 어떻게 만들고, 몇 개를 두어야 하나?
- Q3 알려진 결함(지금은 안 잡히는 것)을 테스트로 어떻게 고정하나?
- Q4 내 게이트가 실제로 무언가를 잡는지 어떻게 확인하나? (돌연변이 검사)
- Q5 검사가 폭주할 때의 자원 상한은?

## 목차
- §1 왜 0건을 믿지 않는가
- §2 음성 대조군 만드는 법
- §3 알려진 결함을 '현재 상태'로 고정하기
- §4 기대표 방식 vs 줄 끝 표식 방식
- §5 돌연변이 검사
- §6 자원 상한과 폭주
- §7 체크리스트

---

## §1 왜 0건을 믿지 않는가
status: verified · last-confirmed: luau 0.742 · 근거: `snippets/modes-luaurc-nonstrict-silences.luau`, `snippets/generics-literal-to-indexer-unknown.luau`, `snippets/recursion-declaration-order.luau`

0건은 세 가지 서로 다른 상황에서 똑같이 나온다.
1. 코드가 실제로 맞다.
2. **검사가 꺼졌다.** `.luaurc` 가 `nonstrict` 이고 파일에 `--!strict` 가 없으면 명백한 에러도 0건이다. CLI 의 `--mode=strict` 는 이를 덮어쓰지 못한다.
3. **타입이 샜다.** `unknown`, 에러 타입, never 처럼 행동하는 타입이 끼면 그 뒤의 검사가 조용히 사라진다(luau-types 스킬의 결함 카탈로그).

출력만으로는 이 셋을 구별할 수 없다. 그래서 **같은 실행 안에서 반드시 잡혀야 하는 줄**을 함께 둔다.

## §2 음성 대조군 만드는 법
status: verified · last-confirmed: luau 0.742 · 근거: `snippets/verify-negative-control.luau`, 하네스 돌연변이 검사(`snippets/RESULTS.md`) · 원천: stl-luau/.claude/base/typing-limits.md 원칙, quad/scripts/doc-snippets.py 통제군

- 주장하는 줄 바로 옆에 **같은 실수의 다른 모양**을 둔다. 예: 람다 파라미터 생략이 문제라면, 생략하지 않은 람다가 잡히는 줄을 둔다. 이 대조군은 "검사기가 이 파일을 strict 새 솔버로 보고 있다"는 증거가 된다.
- 대조군은 **에러 메시지의 일부까지** 기대한다(`-- expect-error: but got 'string'`). 엉뚱한 이유로 난 에러가 대조군을 통과시키지 않게 하기 위해서다.
- 음성 값을 만들 때는 주석으로 만든다: `(nil :: any) :: Box<string>`. 다른 추론 결과(무주석 콜백의 결과 등)로 음성 값을 만들면 그 값이 이미 에러 타입이라 무엇이든 통과한다(quad 8.25 주의, described).
- 실행 가능한 주장은 `assert` 로 **런타임 값이 정적 타입과 다름**을 보인다(예: `assert(type(n) == "string")`, `n: number`). 타입 시스템이 거짓말한다는 가장 강한 증거다.
- 대조군은 프로젝트 게이트에도 둔다. 검사기가 포기하면(too complex 등) 다른 것이 모두 통과해 버리므로, "반드시 진단 2건이 나야 하는 파일", "반드시 런타임 에러가 나야 하는 실행", "반드시 통과해야 하는 실행"을 통제군으로 두고, 어긋나면 게이트를 실패시킨다(quad doc-snippets.py 의 통제군 셋, described).

## §3 알려진 결함을 '현재 상태'로 고정하기
status: verified · last-confirmed: luau 0.734, 0.742 · 근거: `tools/check_snippets.py`, `snippets/generics-bare-lambda-free-type.luau`

- 지금 잡히지 않는 줄에 `-- bug-present` 를 단다. 하네스는 그 줄이 **0건일 때 통과**하고, 진단이 생기면 "동작이 바뀜 → 문서 갱신"으로 실패한다. 솔버가 고쳐지는 순간 알 수 있다.
- 버전마다 다르면 조건을 붙인다: `-- bug-present [<0.742] || expect-error [>=0.742]`. 실제로 0.742 에서 넷이 이렇게 바뀌었다.
- `bug-present` 가 있는 파일에는 그 버전에서 살아 있는 `expect-error` 가 최소 하나 있어야 한다(하네스가 강제). 대조군 없이 "0건이라 결함이 있다"고 주장할 수 없기 때문이다. 같은 파일에 둘 수 없는 경우(파일 전체의 모드가 주제인 경우)에만 `--@no-control 이유` 로 빼고, 짝이 되는 대조 파일을 둔다(`modes-*` 두 파일).

## §4 기대표 방식 vs 줄 끝 표식 방식
status: described · 원천: stl-luau `scripts/spike-expectations.tsv` + `.claude/tools/spike-diff.py`, quad `scripts/doc-snippets.py`, 이 저장소 `tools/check_snippets.py`

| 방식 | 모양 | 장점 | 단점 |
|---|---|---|---|
| 기대표(tsv) | `건수<TAB>경로<TAB>줄,줄,…`, 도구가 줄별 건수를 대조해 어긋난 줄만 출력 | 소스에 표식을 심지 않는다. 큰 스파이크 파일에 맞다 | 줄 번호가 바뀌면 표를 같이 고쳐야 한다 |
| 줄 끝 표식 | `-- expect-error[: 부분]`, `-- bug-present` (이 저장소), `-- 타입 에러` (quad 문서 펜스) | 수정해도 표식이 줄과 함께 움직인다. 짧은 스니펫에 맞다 | 표식이 코드에 섞인다 |
| 펜스 정보 문자열 | 마크다운 ```` ```luau continue ```` / `skip` / `no-run` / `error=<ID>` (quad) | 문서 코드 블록을 그대로 검사한다 | 블록 간 문맥(체이닝, 모듈 등록)을 하네스가 알아야 한다 |

이 저장소는 `.luau` 파일이 정본이고 줄 끝 표식을 쓴다. 문법은 `snippet-markers.md` 에 있다.

## §5 돌연변이 검사
status: verified (이 저장소 하네스) / described (원천) · 근거: `snippets/RESULTS.md` "하네스 자체 검증" · 원천: stl-luau/.claude/tools/mutate.sh

- 게이트가 무언가를 잡는다는 증거는 **일부러 깨뜨렸을 때 실패하는 것**이다. 이 저장소 하네스는 네 가지 돌연변이(기대 문자열 바꾸기, 대조군을 맞는 코드로 고치기, 버전 조건 떼기, 대조군 지우기)를 모두 실패로 잡았다.
- 프로젝트 게이트에 적용하는 법: 작업 트리가 아니라 **사본**에서 돌연변이 하나를 적용하고(`old` 문자열은 파일에 정확히 한 번 나와야 함), 게이트를 돌려 종료 코드로 판정한다. 0 이면 생존(테스트 공백 후보), 1 이면 잡힘이다. 124, 134, 137, 143(시간 초과, 폭주)도 잡힘으로 친다. 하나씩 돌린다. 원천은 작업 트리에서 돌리다 폭주 사고를 겪었다.

## §6 자원 상한과 폭주
status: described · 원천: stl spike-diff.py, 이 저장소 check_snippets.py

- 검사 명령은 `ulimit -v 2097152; timeout 120 luau-analyze …` 처럼 메모리와 시간 상한 안에서 돌린다. 타입 검사는 특정 모양에서 지수적으로 느려지거나 메모리를 다 쓸 수 있다.
- 병렬 검사는 버전에 따라 위험하다. 0.734 의 `luau-analyze` 는 병렬 검사에서 힙을 깨뜨렸다(상류 #3020, stl mise.toml 머리 주석).

## §7 체크리스트
1. 파일 첫 줄이 `--!strict` 인가(.luaurc 에 기대지 않는다)
2. 같은 실행에 잡혀야 하는 대조군이 있고, 메시지 일부까지 기대하는가
3. 알려진 결함은 `bug-present` 로 현재 상태를 고정했는가
4. 결과에 도구와 버전과 솔버를 적었는가("luau-analyze 0.742 새 솔버")
5. 게이트를 바꿨다면 돌연변이 하나로 실패하는지 확인했는가
