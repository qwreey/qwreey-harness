---
title: "코루틴과 스레드의 순수 의미론 (엔진 무관)"
description: "엔진 무관 코루틴 의미론: resume·wrap 이 에러를 (false, err) 로 삼키는 길, 죽은·실행 중 코루틴, table.sort 비교자·메타메서드·C 경계와 CLI 메인 스레드에서의 yield 실패, thread-local·문맥 전파 없음"
keywords:
  - "코루틴 에러 사라짐"
  - "coroutine error swallowed"
  - "coroutine.resume 에러"
  - "coroutine.wrap 에러"
  - "attempt to yield across C-call boundary"
  - "cannot resume dead coroutine"
  - "cannot resume running coroutine"
  - "C stack overflow"
  - "coroutine.isyieldable"
  - "CLI 메인 스레드 yield"
  - "thread-local"
  - "문맥 전파"
  - "context propagation"
  - "암묵 문맥 누출"
kind: reference
category: luau/runtime/coroutines
tags: [silent, cli]
last_verified: 2026-11-10
last_confirmed:
  - luau 0.734
  - luau 0.742
---
# coroutines — 코루틴과 스레드의 순수 의미론 (엔진 무관)

## 이 파일이 답하는 질문
- Q1 `coroutine.resume` 으로 돌린 스레드의 에러는 어디로 가나? 죽은·실행 중 코루틴을 resume 하면?
- Q2 yield 할 수 없는 자리(`table.sort` 비교자, 메타메서드, C 경계)에서 기다리면? luau CLI 최상위에서는?
- Q3 thread-local 이나 비동기 문맥 전파가 있나? 암묵 문맥은 왜 새나?

## 목차
- §1 코루틴 에러가 사라지는 길
- §2 yield 할 수 없는 문맥
- §3 문맥 전파가 없다

Roblox `task` 라이브러리(spawn·defer·delay·cancel 의 계약, defer 순서, 협력 스케줄링의 경쟁, 시한, 시계)는 roblox-engine `tasks-and-threads.md` 가 정본이다. 코루틴 **비용**은 luau-perf `calls-and-closures.md`, `resume` 의 에러 삼킴을 스타일 규칙으로 막는 법은 luau-style `pitfalls.md`, 가상 시계 시험은 luau-testing `gc-and-time.md` §3.

---

## §1 코루틴 에러가 사라지는 길
status: verified (resume 의 반환·죽은 코루틴·`error(err, 0)` 전파) / described (나머지) · last-confirmed: luau 0.734, 0.742 (`snippets/style-coroutine-resume-swallows.luau`), Studio 0.742(rbvm, `coroutine.wrap`) · 근거: `snippets/style-coroutine-resume-swallows.luau`; rbvm `.claude/review/2026-10-05-code-review.md:168-185`, `.claude/review/2026-10-05-repro/B3_wait_error_swallowed.luau`, rbvm `.claude/design/engine-behavior.md:34`; quad `.claude/base/ref-plan.md:314-325,424-434`, `.claude/archive/v2-initial-implementation/m2-implementation-round11.md:122-128` · 후보: R-10, Q-066

- `coroutine.resume` 은 던지지 않고 `(false, err)` 를 돌려준다. 결과를 안 보면 에러가 **아무 출력 없이 사라진다.** 전파하려면 `if not ok then error(err, 0) end`.
- 직접 `coroutine.resume(th)` 로 재개한 스레드는 다음 yield 까지 재개한 쪽 스택에서 돈다. 그 안의 에러도 위처럼 삼켜진다. Roblox 에서는 엔진이 재개하게 `task.spawn(th, ...)` 를 쓰거나(roblox-engine `tasks-and-threads.md` §1), 결과를 보고 `warn(debug.traceback(th, err))` 한다. "task.spawn 이면 엔진이 Output 에 보고한다" 는 Studio 확인이 필요하다(roblox-engine `tasks-and-threads.md` 미판정).
- 죽은 코루틴 resume 은 `(false, "cannot resume dead coroutine")`. 실행 중인 코루틴을 자기 안에서 resume 하면 위치 없는 raw `cannot resume running coroutine`.
- `pcall(coroutine.wrap(function() error("boom") end))` 는 엔진에서 `false, "<위치>: boom"`(위치가 한 번만 붙음)이었다.

mock 흉내: rbvm 의 `coroutine.wrap` 은 nil 을 돌려줬다(B4). 고치면 위치가 두 번 붙었다(B5).

## §2 yield 할 수 없는 문맥
status: described · last-confirmed: luau CLI(rbvm, stl, quad 재현) · 근거: rbvm `.claude/review/2026-10-05-code-review.md:286-295`; stl-luau-doctor `.claude/papers/01-fut.md:11-16,25-32`; quad `.claude/archive/v2-initial-implementation/m8-implementation-round18.md:17` · 후보: R-13, S-132, S-133, Q-067

- `table.sort` 비교자, 메타메서드, C 경계에서 `Wait` 류를 부르면 `attempt to yield across C-call boundary`. **등록을 먼저 하고 그다음 yield 하는 구조**면 yield 가 실패해도 등록(연결·워커)이 남아 나중에 엉뚱한 값을 주입한다. 등록 전에 `coroutine.isyieldable()` 을 확인한다.
- luau CLI 메인 스레드는 `coroutine.isyieldable()` 이 true 인데, 거기서 yield 하면 호스트가 거부하고 `pcall` 로도 못 잡는 크래시가 난다. CLI 테스트에서 기다리는 코드는 직접 만든 코루틴 안에서 돌린다.
- 즉시 실행 스케줄러가 콜백 사슬을 재귀 resume 하면 약 198단에서 `C stack overflow`. 큐(트램펄린)로 펴고 상한을 둔다. Lua 호출 깊이 한도(약 20000)와는 다른 한도다.

mock 흉내: 해당 없음(언어·호스트 동작). Roblox 엔진의 C 경계 목록은 다를 수 있다.

## §3 문맥 전파가 없다
status: described · 근거: devplorer `.claude/review/2026-10-20-recorder-depth.md:30-42`; quad `.claude/archive/context-rejected.md:28-36` · 후보: D-R09, Q-069

- Luau 에는 thread-local 도 비동기 문맥 전파도 없다. 코루틴 키 push-pop 이나 전역 플래그로 만든 암묵 문맥은 yield 중 끼어든 코루틴에 새고, `task.spawn` 한 새 코루틴은 문맥을 물려받지 못한다.
- 문맥이 필요하면 인자로 명시적으로 넘긴다. 코루틴을 키로 한 표로 흉내 낼 때는 새 코루틴(spawn·wrap)마다 문맥을 직접 복사해야 하고, yield 사이에 다른 코루틴이 같은 전역 플래그를 읽는 것을 막을 수 없다.

mock 흉내: 해당 없음(언어 동작).
