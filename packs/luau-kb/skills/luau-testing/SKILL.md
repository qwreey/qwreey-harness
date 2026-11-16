---
name: luau-testing
description: >-
  Writing and running Luau tests: luau CLI runner (exit codes, assert, pcall), -O1 vs -O2, golden files, mocks,
  time-dependent logic (debounce, timers, virtual clock) and GC. Use when writing specs or a runner, or a test fails
  only under -O2. Check results are luau-verify. 트리거: 테스트 러너 짜기, -O2 에서만 깨짐, 디바운스·타이머 시험.
---
# luau-testing

이 스킬은 "Luau 코드가 **실행해서** 맞는지 어떻게 시험하나"를 다룬다. 사실의 근거는 플러그인 루트의 `snippets/test-*.luau`(그리고 최적화 수준 쪽 `opt-*`, `native-*`)이고, 하네스는 `tools/check_snippets.py` 다. 절마다 `status: verified`(스니펫이 luau 0.734/0.742 에서 재현) 또는 `described`(원천 서술만)가 붙어 있다.

## 먼저 지킬 원칙
1. **기본 러너는 `luau` CLI 다**(결정 D-03). Roblox 에 기대는 부분만 필요한 만큼 mock 으로 바꾸고, Studio 는 mock 이 맞는지 확인할 때만 쓴다.
2. **같은 스위트를 `luau` 와 `luau -O2` 로 두 번 돈다.** `-O1` 테스트로는 인라인 때문에 생기는 실패가 영원히 안 보인다.
3. **에러는 메시지와 정확한 사용자 줄을 같이 단언한다.** 기대 줄은 그 자리에서 `debug.info(1, "l") + 1` 로 잰다(헬퍼로 빼지 않는다).
4. **테스트가 무언가를 잡는다는 증거를 둔다.** 러너 음성 대조군(일부러 실패하는 케이스), 등록 누락 검사, 돌연변이.
5. 게이트는 출력 줄 수가 아니라 **종료 코드**로 판정한다. 실행은 `timeout`·`ulimit -v` 안에서 한다.

## 결정 트리
- **무엇으로 돌리나** → `references/runners.md` §1–3. 프레임워크를 고르려면 §6(Jest Roblox 만 활성, TestEZ·jest-lua 는 새로 쓰지 않음)
- **테스트를 새로 쓴다**
  1. 엔진과 무관한 로직인가? → 순수 스펙. 구조와 단언은 `references/assertions.md` §1–2
  2. Roblox API 를 건드리나? → `references/roblox-boundary.md` §1–3 으로 경계를 긋고, mock 이 틀리기 쉬운 곳은 §4
  3. 에러를 던지는 API 인가? → `references/assertions.md` §3–4 (사용자 줄 단언)
  4. 시간·GC 에 기대나? → `references/gc-and-time.md`
- **테스트가 `-O2`·Studio·`--!native` 에서만 깨진다** → `references/optimize-levels.md` §2–4
- **"0 failed" 인데 불안하다 / 게이트를 믿을 수 있나** → `references/negative-controls.md` §1–3
- **참조 구현과 대조, 무작위 입력, 시드** → `references/negative-controls.md` §4–5, `references/assertions.md` §6
- **다른 저장소는 어떻게 하나** → `references/repo-practices.md`

## 증상 → 파일 라우팅
| 증상 / 질문 | 읽을 곳 |
|---|---|
| `luau` CLI 의 종료 코드, `-a` 인자, `arg` 없음, require 반환 개수, `--coverage` | `references/runners.md` §2 |
| 테스트 엔트리를 `init.luau` 로 지었더니 require 가 엉뚱한 곳을 본다 | `references/runners.md` §3 |
| `io`·`fs` 없이 픽스처·골든 파일 비교 | `references/runners.md` §4 |
| lute test, lune, Jest Roblox, jest-lua, TestEZ, run-in-roblox, Open Cloud 실행 | `references/runners.md` §5–7 |
| `pcall` 에러 값에 `파일:줄:` 이 붙는지, `error(tbl)`·`assert(nil, tbl)` | `references/assertions.md` §2 |
| 에러 위치 단언이 `-O2` 에서 -1 이나 위치 없음 | `references/assertions.md` §3, `references/optimize-levels.md` §2 |
| blame 단언이 파일 이름만 본다 | `references/assertions.md` §4 |
| `eq<T>(a, b)` 헬퍼가 타입이 달라도 에러가 없다 / `pcall` 의 err 가 any | `references/assertions.md` §5 |
| 경계 케이스, 데이터 고르기, 정확값 단언 | `references/assertions.md` §6 |
| `-O1` 은 통과, `-O2` 는 실패 / traceback 의 함수 이름이 사라짐 | `references/optimize-levels.md` §1–2 |
| `--!optimize`, `--!native`, `@native` 가 CLI `-O` 를 이기는가 | `references/optimize-levels.md` §3 |
| `getfenv` 로 mock 을 주입한 스펙이 `-O2` 를 재현하나 | `references/optimize-levels.md` §4 |
| 러너가 케이스를 정말 돌렸나, 등록 누락, 돌연변이 검사 | `references/negative-controls.md` §1–3 |
| 차등 시험, 퍼즈, 퍼저 검증, 축소, 시드 | `references/negative-controls.md` §4–5 |
| CLI 에 `Vector3`·`Enum`·`task` 가 없다 / 모듈 로드에서 죽는다 | `references/roblox-boundary.md` §3 |
| mock 과 엔진 결과가 다르다(같은 값 발화, 리스너 에러, Connect) | `references/roblox-boundary.md` §4 |
| Deferred 시그널을 CLI 에서 흉내 내기 | `references/roblox-boundary.md` §5 |
| 가짜 Instance 로 `typeof(x) == "Instance"` 분기를 못 탄다 | `references/roblox-boundary.md` §6 |
| weak 표 정리·누수 검증, KB 가 흔들림, `collectgarbage` 가 Unknown global | `references/gc-and-time.md` §1–2 |
| 디바운스·스로틀·타이머 시험, `task.wait` 지터 | `references/gc-and-time.md` §3 |
| Roblox 에서 `collectgarbage("collect")` 가 거부됨 | `references/gc-and-time.md` §4 |
| quad, stl-luau, table-sim, devplorer, tbox, moonwave, rbvm 의 테스트 방식 | `references/repo-practices.md` |
| mock 작성·주입 패턴, Studio MCP 로 확인하는 절차 | luau-roblox 스킬 `references/mocks.md`, `references/studio-mcp.md` |
| 타입 진단을 테스트로 고정(expect-error, bug-present) | luau-verify 스킬 `references/snippet-markers.md` |
| 최적화 수준·인라인 규칙·native 성능 자체 | luau-perf 스킬 |

## 답할 때
- 절의 `status` 를 함께 말한다. `described` 는 "원천 서술, 미재현"이라고 밝힌다.
- 버전과 최적화 수준을 붙인다(예: "luau 0.742, `-O2` 에서만").
- mock·심의 결과를 엔진 사실로 말하지 않는다. 엔진 쪽 사실은 roblox-engine·roblox-net·roblox-world 스킬의 Studio 실측을 인용한다.
- 새 사실은 `snippets/test-*.luau` 에 최소 재현과 하네스 머리(`--@run`, `--@run-opt=0,2`, `--@run-with … => ok|fail; out~…`)를 먼저 넣고 `python3 -I tools/check_snippets.py --luau 0.734,0.742 snippets/test-*.luau` 로 돌린다.
