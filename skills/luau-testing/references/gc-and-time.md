# gc-and-time — GC 프로브와 시간 의존 로직 시험

## 이 파일이 답하는 질문
- Q1 weak 표가 정리되는지, 누수가 없는지를 테스트로 어떻게 보이나?
- Q2 GC 측정이 KB 로는 왜 흔들리나? 무엇으로 판정하나?
- Q3 "수거됐다/안 됐다" 프로브가 스스로 결론을 망치는 함정은?
- Q4 Roblox 에서도 `collectgarbage("collect")` 를 쓸 수 있나?
- Q5 디바운스·스로틀·타이머처럼 시간에 기대는 로직은 어떻게 결정적으로 시험하나?

## 목차
- §1 luau CLI 의 GC 프로브: 객체 수로 판정
- §2 프로브 함정
- §3 가상 시계
- §4 Roblox 쪽 차이

GC·weak 표의 **언어 사실**(ephemeron 이 없다 등)과 메모리 비용은 luau-perf·luau-style 스킬 소관이다. 이 파일은 측정·시험 방법만 다룬다.

---

## §1 luau CLI 의 GC 프로브: 객체 수로 판정
status: verified · last-confirmed: luau 0.742 (0.734 동일, `-O2` 같음) · 근거: `snippets/test-gc-weak-probe.luau`, `quad/.claude/audit/round13-e42-gc-sweep/README.md:10-13`, 후보 Q-122·R-48

- `luau` CLI 에는 `collectgarbage` 가 있고 `"collect"` 로 전체 수거를 할 수 있다. 단 `luau-analyze` 는 이 이름을 모른다("Unknown global 'collectgarbage'"). `(_G :: any).collectgarbage` 로 꺼낸다(quad `spec.errorutil.luau:18-19` 와 같은 방식).
- `fullgc()`: `collect` 를 최소 3회, `count` 변화가 0.5 KB 미만이 될 때까지(최대 12회) 돈다. 한 번으로는 수렴하지 않는 경우가 있다.
- **판정은 KB 가 아니라 객체 수**: 대상 객체를 weak-key 추적자(`setmetatable({}, { __mode = "k" })`)에 넣고, 수거 뒤 남은 키 수를 센다. KB 증분은 weak 표·해시 용량의 고수위 때문에 회차마다 ±수백 KB 흔들렸다(원천 실측: 같은 1000개 생성이 +121/+1/−63/+65 KB).
- N=0 기준선과 N 을 같이 재고, 여러 회차에 걸쳐 누적 KB 가 **단조 증가**하는지만 KB 신호로 쓴다.
- 결과는 "순수 Luau 수준"으로 표시한다. Roblox GC 와 같다는 보장이 없다.

## §2 프로브 함정
status: verified (2) / described (1, 3) · 근거: `snippets/test-gc-weak-probe.luau`, `quad/.claude/audit/tween-completed-2026-09-21/REPORT.md:25-31,43-44`, `quad/.claude/audit/round13-e42-gc-sweep/README.md:92-93`, 후보 Q-123·Q-005

1. **포획 변수를 지워 "수거됐다"를 보이려는 실수**: 클로저가 잡은 바로 그 업밸류를 `nil` 로 지우면 클로저가 더는 대상을 잡지 않아, 원래 묻던 "클로저가 잡고 있어도 수거되나"의 답이 무효가 된다. 값 클로저는 키를 **따로 복사한** 업밸류로 잡게 하고, 원래 변수만 놓는다. 원천에서 탐사자 판정 둘이 이 이유로 무효 처리됐다.
2. **하네스가 대상을 쥠**: 로그 표·결과 표가 대상을 강하게 담으면 잔존으로 보인다. 스니펫이 로그 표에 넣은 객체는 남고, 로그를 비우면 수거되는 것을 보인다. 기록에는 객체 대신 이름·번호를 담는다.
3. **클로저 캐시**: 업밸류가 반복마다 바뀌지 않는 클로저(`function() end` 등)는 반복마다 같은 객체일 수 있다. "1개 남음"이 누수가 아니라 캐시된 클로저 하나일 수 있다.
- 측정 함수의 지역 변수가 시나리오 객체를 붙잡지 않게, 시나리오 생성은 별도 함수로 뺀다(quad `perf-studio-2026-10-22/REPORT.md:12-17`, described).

## §3 가상 시계
status: verified · last-confirmed: luau 0.742 (0.734 동일, `-O2` 같음) · 근거: `snippets/test-virtual-clock.luau`, `quad/.claude/audit/sugar-studio-2026-09-08.md:23`, `quad/.claude/base/debounce-throttle-plan.md:45-47`, 후보 Q-121·Q-070

- 순수 `luau` CLI 에는 `task` 도 이벤트 루프도 없다. 실제 시간을 기다리는 테스트는 만들 수 없고, 만들 수 있더라도(lune·lute 의 `task`) 느리고 비결정적이다.
- 시간에 기대는 코드는 **시계(`now`)와 예약 함수(`delay`)를 주입받게** 짠다. 테스트는 가상 시계를 넘기고 `advance(dt)` 로 시간을 옮기며, 그 사이에 예약된 콜백을 시각 순(같은 시각이면 예약 순)으로 돌린다.
- `os.clock()` 은 기준점 없는 고정밀 카운터라 차이로만 쓴다. `os.time()` 과 섞지 않는다(Q-070, described).
- 실기기에서는 시나리오가 정본(가상 시계 결과)과 맞는지만 확인한다. 원천은 디바운스를 가상 시계로 8만 시드 차등 시험해 차이 0 을 확인했고, 실기기 `task.wait` 는 ±0.02초 지터를 보였다(described).

## §4 Roblox 쪽 차이
status: described · 근거: `quad/.claude/audit/tween-completed-2026-09-21/infinite-tween-probe.md:10-12`, `quad/.claude/audit/spike10-full-run-2026-09-01.md:12-14`, 후보 Q-011

- Roblox 의 일부 실행 컨텍스트(Studio MCP 실행 스레드 등)에서는 `collectgarbage` 가 `"count"` 만 받고 `"collect"` 는 거부한다("use gcinfo() instead"). 일반 스크립트에서도 막혀 있다는 기록이 있으나 컨텍스트별 범위는 재확인이 필요하다.
- 엔진 안에서 GC 를 압박하려면 할당을 일으킨다: `table.create(5000)` × 20 할당과 `task.wait(0.05)` 를 에포크마다 반복하고, weak 표 canary 가 비는지로 판정한다(원천 실측 2~3 에포크, 1초 미만).
- 엔진의 GC 는 할당이 있어야 진행한다. 유휴 상태에서는 쓰레기가 오래 남을 수 있다(quad `perf-studio-2026-10-22/REPORT.md:12-17`).
- Studio 에서 확인하는 절차는 roblox-luau 스킬 `../../roblox-luau/references/studio-mcp.md`.
