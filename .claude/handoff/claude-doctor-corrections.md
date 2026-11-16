# claude-doctor 자신에 대한 정정 (2026-11-10)

luau-kb 증류에서 재현해 보니 claude-doctor 의 결정 문서·후보표·초안 서술이 틀렸거나 낡은 것들이다. 메인 세션이 반영한다.
- 근거 경로는 `/code/Projects/claude-doctor/packs/luau-kb/` 기준이다.
- 심각도
  - **행동**: rules·결정·후보표를 그대로 따르면 판단이 틀어진다.
  - **표현**: 범위나 상태 표시만 낡았다.

| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 | 상태 |
|---|---|---|---|---|---|---|
| CD01 | `.claude/base/decisions/D-01-const.md` §2 | `local const x = 1` 은 린트 경고만 난다 | nonstrict 에서만 맞다. `--!strict` 에서는 luau-analyze 0.734·0.742 가 `TypeError: Unknown global 'x'` 를 낸다. 실행은 두 모드 모두 된다 | `skills/luau-style/references/idioms.md` 정정, `snippets/style-const-local-const-global.luau` | **행동** | 반영됨(2026-11-10) |
| CD02 | `.claude/scopes/packs/luau-kb/audit/09-other-knowledge-mine.md` M-05 요약 | Luau 로 글자마다 도는 파서는 약 40배 느리다 | 할당 없는 `string.byte` 손 파서는 `gmatch` + `tonumber` 의 0.69~0.74배(인터프리터), 0.25배(native)다. 원문(mrow `REVIEW.md:809-813`)은 파서 컴비네이터 라이브러리의 값이었고, 요약이 일반화를 잘못했다 | `skills/luau-perf/references/strings.md` §5 | **행동** (방향이 뒤집힘) | 반영됨(2026-11-10) |
| CD03 | `.claude/base/decisions/D-12-require-paths.md` §2 "기록 3곳" | 정적 검사가 require 경로 오류를 잡지 못한다 | strict 조건을 붙인다. `--!strict` 면 없는 경로는 `Unknown require` 로 잡힌다. 못 잡는 것은 nonstrict 와 다른 실제 파일로 풀리는 오타다. 규칙 4(실제 require 테스트)는 그대로 필요하다 | `skills/roblox-luau/references/require-and-modules.md` §5·§9, `skills/luau-verify/references/checkers.md` §7 | 표현 | 반영됨(2026-11-10) |
| CD04 | `.claude/scopes/packs/luau-kb/archive/research/drafts/style/skills/luau-style/references/modules.md:314-315` | 위와 같음 + 동적 require 경로는 `ambiguous` 에러를 낸다 | luau 0.734·0.742 런타임은 동적 경로를 실행하고, strict 의 luau-analyze 만 `unsupported path` 로 거부한다(Studio 는 미측정) | `skills/luau-style/references/modules.md` 정정, `snippets/style-require-paths.sh` R3·R4 | 표현 (초안) | 반영됨(2026-11-10) |
| CD05 | `.claude/scopes/packs/luau-kb/audit/09-other-knowledge-mine.md` S-P14·S-P47·S-P27·S-P33·S-P23·S-P01 | stl perf 수치 요약 | 원천과 같이 틀렸다. `.claude/handoff/stl-luau-corrections.md` S01·S07·S06·S04 와 같고, S-P01 은 "`rawget` 도 못 피한다"로 유지 | `.claude/handoff/stl-luau-corrections.md` | 표현 (후보표 비고) | 반영됨(2026-11-10) |
| CD06 | `.claude/scopes/packs/luau-kb/audit/09-other-knowledge-mine.md` §6 모순 2 | 라이브 Roblox 최적화 수준: 미판정 | Roblox 문서 `luau/comments.md` 가 `--!optimize` 기본값을 Studio 테스트 1, 라이브 게임 2 로 적는다. stl 쪽이 맞다(엔진 안 실측은 없음) | `skills/roblox-luau/references/perf.md` §6 | 표현 | 반영됨(2026-11-10) |
| CD07 | `.claude/scopes/packs/luau-kb/audit/08-quad-knowledge-mine.md` Q-011 비고 | `collectgarbage("collect")` 가 일반 스크립트에서도 막혔는지 범위 재확인 필요 | Roblox 샌드박스 전체에서 `"count"` 만 허용된다(`LuaGlobals.md`, 2026-11-10 확인) | `skills/roblox-luau/references/gc-and-weak-tables.md` §6 | 표현 | 반영됨(2026-11-10) |
| CD08 | `.claude/base/decisions/D-10-error-handling.md` | 테이블 필드 경유 호출은 `-O2` 에서 안전하다, 위치가 "사라진다" | 대입 필드만 안전하고 리터럴 필드는 인라인된다. 틀린 줄도 가리킨다. 이미 D-10 "정정" 절에 반영됐다 | `skills/luau-testing/references/optimize-levels.md` §2 | 표현 (반영됨, 확인용) | 반영됨(D-10 정정 절 확인) |

## 상류 문서 (전달처 없음)
- Jest Roblox `docs/docs/GettingStarted.md` 의 `^3.21.0` 은 wally 최신이 3.20.1 이라 해석에 실패할 것으로 보인다(미실행). 출처: `skills/luau-testing/references/repo-practices.md` §3.
- Roblox 문서 `luau/native-code-gen.md` 의 "behavior … is exactly the same" 은 `--!native` 가 최적화 수준 2 를 강제해 에러 위치·traceback 이 바뀌는 점(CLI 실측)을 말하지 않는다. 출처: `skills/luau-perf/references/optimizer-and-native.md` §8.
