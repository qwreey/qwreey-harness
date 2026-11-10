# tbox 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)

luau-kb 가 tbox 의 서술을 재현해 보니 틀렸거나 낡은 것들이다. 반영 여부는 tbox 세션이 판단한다.
- 줄 번호는 2026-11-10 에 `/code/Projects/tbox` 를 읽기 전용으로 열어 확인했다.
- 근거 경로는 `/code/Projects/luau-kb/` 기준이다. 스니펫은 `snippets/<ID>`, 도구는 `tools/` 에 있다.
- 심각도
  - **행동**: 그대로 따르면 도구 사용·검증·코드 판단이 틀어진다.
  - **표현**: 처방은 맞고 원인·조건 설명만 부정확하다.
- `decisions/README.md` "이번에 발견한 낡은 서술"의 tbox 항목(5번째 줄)을 T01 로 합쳤다.

| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| T01 | `CLAUDE.md:84-91` | 이 환경의 stylua 2.5.2 는 `syntax = "Luau"` 여도 `f<<T>>(...)` 를 망가뜨린다 | 재현되지 않는다. 설정이 적용되지 않은 실행(하위 폴더에서 실행 등)에서만 망가진다. 저장소 루트에서 `syntax = "Luau"` 로 돌리면 보존된다 | `tools/repro-stylua-typeargs.sh`, `skills/luau-verify/references/tooling.md` (stylua 절), claude-doctor `decisions/D-02-stylua.md` | **행동** (명시 타입 인자나 stylua 를 피할 이유가 없어진다) |
| T02 | `docs/code-review-2026-10-05.md:20-21` | `luau-analyze --fflags=LuauDoNotExportBrokenTypeFunction=false` 로 확인했다 | `luau-analyze` 에서는 효과가 없다. 0.734 는 플래그를 받지만 결과가 플래그 없을 때와 같고, 0.742 는 "unrecognized flag" 경고를 낸다. 그 확인이 필요했던 결론은 luau-lsp 로 다시 봐야 한다 | `skills/luau-types/references/type-functions.md` §5, `tf-cross-module.sh` M1 | **행동** (검증 방법이 무효) |
| T03 | `packages/tbox/scripts/analyze.luau:24-32`; `.vscode/settings.json:7-8` | `--flag:LuauDoNotExportBrokenTypeFunction=false` 를 준다 | 핀인 luau-lsp 1.69.0 에서는 필요하다. 1.70.1 로 올리면 그 플래그는 "Unknown FFlag" 경고만 내고 분석은 계속된다. 버전을 올릴 때 지운다 | `skills/luau-types/references/type-functions-limits.md` X1, `tf-cross-module.sh` M2–M3 | 표현 (버전 올릴 때 할 일) |
| T04 | `packages/tbox/CLAUDE.md:121` | 정적 타입이 옵션 테이블의 모르는 키를 못 잡는 것은 `Types.Merge` 가 만드는 테이블 타입이 닫혀 있지 않아서다 | `Merge` 탓이 아니다. 새 솔버는 손으로 쓴 테이블 타입과 교집합에서도 리터럴의 남는 키를 검사하지 않는다. 런타임 거부(`New` 의 옵션 목록)가 유일한 방어라는 결론은 그대로다 | `type-functions.md` §5, `tf-noalt-merge` | 표현 (원인) |
| T05 | `packages/tbox/CLAUDE.md:150`; `packages/tbox/src/types.luau:105-106` | Luau 교집합(`&`)이 `?` 와 섞이면 깨진다 | 최소 꼴 `(A & B)?` 는 0.734·0.742 에서 대입과 거부 모두 정상이다. 깨지는 꼴이 따로 있으면 재현 파일이 필요하다 | `type-functions.md` §5, `tf-noalt-merge` | 표현 (확인 요청) |
| T06 | `CLAUDE.md:141-145` | 테스트 엔트리를 `init.luau` 로 지으면 `src/init.luau` 와 이름이 겹쳐 ambiguous 가 난다 | 그 조합만으로는 모호하지 않다. ambiguous 는 대상에 `X.luau` 와 `X/` 가 함께 있거나, 요구하는 폴더 옆에 같은 이름 파일이 있을 때 난다. `tests/init.luau` 의 실제 함정은 그 안의 `./` 가 저장소 루트를 가리키는 것이다. 처방(엔트리를 `init.luau` 로 짓지 않음)은 같다 | `skills/roblox-luau/references/require-and-modules.md` §1·§2, `rbx-require-cli.sh` Q4·Q5 | 표현 (원인) |
