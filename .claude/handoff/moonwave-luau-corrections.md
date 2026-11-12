# moonwave-luau 세션에게: luau-kb 증류에서 나온 정정 (2026-11-10)

luau-kb 가 moonwave-luau 의 서술을 재현해 보니 범위가 부정확한 것들이다. 처방은 둘 다 그대로 맞다.
- 줄 번호는 2026-11-10 에 `/code/Projects/moonwave-luau` 를 읽기 전용으로 열어 확인했다.
- 근거 경로는 `/code/Projects/claude-doctor/packs/luau-kb/` 기준이다.
- 심각도: **행동**(따르면 판단이 틀어짐) / 표현(처방은 맞고 범위만 부정확).

| # | 원천 경로:줄 | 원래 서술 | 실측 결론 | 근거 | 심각도 |
|---|---|---|---|---|---|
| M01 | `.claude/conventions.md:73-74` | 정적 검사(luau-analyze)는 require 경로 오류를 런타임만큼 잡지 못한다 | `--!strict` 파일이면 풀리지 않는 경로를 `Unknown require` 로 잡는다. 못 잡는 것은 nonstrict 파일과 **다른 실제 파일로 풀리는** 오타다. 처방(실제로 require 하는 테스트)은 같다 | `skills/luau-verify/references/checkers.md` §7, `snippets/rbx-require-cli.sh` Q8·Q9 | 표현 |
| M02 | `.claude/conventions.md:122-123` (후보 M-14) | `table.insert(values, x:unwrap())` 꼴은 타입 검사가 잡지 않으니 `(x:unwrap())` 로 감싼다 | 괄호 처방은 맞다. 다만 호출이 값 0개를 돌려주는 경우는 `--!strict` 가 `No overload for function accepts 1 arguments` 로 잡는다. 못 잡는 것은 값 2개를 돌려줄 때다 | `skills/luau-style/references/pitfalls.md` 정정, `snippets/style-table-insert-pitfalls.luau` | 표현 (범위) |
