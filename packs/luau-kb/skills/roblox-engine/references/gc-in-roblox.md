---
title: "Roblox 안에서 GC 를 관찰하기, Instance·연결이 얽힌 수거"
description: "Roblox 샌드박스의 collectgarbage 는 count 만 받으므로 할당 압박+프레임 넘기기로 수거를 관찰하는 법, 유휴 Studio 메모리가 안 줄어드는 이유, Instance·연결이 얽힌 수거의 정본 링크"
keywords:
  - "collectgarbage(\"collect\") 안 됨"
  - "use gcinfo() instead"
  - "gcinfo"
  - "collectgarbage(\"count\")"
  - "Roblox 수거 관찰"
  - "할당 압박"
  - "weak 표 canary"
  - "GC 에포크"
  - "Studio 메모리 안 줄어듦"
  - "누수 판정 Studio"
kind: reference
category: roblox/gc
tags: [studio, correction]
last_verified: 2026-11-10
---
# gc-in-roblox — Roblox 안에서 GC 를 관찰하기, Instance·연결이 얽힌 수거

## 이 파일이 답하는 질문
- Q1 Roblox 에서는 `collectgarbage("collect")` 를 못 쓴다. 수거가 됐는지 어떻게 보나?
- Q2 Studio 에서 메모리가 줄지 않는다. 누수인가?
- Q3 Instance 를 weak 키로 쓴 표, `Connect` 로 건 클로저는 수거에 어떻게 얽히나?

## 목차
- §1 수거 관찰: 할당 압박 + 프레임 넘기기
- §2 할당이 없으면 GC 도 멈춘다 (Studio 실례)
- §3 Instance·연결이 얽힌 수거 (요지와 링크)
- 정정

약한 표의 **의미론**(ephemeron 없음, `__mode`, 누수 판정과 프로브 함정)은 Roblox 와 무관해서 luau-runtime `gc-and-weak-tables.md` 가 정본이다. 이 파일은 엔진 위에서만 성립하는 관찰만 둔다. 누수 시험 하네스는 luau-testing `gc-and-time.md`, 비용은 luau-perf `gc-and-memory.md`.

---

## §1 수거 관찰: 할당 압박 + 프레임 넘기기
status: described · last-confirmed: 문서 `reference/engine/globals/LuaGlobals.yaml` collectgarbage(creator-docs ccc2b01d9bf8, STUDIO_VERSION 0.746.0.7461269, `roblox_docs.py api LuaGlobals.collectgarbage` 로 2026-11-10 재확인); quad 2026-09-01·09-08·09-21 Studio, rbvm 0.742(2026-10-13, Deferred) · 근거: 문서 "Roblox's Luau sandbox only allows the `count` option"; quad `.claude/audit/tween-completed-2026-09-21/infinite-tween-probe.md:10-12`, `.claude/audit/spike10-full-run-2026-09-01.md:12-14`, `.claude/audit/round8-studio-2026-09-08.md:11`; rbvm `.claude/design/engine-behavior.md:47` · 후보: Q-011, R-18

- Roblox 의 `collectgarbage` 는 `"count"` 만 받는다(문서, `Deprecated` 태그, `gcinfo()` 를 권한다). Studio MCP 실행 스레드에서도 `"collect"` 는 `use gcinfo() instead` 로 거부됐다.
- 관찰법: **할당 압박 + 프레임 넘기기.** 에포크마다 `table.create(5000)` 을 20번 할당하고 `task.wait(0.05)` 한다. weak 표 canary 가 비면 수거된 것이다. 실측상 2~3 에포크(1초 미만)에 비었다. rbvm 은 Instance 20개가 5프레임 만에 수거됐다.
- 결과는 "N 에포크 안에 수거됨/안 됨"으로 적는다. 대조군(수거돼야 하는 것)이 같은 에포크 안에 수거되는지 같이 본다. tween-completed 실측은 대조군 8 에포크, 누수 후보 150 에포크 잔존으로 판정했다.
- 프로브를 짤 때의 함정(포획 변수를 nil 로 지움, 하네스가 대상을 쥠, 클로저 캐시)은 엔진과 무관하다 → luau-runtime `gc-and-weak-tables.md` §5.

mock 흉내: 해당 없음. CLI 에서는 `collectgarbage("collect")` 로 바로 본다.

## §2 할당이 없으면 GC 도 멈춘다 (Studio 실례)
status: described · last-confirmed: quad Studio 2026-10-22(Play) · 근거: quad `.claude/audit/perf-studio-2026-10-22/REPORT.md:12-17` · 후보: Q-003, S-P51

- 유휴 Studio 클라이언트의 `collectgarbage("count")` 가 12초 동안 56MB 그대로였고, 짧게 사는 쓰레기를 할당하자 약 10MB 로 돌아왔다.
- 그래서 "가만히 두었더니 안 줄어든다"는 누수 증거가 아니다. 언어 규칙(GC 는 할당이 민다)은 luau-runtime `gc-and-weak-tables.md` §4.
- CLI 와 Roblox 의 수거 **시점**은 다르다. 시점에 기대는 버그는 CLI 에서 재현되지 않을 수 있다(luau-roblox `env-dependence.md` §2 마지막 행).

## §3 Instance·연결이 얽힌 수거 (요지와 링크)
status: described · 근거: 아래 링크한 절의 근거를 따른다

| 상황 | 요지 | 정본 |
|---|---|---|
| Instance 를 키로 쓴 weak 표의 항목이 Instance 가 살아 있는데 사라진다 | Lua 참조가 다 사라지면 userdata 가 수거되고 다시 얻으면 다른 userdata 다 | `instance-lifecycle.md` §4 |
| `Connect` 한 클로저가 Instance·홀더를 잡는다 | 엔진이 연결을 쥐므로 그 사슬은 `Destroy` 전까지 산다(수명 묶기에 쓸 수 있다) | `instance-lifecycle.md` §5 |
| Destroy 하지 않고 버린 Instance + 그것을 잡는 연결 | 누수. Tween·AnimationTrack 처럼 아무도 Destroy 하지 않는 객체에 건 연결도 같다 | `instance-lifecycle.md` §6, `tween-and-animation.md` §5 |
| 시그널 userdata 를 표의 키로 썼다 | 읽을 때마다 새것이라 키로 못 쓴다 | `signals-and-events.md` §6 |
| weak-key 표의 값이 키를 잡는다(엔진과 무관) | Luau 는 ephemeron 이 아니라 영구 잔존 | luau-runtime `gc-and-weak-tables.md` §2 |

---

## 정정

| 원천 경로:줄 | 틀리거나 낡은 서술 | 맞는 것 | 근거 |
|---|---|---|---|
| quad qwreey-harness .claude/scopes/packs/luau-kb/audit/08 Q-011 비고 | `collectgarbage("collect")` 가 일반 스크립트에서도 막혔는지 범위 재확인 필요 | Roblox 샌드박스 전체에서 `"count"` 만 허용(문서) | 문서 `reference/engine/globals/LuaGlobals.yaml` collectgarbage (`roblox_docs.py api LuaGlobals.collectgarbage`) |
