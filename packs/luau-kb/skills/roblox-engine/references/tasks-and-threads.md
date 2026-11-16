---
title: "task 라이브러리, 협력 스케줄링의 경쟁, 시한, 시계"
description: "task 라이브러리 계약(spawn 이 같은 thread 반환, 죽은 스레드 cancel no-op, delay 인자 순서), defer 중첩 순서, RemoteFunction 동시 요청의 TOCTOU 경쟁, InvokeClient·WaitForChild 무한 대기와 시한, os.clock 대 GetServerTimeNow"
keywords:
  - "task.defer 와 task.spawn 차이"
  - "task.spawn 반환값"
  - "task.defer 순서"
  - "task.cancel 죽은 스레드"
  - "task.delay 인자 순서"
  - "invalid argument #1 to 'spawn' (function or thread expected)"
  - "협력 스케줄링 경쟁"
  - "TOCTOU"
  - "RemoteFunction 동시 요청"
  - "쿨다운 뚫림"
  - "한 번만 초기화"
  - "InvokeClient 무한 대기"
  - "무한 대기 시한"
  - "os.clock"
  - "GetServerTimeNow 역행"
  - "시계 주입"
kind: reference
category: roblox/tasks
tags: [studio, correction]
last_verified: 2026-11-10
---
# tasks-and-threads — task 라이브러리, 협력 스케줄링의 경쟁, 시한, 시계

코루틴의 **순수 의미론**(resume 의 에러 삼킴, yield 할 수 없는 문맥, 문맥 전파 없음)은 엔진과 무관해서 luau-runtime `coroutines.md` 가 정본이다. 이 파일은 Roblox `task` 라이브러리와 엔진 스케줄러 위의 동작을 둔다.

## 이 파일이 답하는 질문
- Q1 `task.spawn`/`defer`/`delay`/`cancel` 의 반환값과 에러 동작은? 죽은 스레드를 cancel 하면?
- Q2 `task.defer` 안에서 다시 `task.defer` 하면 순서는?
- Q3·Q4 `coroutine.resume` 의 에러, yield 할 수 없는 자리 → luau-runtime `coroutines.md`
- Q5 Roblox 는 협력 스케줄링인데 왜 경쟁(TOCTOU)이 생기나? RemoteFunction 은?
- Q6 끝나지 않는 대기에 시한을 거는 법은?
- Q7 어떤 시계를 써야 하나? 시간 의존 로직은 어떻게 테스트하나?

## 목차
- §1 task 함수의 계약
- §2 defer 의 홉 수와 순서
- §3 코루틴 에러가 사라지는 길 → luau-runtime `coroutines.md` §1
- §4 yield 할 수 없는 문맥 → luau-runtime `coroutines.md` §2
- §5 협력 스케줄링에서의 경쟁
- §6 끝나지 않는 대기와 시한
- §7 시계와 시간 테스트
- 모순 판정 · 정정 · 미판정

조건: Studio 원천 실측은 Deferred 플레이스다(rbvm 0.742 2026-10-13, quad 2026-09-08). task 재개 자체가 Deferred 신호의 재개 지점이다(`signals-and-events.md` §2). mock 약어는 `signals-and-events.md` §0.

---

## §1 task 함수의 계약
status: described · last-confirmed: Studio 0.742.0.7421053(rbvm, 2026-10-13, Edit, Deferred), quad 2026-09-08(Studio) · 근거: rbvm `.claude/design/engine-behavior.md:31-33`, rbvm `.claude/review/2026-10-05-code-review.md:320-326`; quad `.claude/audit/sugar-studio-2026-09-08.md:16-23`, `.claude/base/debounce-throttle-plan.md:670-673,706-710,809-819`; 타입: `snippets/rbx-types-engine-calls.luau` · 후보: R-08, Q-064, Q-065, M-05

- `task.spawn(th)` 은 넘긴 thread 를 **그대로** 돌려준다(`rawequal` true). 래퍼가 원래 thread 를 돌려주지 않으면 `task.cancel(task.spawn(th))` 가 먹지 않는다.
- `task.spawn(123)` 은 즉시 에러 `invalid argument #1 to 'spawn' (function or thread expected)`.
- `task.delay` 로 만든 스레드는 발화 뒤 `coroutine.status == "dead"` 다. **죽은 스레드의 `task.cancel` 은 에러 없는 no-op** 이다. 상태 가드가 필요 없다.
- `task.delay(시간, fn, ...)` — **시간이 첫 인자다**(JS `setTimeout` 과 반대). 순서를 바꾸면 타입 검사가 잡는다(verified, luau-lsp 1.70.1·1.69.0).
- `task.delay` 는 호출마다 스레드를 만든다. Heartbeat 마다 cancel + 재예약하면 스레드가 계속 생기고 버려진다. 대안은 마감 시각을 `os.clock()` 으로 다시 확인하는 게으른 타이머다(미벤치). 대기 중 콜백은 업밸류를 강하게 잡는다.
- `task.wait` 해상도 때문에 타이머에 ±0.02초(프레임 단위) 지터가 있다.

mock 흉내: rbvm 래퍼는 다른 thread 를 돌려주고 `spawn(123)` 을 조용히 통과시켰다(B20). quad runshim 의 `task.wait(t)` 는 즉시 `t` 를 돌려준다(luau-roblox `mocks.md` §4). 죽은 스레드 cancel 을 "에러"로 만든 mock 헤더가 있었다(정정 표).

## §2 defer 의 홉 수와 순서
status: described (가짜 스케줄러 재현, Studio 미확인) · 근거: rbvm `.claude/review/2026-10-05-code-review.md:313-318`; quad runshim `flush()`(luau-roblox `mocks.md` §4) · 후보: R-09, Q-079

- `task.defer` 콜백 안에서 다시 `task.defer` 하는 래퍼는 홉이 둘이다. `defer(A); defer(B); 래퍼(C); defer(D)` 가 **A B D C** 순서가 된다. 돌려받은 thread 를 cancel 해도 안쪽 defer 가 이미 예약돼 있어 C 가 돈다.
- 같은 시각 항목을 `table.sort` 로 꺼내는 가상 큐는 5개부터 FIFO 를 잃는다(luau-roblox `mocks.md` §4). 엔진의 같은 프레임 defer 순서는 아무도 재지 않았다.

mock 흉내: 가상 스케줄러가 엔진과 같은지는 미확인이다. 순서에 기대는 코드는 Studio 로 확인한다.

## §3 코루틴 에러가 사라지는 길 → luau-runtime `coroutines.md` §1
- 언어 동작이라 옮겼다(2026-11-10). 요지: `coroutine.resume` 은 `(false, err)` 를 돌려주고 던지지 않는다. 엔진이 재개하게 하려면 `task.spawn(th, ...)` 를 쓴다.
- Roblox 고유로 남은 것: `task.spawn` 한 스레드의 에러를 엔진이 Output 에 보고하는지는 Studio 미확인이다(미판정). `pcall(coroutine.wrap(f))` 는 엔진에서 `false, "<위치>: boom"`(위치 한 번)이었다(rbvm, Studio 0.742).

## §4 yield 할 수 없는 문맥 → luau-runtime `coroutines.md` §2
- 언어·호스트 동작이라 옮겼다(2026-11-10). 요지: `table.sort` 비교자·메타메서드·C 경계에서 `Wait` 류를 부르면 `attempt to yield across C-call boundary` 다. 등록 전에 `coroutine.isyieldable()` 을 본다. Roblox 엔진의 C 경계 목록은 CLI 와 다를 수 있다(미측정).

## §5 협력 스케줄링에서의 경쟁
status: described · last-confirmed: devplorer 2026-10-20(Studio Play 에서 수정 확인), quad 서술 · 근거: devplorer `.claude/review/2026-10-20-actions-security.md:36-43,159`, `.claude/review/2026-10-20-recorder-depth.md:30-42`, `.claude/review/2026-10-21-ancestry.md:56-60`, `.claude/review/2026-10-19-server-security.md:98-119`; quad `.claude/qa-request/post-implementation-review-round13.md:224`, `.claude/archive/context-rejected.md:28-36` · 후보: D-R08, D-R09, Q-068, Q-069

- Roblox 스크립트는 협력 스케줄링이라 **양보 없는 구간에는 다른 스레드가 끼지 못한다.** 반대로 양보하는 호출(DataStore, `InvokeClient`, 사용자 후크, `task.wait`) 사이에는 끼어든다.
- **RemoteFunction 호출은 호출마다 별도 스레드다.** 확인과 설정 사이에 양보가 있으면 동시 요청이 모두 확인을 통과해 쿨다운이 뚫린다. 확인과 예약은 양보 없는 구간에서 하고, 실패하면 "내가 넣은 값일 때만" 되돌린다.
- 권한처럼 양보 사이에 바뀔 수 있는 것은 **효과 직전에 다시 확인**한다(TOCTOU).
- "한 번만" 초기화 함수가 yield 하고 완료 표시를 성공 뒤에 세우면, 기다리는 사이 두 번째 호출이 같은 초기화를 다른 스레드에서 한 번 더 돈다. 진행 중 표시를 먼저 세우고 대기자를 모은다.
- 암묵 문맥(thread-local 흉내)은 yield 중 끼어든 코루틴에 샌다 → luau-runtime `coroutines.md` §3.

mock 흉내: 동기 mock 은 양보 지점이 없어 경쟁이 재현되지 않는다(**아니오**). 경쟁 테스트는 가짜 스케줄러로 양보 지점을 명시적으로 끼워 넣거나 Studio 로 한다.

## §6 끝나지 않는 대기와 시한
status: described · 근거: devplorer `.claude/review/2026-10-20-interpreter.md:56-67,173-174`, `.claude/review/2026-10-19-client-code.md:46-53,186`, `.claude/review/2026-10-19-server-security.md:149-160,353-354`, `.claude/review/2026-10-19-server-logs-remote.md:125-136` · 후보: D-R21, D-R42, D-R10

- 시한 없이 영원히 기다릴 수 있는 것: `InvokeServer`, 시한 없는 `WaitForChild`, `Event:Wait()`, OnInvoke 없는 `BindableFunction:Invoke`, 서버의 `InvokeClient`(클라이언트가 답하지 않으면 서버 스레드를 붙잡는다).
- 처방: 본문을 자기 스레드에서 돌리고 `task.delay` 경쟁으로 시한을 건다. 시한에 `task.cancel` 한다. `WaitForChild` 는 timeout 인자를 준다(시간이 지나면 nil, `instance-api.md` §1).
- 시한이 지나도 이미 spawn 한 스레드는 남을 수 있으므로 **동시 호출 수 상한**을 둔다. `task.cancel` 이 엔진 호출(InvokeClient 등) 안에서 멈춘 스레드를 끊는지는 미실측이다.
- `InvokeClient` 는 서버 쪽에서 쓰지 않는 편이 안전하다(악성 클라이언트가 답하지 않을 수 있다). 원격 쪽 규칙은 roblox-net `remotes-and-replication.md`.

mock 흉내: 해당 없음.

## §7 시계와 시간 테스트
status: described · 근거: quad `.claude/base/debounce-throttle-plan.md:45-47,622-626,784-805`, `.claude/audit/sugar-studio-2026-09-08.md:23`, `.claude/audit/round13-e54-debounce-fuzz/README.md:1`; devplorer `.claude/review/2026-10-19-server-security.md:363-365`, `.claude/review/2026-10-20-recorder-depth.md:83-85`; stl-luau-doctor `.claude/papers/01-fut.md:45-82`; table-sim `<비공개>` · 후보: Q-070, D-R54, Q-121, S-134

- `os.clock()` 은 고정밀 **단조** 시계지만 기준점이 없다. 차이로만 쓰고 `os.time` 과 섞지 않는다.
- `workspace:GetServerTimeNow()` 는 보정 때문에 **역행하거나 크게 뛸 수 있다.** 간격 측정에는 `os.clock()` 을 쓴다.
- 순수 `luau` CLI 에는 `task` 도 이벤트 루프도 없다. 시간 의존 로직(Debounce, Throttle, 타이머)은 **시계와 스케줄러를 주입**하고 가상 시계로 결정적으로 시험한다(quad E54: 8만 시드 차등 0). Studio 에서는 시나리오가 정본과 맞는지만 본다(실기기 지터 ±0.02초).
- Promise 류 라이브러리는 스케줄러를 주입받는다(기본 즉시, Roblox 에서는 `task.defer`). 거절을 `pcall` 로 처리하면 스택이 사라지고 `xpcall` 이 보존한다.
- 주입 패턴은 luau-roblox `mocks.md` §2.

mock 흉내: 가상 시계가 곧 mock 이다. 프레임 지터와 재개 지점은 흉내 내지 않는다.

---

## 모순 판정

| # | 내용 | 판정 |
|---|---|---|
| claude-doctor .claude/scopes/packs/luau-kb/audit/08 M-05 | 죽은 스레드 `task.cancel`: mock 헤더 "에러" 대 Studio "no-op" | **판정**: Studio 실측(quad 2026-09-08, rbvm 2026-10-13 둘 다 no-op)이 맞다. mock 헤더가 틀렸다 |

## 정정

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| quad `.claude/archive/post-implementation-review/post-implementation-review-round9.md:30`(mock 헤더 인용) | 죽은 스레드에 `task.cancel` 은 에러 | 에러 없는 no-op | quad sugar-studio-2026-09-08:16-23, rbvm engine-behavior:33 |
| quad `.claude/base/ref-plan.md`(옛 서술, claude-doctor .claude/scopes/packs/luau-kb/audit/08 M-14) | `coroutine.resume` 에러는 나중에 난다 | `(false, err)` 를 돌려주고 삼킨다 | quad H-170 실측 |

## 미판정
- **같은 프레임 `task.defer` 여러 개의 엔진 순서와 R-09 의 홉 순서.** 절차: Edit 에서 `execute_luau` 로 `defer(A); defer(B); defer(function() defer(C) end); defer(D)` 를 걸고 `_G.order` 에 기록, 다음 호출에서 읽는다. 40개로 늘려 FIFO 인지 본다.
- **`task.spawn` 한 스레드의 에러를 엔진이 Output 에 보고하는가.** 절차: `task.spawn(function() error("x") end)` 뒤 `get_console_output` 으로 확인한다(읽기 도구).
