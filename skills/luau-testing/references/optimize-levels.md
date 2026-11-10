# optimize-levels — 테스트를 `-O2` 로도 돌려야 하는 이유

## 이 파일이 답하는 질문
- Q1 `luau` CLI 기본(-O1)으로만 테스트하면 무엇을 놓치나?
- Q2 `-O2` 에서 무엇이 바뀌어 테스트가 깨지나? 라이브러리 버그와 테스트 측정 버그를 어떻게 가르나?
- Q3 `--!optimize`, `--!native`, `@native` 가 있는 파일은 CLI 플래그를 따르나?
- Q4 `getfenv` 로 mock 을 주입한 스펙은 `-O2` 를 재현하나?
- Q5 traceback 이나 `debug.info` 의 함수 이름을 단언해도 되나?
- Q6 게이트에는 어떻게 넣나?

## 목차
- §1 결론: 같은 스위트를 `-O1` 과 `-O2` 로 두 번
- §2 `-O2` 에서 바뀌는 것 (D-10 정정 반영)
- §3 소스 지시어가 CLI 플래그를 이긴다
- §4 `getfenv` 가 인라이닝을 끈다
- §5 실례: quad 스펙 3개가 `-O2` 에서만 실패
- §6 게이트에 넣는 법
- §7 정정

---

## §1 결론: 같은 스위트를 `-O1` 과 `-O2` 로 두 번
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/test-o2-line-probe.luau`, `snippets/opt-cli-level-o1.luau`, `snippets/opt-cli-level-o2.luau`, `stl-luau/scripts/check.sh:355-360`, 후보 S-116·S-118, D-10

- `luau` CLI 의 기본은 `-O1` 이다. 최적화 수준 2 는 같은 모듈의 작은 지역 함수를 **호출 자리에 인라인**한다. 인라인된 함수는 스택 프레임이 없어서 `error(msg, level)`, `debug.info(level, …)`, `debug.traceback` 이 보는 프레임이 달라진다.
- 그래서 `-O1` 에서만 도는 테스트는 `-O2` 에서만 나는 실패를 **영원히 보지 못한다.** `opt-cli-level-o1.luau` 는 지시어 없이 기본 실행은 통과하고 `luau -O2` 에서는 첫 단언이 실패한다(하네스의 `--@run-with -O2 => fail` 이 이 음성 대조군을 고정한다).
- Roblox 문서는 `--!optimize` 기본값을 **Studio 테스트 1, 라이브 게임 2** 로 적는다(`/docs/en-us/luau/comments.md`, 2026-11-10 확인. 엔진 안 실측은 없음, roblox-luau `perf.md` §6). 즉 Studio 플레이 테스트도 라이브의 인라인 경로를 보지 못한다. `--!native`·`@native` 는 엔진과 무관하게 수준 2 를 강제한다(§3).
- 최적화 수준·인라인 규칙·native 자체의 설명은 luau-perf 스킬 소관이다. 이 파일은 테스트 쪽 함의만 다룬다.

## §2 `-O2` 에서 바뀌는 것 (D-10 정정 반영)
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/opt-o1-error-level.luau`, `snippets/opt-o2-error-level.luau`, `snippets/opt-o2-traceback.luau`, `snippets/opt-inline-rules.luau`, `snippets/test-o2-line-probe.luau`

| 모양 | `-O1` | `-O2` |
|---|---|---|
| 테스트 헬퍼 `curline()` = `debug.info(2, "l")` | 호출자 줄 | **-1** (헬퍼가 인라인되어 level 2 가 `pcall`) |
| 로컬 함수 안 `error(msg, 2)`, 호출자가 사용자 람다 | 사용자 줄 | **위치 없음** |
| 로컬 함수 안 `error(msg, 2)`, 호출자가 인라인되지 않는 함수(가변 인자 등) | 사용자 줄 | **틀린 줄**(호출자의 호출자) |
| 상수 테이블 리터럴의 필드 함수 `local T = { f = function … end }` | 사용자 줄 | **위치 없음**(리터럴 필드도 인라인된다) |
| 생성 뒤 대입한 필드 `function M.f` | 사용자 줄 | 사용자 줄(인라인 안 됨) |
| `debug.traceback` 의 인라인된 함수 이름 줄 | 있음 | **없음**. 몸통 줄 번호는 남는다 |
| 인라인된 자리의 `debug.info(1, "n")` | 함수 이름 | 바깥 함수 이름(최상위면 `""`) |

- **정정(D-10)**: "테이블 필드를 거치면 `-O2` 에서 안전하다"는 `function M.f` 처럼 **대입으로 만든 필드**에만 맞다. 테이블 리터럴 안에 쓴 필드 함수는 인라인된다. 그리고 손으로 센 level 은 위치를 잃기만 하는 게 아니라 **틀린 줄**을 가리킬 수도 있다.
- 테스트가 깨지는 원인은 둘로 나뉜다. (a) **라이브러리 버그**: 손으로 센 `error(msg, 2|3)` 이 `-O2` 에서 엉뚱한 프레임을 가리킨다. (b) **측정 버그**: 테스트가 헬퍼로 줄을 재거나, traceback 의 함수 이름을 단언한다. (b) 는 `assertions.md` §3 규칙으로 고친다. traceback 은 함수 이름 대신 메시지와 줄로 단언한다.

## §3 소스 지시어가 CLI 플래그를 이긴다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/opt-o1-error-level.luau`(`--@run-with -O2 => ok`), `snippets/opt-o2-error-level.luau`(`--@run-with -O0 => ok`), `snippets/native-directive-forces-o2.luau`, `snippets/native-attribute-forces-o2.luau`, `snippets/native-directive-order.luau`

- 파일 머리의 `--!optimize 1|2` 는 CLI `-O` 를 이긴다. 그런 파일은 `luau -O2` 로 돌려도 지시어 수준으로 컴파일된다. 테스트 대상 모듈에 `--!optimize 1` 이 있으면 `-O2` 실행이 그 모듈의 `-O2` 경로를 재현하지 못한다.
- `--!native` 는 최적화 수준을 2 로 올리고, 파일 어디에든 `@native` 함수가 하나라도 있으면 `--!optimize 1` 보다 우선해 모듈 전체가 수준 2 가 된다. `--codegen` 없이 인터프리터로 돌려도 인라인이 일어난다. 즉 `--!native` 를 붙이는 순간 `-O1` 테스트가 이미 `-O2` 동작을 본다(CLI 실측, 엔진 안은 described).
- `--codegen`(네이티브 실행) 자체는 에러 위치를 바꾸지 않는다. 바뀌는 것은 최적화 수준 때문이다(`opt-*` 의 `--@run-with --codegen => ok`).

## §4 `getfenv` 가 인라이닝을 끈다
status: verified · last-confirmed: luau 0.742 (0.734 동일) · 근거: `snippets/test-getfenv-inline-off.luau`(`--@run-with -O2 => ok; out~helper=ok`), luau.org performance 가이드("inlining is completely disabled for modules that use getfenv/setfenv"), 후보 Q-118·D-R19

- 모듈 안에서 `getfenv` 라는 이름을 **읽기만 해도**(호출하지 않아도) 그 모듈의 `-O2` 인라이닝이 꺼진다. 같은 몸통의 `test-o2-line-probe.luau` 는 `-O2` 에서 `helper=lost` 인데, `getfenv` 한 줄을 더한 사본은 `helper=ok` 다.
- 함의: Roblox 전역을 `getfenv(f).Instance = mock` 으로 주입하는 스펙 파일은 `-O2` 로 돌려도 **그 파일 자신**의 인라인 경로를 재현하지 못한다. 인라이닝은 모듈 단위라 `require` 한 라이브러리 모듈은 여전히 인라인되므로, 라이브러리 쪽 (a) 버그는 잡힌다.
- 주입을 생성자 인자나 모듈 테이블 필드로 받으면 `getfenv` 가 필요 없다(`roblox-boundary.md` §2).

## §5 실례: quad 스펙 3개가 `-O2` 에서만 실패
status: verified · last-confirmed: luau 0.734 (quad 의 핀), 2026-11-10 · 근거: 원천 claude-doctor `drafts/gaps/testing.md` §12(quad 테스트를 `luau -O2` 로 읽기 전용 실행, 64/67 통과), `quad/scripts/test.sh:7,81-84`, `quad/quad-base/test/spec.errorutil.luau:21-23`, `quad/quad-base/src/Relate.luau:28-29`

| 스펙 | 실패 | 분류 |
|---|---|---|
| `spec.errorutil` | "error should blame line …" — 테스트 쪽 `curline()` 헬퍼가 인라인되어 -1 | 측정 버그(§2 (b)) |
| `spec.fallback` | traceback 에 인라인된 함수 이름이 없음 | 측정 버그(이름 단언) |
| `spec.relate` | 에러가 사용자 파일을 가리키지 않음 — 라이브러리의 손으로 센 `error(…, 3)` | 라이브러리 버그(§2 (a), D-10 이 막으려는 모양) |

quad 게이트는 `luau "$f"`(기본 -O1)만 돌려 이 셋을 보지 못했다. 고치는 일은 quad 저장소 소관이다.

## §6 게이트에 넣는 법
status: verified (이 저장소 하네스) / described (원천 게이트) · 근거: `tools/check_snippets.py` 의 `--@run-opt`, `--@run-with`, `stl-luau/scripts/check.sh:349-360`

- 프로젝트 게이트: `luau tests/run.luau` 다음에 `luau -O2 tests/run.luau` 를 같은 상한(`timeout`, `ulimit -v`)으로 한 번 더 돈다. stl-luau 가 이렇게 한다.
- 이 저장소 스니펫: 실행 주장에 `--@run-opt=0,2` 를 단다. 수준마다 결과가 **달라야** 하는 주장은 `--@run-with -O1 => ok; out~…` 와 `--@run-with -O2 => ok; out~…` 처럼 출력으로 판정하고, 한쪽에서 실패해야 하면 `=> fail` 로 음성 대조군을 고정한다. 문법은 luau-verify 스킬 `snippet-markers.md`.
- `-O0` 도 한 번 돌리면 상수 접기에 기댄 단언이 드러난다(접기는 `-O1` 부터, luau-perf 스킬).

## §7 정정
- `quad/scripts/test.sh:81-84` — 스펙을 `luau "$f"`(기본 -O1)로만 돌린다. `-O2` 에서 3개 실패(§5). 게이트에 `-O2` 실행이 없다.
- `quad/quad-base/test/spec.errorutil.luau:21-23` — 기대 줄을 헬퍼 `curline()`(`debug.info(2, "l")`)로 잰다. `-O2` 에서 -1.
- `quad/quad-base/src/Relate.luau:28-29` — 손으로 센 `error(…, 3)`. `-O2` 에서 사용자 줄을 가리키지 않는다.
- D-10 본문 "테이블 필드 경유 호출은 `-O2` 에서 안전" — 대입 필드에만 맞다(이미 claude-doctor `decisions/D-10-error-handling.md` "정정" 절에 반영).
