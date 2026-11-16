---
title: "측정부터, 그리고 믿을 수 있게 재는 법"
description: "추측 대신 측정부터: 프로파일, 워밍업·순서 회전·측정 전 GC·중앙값·control 대조군을 갖춘 벤치 하네스, -O1·-O2·--codegen 모드 선택, 잡음 바닥 읽기, 같은 파일 인라인 같은 벤치 함정과 bench/ 실행법"
keywords:
  - "벤치마크 짜는 법"
  - "마이크로벤치"
  - "microbenchmark"
  - "benchmark harness"
  - "벤치 하네스"
  - "luau --profile"
  - "워밍업 중앙값"
  - "잡음 바닥"
  - "noise floor"
  - "control 대조군"
  - "벤치 함정"
  - "측정부터"
  - "os.clock"
  - "bench/run.sh"
  - "summarize.py"
  - "어느 모드로 재나"
  - "Bench.run"
kind: reference
category: luau/perf/measurement
tags: [measured, cli, o2]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# benchmarking-method — 측정부터, 그리고 믿을 수 있게 재는 법

## 이 파일이 답하는 질문
- Q1 최적화하기 전에 무엇부터 재나? 추측으로 고치면 왜 안 되나?
- Q2 마이크로벤치는 어떻게 짜나(워밍업, 반복, 중앙값, `os.clock`, GC 통제, 음성 대조군)?
- Q3 어느 모드(`-O1`, `-O2`, `--codegen`)로 재나? Roblox 의 실제 조건과 무엇이 다른가?
- Q4 결과를 어떻게 읽나? 몇 % 차이부터 믿나?
- Q5 자주 밟는 벤치 함정은?
- Q6 이 저장소의 `bench/` 는 어떻게 돌리고, 새 벤치는 어떻게 더하나?

## 목차
- §1 원칙: 측정부터
- §2 하네스 규칙
- §3 모드와 실제 조건
- §4 결과 읽기와 잡음 바닥
- §5 벤치 함정
- §6 `bench/` 사용법
- §7 Roblox 안에서 재기

---

## §1 원칙: 측정부터
status: described · 근거: 후보 S-P45, S-P47, M-07(mrow REVIEW:832,856-862), stl-luau-doctor/.claude/conventions.md:147

- **느린 곳을 먼저 찾는다.** `luau --profile[=Hz] f.luau` 는 `profile.out` 을 남긴다(0.742 `--help`). 함수 단위로 어디에 시간이 가는지 본 뒤에야 고칠 곳을 고른다.
- **고치기 전·후를 같은 조건에서 잰다.** 같은 기계, 같은 모드, 같은 입력, 같은 프로세스 안에서 번갈아 잰다.
- **차수(Big-O)만 보고 "훨씬 빠르다"고 쓰지 않는다.** 이 런타임에서는 C 로 내려가는 쪽(해시, `table.sort`, `table.move`, `string.*`)이 상수 배에서 크게 이긴다. 반대로 C 기준선도 이길 수 있다. 실측 예는 `algorithms-and-structures.md`, `strings.md` §2.
- **격리 벤치의 승리가 실제 코드에서 뒤집힐 수 있다.** mrow 는 격리 벤치에서 이긴 변경이 파서 전체에서 8~20% 느려진 사례를 적었다(M-07). 마이크로벤치는 후보를 고르는 데 쓰고, 채택은 실제 경로로 확인한다.

## §2 하네스 규칙
status: verified · last-confirmed: luau 0.734·0.742 · 근거: `bench/lib/bench.luau`, `bench/run.sh`, 후보 S-P45, Q-094, Q-122

`bench/lib/bench.luau` 의 `Bench.run(group, cases, opts)` 가 아래를 강제한다.

| 규칙 | 하는 일 | 왜 |
|---|---|---|
| 워밍업 | 처음 2 라운드를 버린다 | 표 성장, 인라인 캐시, 네이티브 컴파일 뒤의 정상 상태를 잰다 |
| 반복 | 기본 11 라운드(무거운 것 5~9) | 한 번의 값은 잡음이다 |
| 순서 회전 | 라운드마다 케이스 순서를 한 칸씩 돌린다 | 기계 부하의 표류가 한 케이스에만 쌓이지 않는다 |
| GC 통제 | 측정 직전마다 앞 결과를 놓고 `collectgarbage("collect")` | 앞 케이스의 쓰레기와 살아 있는 결과가 뒤 케이스 시간에 섞이지 않는다. GC 비용 자체를 볼 때만 `gc = false` |
| 시간 | `os.clock()` 차이 | CPU 시간이다. 측정 단위가 수 ms 이상이 되게 반복 수를 잡는다 |
| 통계 | **중앙값**으로 비율을 낸다. 최소값도 함께 출력한다 | 원천(stl 문서)은 최소값을 썼다. 중앙값이 외톨이 값에 덜 흔들린다. 할당이 많은 그룹은 §4 처럼 최소값 비율도 본다 |
| 음성 대조군 | 기준 케이스를 `control` 로 한 번 더 잰다 | 같은 코드의 비율이 1.00 에서 벗어난 만큼이 그 그룹의 잡음 바닥이다 |
| 결과 붙잡기 | 케이스 반환값을 전역 칸에 둔다 | 계산이 버려지지 않게 한다. 루프 안 누적값(`s += …`)을 돌려준다 |
| 프로세스 반복 | `run.sh` 가 모드마다 프로세스 3개 | 실행마다 달라지는 해시 배치·GC 시점을 프로세스 사이 범위로 보인다 |

- 메모리는 `Bench.mem` 으로 잰다. n 개를 붙잡은 채 collect 전후의 `collectgarbage("count")` 차이를 n 으로 나눈다.
- GC 잔여를 판정할 때는 KB 보다 **약한 키 추적자에 남은 객체 수**로 본다. KB 는 표 용량 고수위로 수백 KB 흔들린다(Q-122). `collect` 는 여러 번 부른다.
- 테스트 데이터는 결정적 난수(`Bench.rng`)로 만든다.

## §3 모드와 실제 조건
status: verified(CLI) / described(Roblox) · last-confirmed: luau 0.742 · 근거: `optimizer-and-native.md` §1·§2, create.roblox.com luau/comments.md(2026-11-10판), 후보 S-P45, 모순표 claude-doctor .claude/scopes/packs/luau-kb/audit/09 §6-2

| 조건 | 무엇이 다른가 |
|---|---|
| `luau f.luau` | CLI 기본 `-O1`, 인터프리터. **수치 대부분의 원천(stl 0.734)이 이 조건이다** |
| `luau -O2 f.luau` | 인라인, 루프 펼치기, 내장 접기. 파라미터 타입 주석으로 타입 맵을 만든다 |
| `luau -O2 --codegen f.luau` | 불러온 **모든 모듈**을 네이티브로 컴파일한다. Roblox 에서는 `--!native`/`@native` 를 단 것만 네이티브다 |
| Roblox Studio 플레이 테스트 | 문서상 `--!optimize` 기본 1 |
| Roblox 라이브 게임 | 문서상 기본 2. 네이티브는 서버와 Android 클라이언트에서만, 지시어를 단 스크립트만 |

- 셋 다 잰다. 이 스킬의 재측정은 모드 넷(0.734 `-O1`, 0.742 `-O1`/`-O2`/`-O2 --codegen`)이다. 0.734 `-O1` 은 원천 수치와 조건을 맞춘 대조 열이다.
- **같은 파일에 흉내 낸 함수는 `-O2` 에서 인라인되어 공짜가 된다.** 실제 라이브러리는 다른 모듈이라 인라인되지 않는다. 그래서 `bench/lib/arr.luau`·`bench/lib/vfuncs.luau` 처럼 측정 대상을 다른 모듈에 두고, 필드 대입으로 만든다(`optimizer-and-native.md` §3).
- "Roblox 라이브는 `-O2`" 는 공식 문서의 서술이다. 엔진 안에서 직접 재지는 않았다(claude-doctor .claude/scopes/packs/luau-kb/audit/09 모순 2).

## §4 결과 읽기와 잡음 바닥
status: verified · last-confirmed: luau 0.742 · 근거: `bench/results/2026-11-10.tsv`, `bench/RESULTS.md`

- **비율을 먼저 본다.** 절대 ms 는 기계마다 다르다. 이 스킬의 표는 "기준 케이스 대비 배수"이고, 칸은 `프로세스 3개의 중앙값 (최소–최대)` 이다.
- 이번 측정 기계: AMD Ryzen 5 7600 위 4 vCPU 컨테이너, 다른 세션과 공유(load average 5 안팎).
- 이번 측정의 `control` 비율(중앙값): 49 그룹 중 43 그룹이 0.94~1.06 이었다. 벗어난 여섯은 모두 할당이 많은 그룹이다(`tbl-ctor-slots/build` 1.13~1.41, `tbl-queue/pushfront` 1.60~1.78, `tbl-nil-holes/build` 0.734 에서 1.77, `str-build/parse` 1.05~1.11, `algo-basics/union` 0.92~0.94, `tbl-prealloc/n10000` 0.734 에서 0.91).
- 원인은 **GC 단계가 측정 구간에 들어가느냐**다. 이런 그룹은 한 프로세스 안에서도 시간이 두 값으로 갈린다(중앙값은 흔들리고 최소값은 안정). 그래서 `summarize.py --stat min` 으로 최소값 비율을 같이 보고, 그쪽 `control` 이 1.00 근처인지 확인한 뒤 최소값 비율을 쓴다(이번에는 위 여섯 중 `tbl-nil-holes/build` 0.734 만 최소값에서도 1.76 이었다. 그 그룹은 같은 그룹 안 두 방식을 직접 나눈 비율로 적었다).
- 그런 그룹에서는 **±15% 안의 차이를 결론으로 쓰지 않는다.** 그룹별 값은 `bench/RESULTS.md`(중앙값 표와 최소값 표).
- 하네스 개선 이력: 첫 실행은 앞 케이스의 결과를 붙잡은 채 다음 케이스를 쟀다(힙 크기가 섞임). 지금 판은 측정 전에 놓는다. 측정 직전에 같은 케이스를 한 번 더 돌리는 예비 실행도 시험했지만 GC 단계로 인한 갈림을 없애지 못해 넣지 않았다.
- 1.5 배 넘는 차이가 모드 넷에서 같은 방향이면 믿는다. 모드 사이에서 방향이 바뀌면 원인(대개 `-O2` 인라인이나 네이티브)을 찾아 조건을 적는다.

## §5 벤치 함정
status: verified(표시한 행) / described · 근거: 표의 후보 ID

| 함정 | 증상 | 처방 | 근거 |
|---|---|---|---|
| 같은 파일의 지역 함수를 비교 대상에 섞음 | `-O2` 에서 한쪽만 인라인되어 3~6 배 차이가 "생긴다" | 대상 함수를 다른 모듈에 둔다 | verified, `bench/call-closures.luau` upvalue 그룹, S-P26·S-P27 |
| 원소마다 래퍼 클로저로 감싸 부름 | 래퍼 호출 값이 결과를 덮는다 | 루프는 케이스 안에 두고 실제 호출 모양 그대로 쓴다 | S-P45 |
| 할당이 많은 벤치 | GC 시점 때문에 실행마다 2 배까지 흔들린다 | 측정 전 collect, 프로세스 반복, 같은 실행 안의 비율만 비교 | S-P38 |
| 키 이름만 바꾼 비교 | 해시 칸 배치가 바뀌어 ±5% 흔들린다. 같은 필드 읽기가 표마다 1.6 배 다르게 나온 적도 있다(이번 측정 중 관측, 재현 안 됨) | 이름 비교는 결론을 내지 않는다 | S-P25 |
| 같은 키로 split 을 반복 | 그 노드가 뿌리가 되어 O(1) 로 보인다 | 키를 바꿔 가며 | S-P46 |
| require 시간 비교 | 경로가 달라 3 ms 차 | 두 사본을 같은 경로에 번갈아 둔다 | S-P46 |
| "생성 시간 빼기" | 차이가 잡음보다 작아 결론이 안 난다 | 생성과 연산을 따로 잰다 | S-P46 |
| 타이밍 반복과 호출 횟수 세기를 같은 카운터로 | 카운트가 반복 수만큼 불어난다 | 분리한다 | Q-094 |
| mock 위 CLI 비율 | 엔진 호출이 빠져 있다 | "상한"으로 읽는다 | Q-094 |
| 측정 커밋을 안 적음 | 나중에 재현 못 함 | 커밋 sha, 버전, 모드를 결과와 같이 적는다 | Q-094(H-808) |
| 첫 실행의 이상치 | `-O2` 2.07x, codegen 7.56x 같은 값이 한 번 나오고 재현 안 됨 | 프로세스 반복으로 거른다 | stl perf 18절 |

## §6 `bench/` 사용법
status: verified · last-confirmed: luau 0.734·0.742

```bash
cd /code/Projects/claude-doctor/packs/luau-kb
# 전부(프로세스 3 × 모드 4). 결과 TSV 를 덧붙인다
choom -n 1000 -- prlimit --data=3221225472 -- bash bench/run.sh -p 3 -o bench/results/$(date +%F).tsv
# 하나만, 모드를 골라서
choom -n 1000 -- prlimit --data=3221225472 -- bash bench/run.sh -p 1 -m "0.742|-O2 --codegen" -o /tmp/x.tsv bench/mt-index.luau
# 표로
python3 -I bench/summarize.py bench/results/2026-11-10.tsv > /tmp/t.md            # 중앙값 비율
python3 -I bench/summarize.py bench/results/2026-11-10.tsv --stat min > /tmp/m.md # 최소값 비율
```
- 모든 실행은 `choom -n 1000 -- prlimit --data=3221225472 --` 안에서 돈다. 메모리 cgroup 을 여러 세션이 함께 쓰므로 벤치가 먼저 죽게 한다. 셸에서 직접 돌릴 때는 `choom -n 1000 -p $$` 를 먼저 둔다.
- 새 벤치: 파일 머리에 `주장(후보 ID)`, `원 수치(원천 경로와 조건)` 를 적고, 같은 일을 하는 케이스를 한 그룹에 넣는다. 첫 케이스가 기준이다. 결정적인 주장(메모리 배치, 의미)은 `snippets/perf-*.luau` 로 따로 둔다.

## §7 Roblox 안에서 재기
status: described · 원천: claude-doctor .claude/scopes/packs/luau-kb/archive/research/drafts/gaps/native-codegen.md §8, roblox-engine 스킬

- 엔진 API 비용(Instance 생성, 속성 대입, 바인더블 복사, 트윈)은 CLI 로 잴 수 없다. roblox-engine 스킬의 `../../roblox-engine/references/perf.md`(Studio 기준치)와 luau-roblox 스킬의 `../../luau-roblox/references/studio-mcp.md` §6(내장 `rbx-perf-profiling`)을 본다.
- Studio 실행 컨텍스트에 따라 `collectgarbage("collect")` 가 막혀 있다. 할당 부하와 `task.wait` 로 GC 를 진행시키고 약한 표 canary 로 판정한다(`gc-and-memory.md` §5).
- 네이티브 확인은 Script Profiler 의 `<native>` 표시, 코드 크기는 서버 콘솔의 `debug.dumpcodesize()` 다(`optimizer-and-native.md` §6).
