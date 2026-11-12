# devplorer 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)

luau-kb 가 devplorer 의 서술을 더 새 실측·문서와 대조해 보니 틀렸거나 낡은 것들이다. 반영 여부는 devplorer 세션이 판단한다.
- 줄 번호는 2026-11-10 에 `/code/Projects/devplorer` 를 읽기 전용으로 열어 확인했다.
- 근거 경로는 `/code/Projects/luau-kb/` 기준이다.
- 심각도
  - **행동**: 그대로 따르면 설계·예산 판단이 틀어진다.
  - **표현**: 결론은 맞거나 이미 같은 저장소 안에서 고쳐졌고, 문구만 낡았다.

| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| DV01 | `.claude/review/2026-10-19-server-security.md:190` (S-08) | DataStore 쓰기 예산은 서버 전체가 공유하는 "분당 60 + 플레이어 수 × 10" 이다 | 2026-10 문서 기준 서버 기본값은 `60 + 플레이어 × 40`(Write)이고, experience 전체 한도는 `300 + CCU × 20` 이다. 2026-07-29 부터 Open Cloud 와 공유한다. 옛 예산을 인용했다 | `skills/roblox-luau/references/platform-services.md` 정정, table-sim `<비공개>` | **행동** (예산 계산) |
| DV02 | `.claude/review/2026-10-19-server-security.md:92`, `:389-390` | 약한 표에 둔 Instance 가 수거되는지는 실측하지 않았으므로(S-03) 약한 표를 쓰지 않았다 | Destroy 된 Instance 는 수거된다(rbvm·quad Studio 실측). 다만 엔진이 userdata 를 다시 만들 수 있어 weak 키 항목이 미아가 될 수 있다. 설계를 다시 정할 때 이 두 사실을 입력으로 쓴다 | `skills/roblox-luau/references/instance-lifecycle.md` §4–5·정정, rbvm `.claude/design/engine-behavior.md:47` | **행동** (설계 판단의 입력) |
| DV03 | `.claude/review/2026-10-20-client-palette-copy.md:50` | `Workspace.SignalBehavior` 가 Deferred 일 때의 동작은 미실측이다 | 같은 저장소 bindable-watch(`:85`)와 quad·rbvm 이 실측했다 | `skills/roblox-luau/references/signals-and-events.md` 정정 | 표현 |
| DV04 | `.claude/feedback/quad-upstream-2026-10-20.md:494` | 필드를 좁힌 뒤 다른 호출이 끼면 "could be nil" 이 난다 | luau-analyze 0.734·0.742, luau-lsp 1.69.0·1.70.1 모두 재현되지 않았다. 재현되는 것은 루프 모양뿐이다. quad 상류에 보낼 문서라 보내기 전에 재확인을 권한다 | `skills/luau-types/references/unions-singletons.md` §6·§12, `unions-closure-loop-narrowing` | 표현 |
| DV05 | `.claude/review/2026-10-19-server-structure.md:25` (【추론】) | `QueryDescendants` 가 `:has()`·`:not()` 과 `[prop ^= "x"]` 계열 연산자를 지원한다(문서 기억) | `:not` 은 "Expected at least one filter", `^=`·`*=`·`$=` 는 "comparison operator expected"(`not a valid selector`)로 엔진이 거부한다 | `skills/roblox-luau/references/instance-api.md` 정정 | 표현 (같은 저장소 `.claude/audit/2026-10-19-server-structure.md:23` 과 `.claude/review/2026-11-08-post-move-audit.md:40` 이 이미 실측) |
