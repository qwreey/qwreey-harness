# rbvm 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)

luau-kb 가 rbvm 의 서술을 엔진 실측(대부분 rbvm 자신의 `.claude/design/engine-behavior.md`)과 대조해 보니 어긋나는 것들이다. 반영 여부는 rbvm 세션이 판단한다.
- 줄 번호는 2026-11-10 에 `/code/Projects/rbvm` 을 읽기 전용으로 열어 확인했다.
- 근거 경로는 `/code/Projects/claude-doctor/packs/luau-kb/` 기준이다.
- 심각도
  - **행동**: rbvm 이 엔진과 다르게 동작하거나, 그 서술을 근거로 한 설계가 틀어진다.
  - **표현**: 이미 고쳐졌거나 근거만 낡았다.
- `.claude/base/decisions/README.md` "이번에 발견한 낡은 서술"의 rbvm 항목(4번째 줄)을 R04 로 합쳤다. `HUMAN_TODO.md` 의 기존 rbvm `const` 항목과 같은 내용이다.

| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| R01 | `.claude/design/architecture.md:209` | require 프록시는 접두사가 없으면 형제 기준으로 푼다 | 엔진은 접두 없는 경로를 `require path must start with a valid prefix: ./, ../, or @` 로 즉시 거부한다. rbvm 이 엔진에서 실패할 코드를 통과시킨다. 없는 모듈·빈 세그먼트·모르는 alias 에서 무한 대기하는 점(엔진은 즉시 에러)도 같은 절에 있다 | `skills/roblox-luau/references/require-and-modules.md` §6, `instance-api.md` 정정, rbvm `.claude/design/engine-behavior.md:68-83` | **행동** (mock 충실도) |
| R02 | `.claude/design/gc-and-lifecycle.md:87-92` | 시그널 키를 강하게 쥐고 있으면 같은 userdata 를 다시 얻는다 | 쥔 채로도 다시 얻은 값과 `rawequal` 이 false 다(`==` 는 true). 표 키는 `rawequal` 기준이라, 다시 얻은 시그널로 표를 조회하면 다른 키가 된다 | `skills/roblox-luau/references/signals-and-events.md` 정정, rbvm `.claude/design/engine-behavior.md:22` | **행동** |
| R03 | `.claude/review/2026-10-05-code-review.md:590` | 엔진에서는 Destroying 시점에 계층이 아직 온전하다 | Deferred 에서는 핸들러 안에서 `Parent` 가 이미 nil 이다 | `skills/roblox-luau/references/instance-lifecycle.md` 정정, rbvm `.claude/design/engine-behavior.md:45` | 표현 (원천에서 이미 정정 표시) |
| R04 | `.claude/conventions.md:28-37` | `const` 를 쓰지 말 것 — `local` 만 | 금지 근거(pesde 0.7.3 의 `const` 미지원)는 0.7.4 에서 사라졌다. D-01 확정은 "써도 된다, 한 파일 안에서 섞지 않는다"다. 규약을 유지할지는 rbvm 이 정한다 | claude-doctor `.claude/base/decisions/D-01-const.md` | 표현 (근거가 낡음) |
