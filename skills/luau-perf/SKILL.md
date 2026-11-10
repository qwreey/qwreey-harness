---
name: luau-perf
description: >-
  Luau 코드의 실행 성능을 판단하고 재는 지식이다. 측정부터 시작하는 절차(프로파일, 워밍업·중앙값·GC 통제·음성
  대조군을 갖춘 벤치 하네스)와, luau 0.742 의 -O1·-O2·--codegen 세 모드로 다시 잰 비율을 근거로 메타테이블 비용(겉표
  정수 키 칸 세금과 그 범위, rawget·freeze 로 못 피함), 테이블 배열부·해시부 성장 함정(nil 구멍, 앞에서 비우는 큐,
  생성자 밖 번호 칸 대입, table.create·table.move), 순회 모양(ipairs·일반화 for·next), 호출 모양과 가변 인자·클로저·
  pcall·코루틴 비용, 문자열 누적과 패턴 역추적, 최적화 수준과 --!optimize·-O2 인라인(error level 위치 변화 포함),
  --!native·@native 와 타입 주석의 native codegen 효과, 약한 테이블과 GC 압박·메모리, 알고리즘 선택(해시 대 정렬,
  힙, 결과 표 대 다중 반환)을 다룬다. 코드가 느리다, 최적화해 달라, 벤치마크를 짜거나 결과를 해석한다, 메타테이블
  비용이나 테이블·배열 성능을 묻는다, native 나 --!optimize 를 쓸지 정한다, 메모리·GC 압박이 의심된다 같은 요청에서
  쓴다. Roblox 엔진 API 비용은 roblox-luau, 타입 문제는 luau-types 가 다룬다.
---
# luau-perf

이 스킬은 "이 Luau 코드는 왜 느린가, 무엇을 바꾸면 얼마나 빨라지나"를 다룬다. **수치는 기계마다 다르므로 배수(비율)로 적는다.** 표의 열은 언제나 `버전 모드` 다(0.734 `-O1` 은 원천과 조건을 맞춘 대조 열).

## 결정 트리
1. **측정부터.** 추측으로 고치지 않는다. 느린 경로를 `luau --profile` 이나 실제 호출 모양의 벤치로 찾는다. 어느 모드에서 재는지 정한다(CLI 기본 `-O1`, Roblox 라이브 `-O2`, 서버 native). → `references/benchmarking-method.md` §1–§3
2. **벤치는 하네스로.** 워밍업, 순서 회전, 측정 전 GC, 중앙값, `control` 대조군, 프로세스 반복. 비교 대상 함수는 다른 모듈에 둔다(같은 파일이면 `-O2` 가 인라인한다). → `bench/lib/bench.luau`, `benchmarking-method.md` §2·§5
3. **잡음 바닥을 넘는 차이만 믿는다.** `control` 이 1.00 에서 벗어난 만큼이 잡음이다. 모드 넷에서 방향이 같은지 본다. → `benchmarking-method.md` §4
4. **원인별로 고친다.** 아래 라우팅 표에서 증상을 찾는다. 고친 뒤 같은 벤치로 다시 잰다.
5. **실제 경로로 채택을 확인한다.** 격리 벤치의 승리가 실제 코드에서 뒤집힐 수 있다.

## 라우팅
| 증상 / 질문 | 읽을 곳 |
|---|---|
| 메타테이블을 붙였더니 배열 인덱싱이 느리다, `rawget`·`freeze` 로 피할 수 있나 | `references/metatables.md` §2·§4 |
| 메타테이블 객체의 필드·안쪽 표 접근, 클래스 구조를 어떻게 짜나 | `references/metatables.md` §3·§6 |
| 메서드를 인스턴스에 복사하면, 생성·메모리 비용 | `references/metatables.md` §5 |
| 배열에 nil 구멍, 앞에서 빼는 큐, `table.remove(t, 1)`, 음수 키 | `references/tables.md` §2·§3 |
| 레코드를 번호 칸으로 할까 이름 필드로 할까, 생성자 밖 대입 | `references/tables.md` §4 |
| `table.create`, `table.move`, `table.clone`, `#` 비용, 키 종류별 조회 | `references/tables.md` §5–§7 |
| `ipairs` 대 숫자 for 대 `for k, v in t`, 이터레이터 API 설계, `next(t, k)` | `references/iteration.md` |
| `obj:M()` 대 `Mod.M(obj)`, 함수 감싸기, 동적 dispatch | `references/calls-and-closures.md` §2 |
| 클로저 콜백·업밸류 비용, 가변 인자·`select`·`table.pack`, `pcall`, 코루틴, 인자 표 | `references/calls-and-closures.md` §3–§5 |
| 문자열 `..=` 누적, 파서, 사용자 패턴의 역추적 | `references/strings.md` |
| `-O2`·`--!optimize`, 인라인 조건, `error(msg, 2)` 위치가 `-O2` 에서 틀림 | `references/optimizer-and-native.md` §2–§4 |
| `t.Name` 대 `t[1]`, 다른 모듈 상수 키, `::` 캐스트 비용 | `references/optimizer-and-native.md` §3·§5 |
| `--!native`/`@native` 를 붙일까, 타입 주석이 native 에 주는 효과 | `references/optimizer-and-native.md` §6 |
| 약한 테이블 비용, `__mode="ks"`, ephemeron 누수, GC 시간, 객체 메모리 크기 | `references/gc-and-memory.md` |
| 해시 대 정렬 병합, 힙 짓기, `table.sort` 비교자, 결과 표 대 다중 반환, 자료구조 선택 | `references/algorithms-and-structures.md` |
| Instance 생성·속성 대입·바인더블·트윈 비용, Studio 프로파일러, 라이브 최적화 수준 | roblox-luau 스킬 `references/perf.md`, `references/studio-mcp.md` §6 |

## 자주 밟는 함정 (요약, 0.742)
- 메타테이블이 붙은 표의 `t[i]` 는 `-O1` 1.6 배, native 읽기 2.1 배·쓰기 4.4 배 느리다. 상수 문자열 필드와 안쪽 표는 영향 없다.
- 배열을 채우며 구멍에 nil 을 두면 원소가 해시부로 가서 만들기 8~11 배(자리표시자 방식 대비), 인덱싱 4.6~7.8 배 느리다. 자리표시자로 채우고 끝에 nil 로 바꾼다.
- 앞에서 nil 로 비우며 번호가 계속 커지는 큐는 링 버퍼보다 5~15 배 느리다.
- 번호 칸을 생성자 밖에서 대입하면 만들기가 2.6~2.9 배다. `{prev, nil, value = v}` 처럼 생성자에 자리를 잡는다.
- `-O2` 는 같은 파일 지역 함수를 인라인해 공짜로 만든다. 같은 파일에 흉내 낸 함수로 벤치하면 결론이 틀어진다.
- `-O2`(그리고 `--!native`/`@native`)에서는 손으로 센 `error(msg, level)` 이 위치를 잃거나 틀린 줄을 가리킨다.
- `s ..= x` 누적은 O(n²) 다. 표에 모아 `table.concat`.
- 약한 키 표 `__mode="k"` 는 비워져도 칸 배열이 줄지 않는다(`"ks"` 는 준다). 값이 키를 가리키면 영원히 안 비워진다(ephemeron 아님).

## 근거와 재현
- 벤치: `/code/Projects/luau-kb/bench/*.luau`(19 개), 실행 `bench/run.sh`, 표 `bench/summarize.py`, 결과 `bench/RESULTS.md`·`bench/results/2026-11-10.tsv`.
- 결정적인 주장: `/code/Projects/luau-kb/snippets/perf-*.luau`(8 개, `--@run`), 결과는 `snippets/RESULTS.md` 의 perf 절.
- 최적화 수준·native 의 CLI 주장: `snippets/opt-*.luau`, `snippets/native-*.luau`(luau-testing·verify 담당), `/code/Projects/claude-doctor/drafts/gaps/tools/run_opt.sh`(58 개 검사).
- 원천: stl-luau-doctor `.claude/base/perf-measurements.md`(0.734 `-O1` 중심), 후보표 claude-doctor `audit/08`·`audit/09`. 각 절에 후보 ID 를 남겼다.
