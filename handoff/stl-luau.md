# stl-luau 세션에게 — 에이전트 문서 다이어트 반영 요청

claude-doctor 가 stl-luau 의 `.claude` 문서를 공식 권장 구조로 재구성한 초안을 만들었습니다. 이 세션이 진행 중인 작업과 충돌하지 않도록, **반영은 이 세션이 직접** 해 주세요. 지금 작업이 끝난 뒤에 해도 됩니다.

## 초안 위치
- 브랜치: `doctor/diet` (worktree `/code/Projects/stl-luau-doctor`, `e77fc03` 기준 7커밋)
- 근거와 분류표: `/code/Projects/claude-doctor/audit/07-stl-luau-diet.md`
- `src/`, `tests/` 는 바꾸지 않았습니다.

## 무엇이 바뀌나
1. **CLAUDE.md**: `@import` 셋을 끊고 본문 52줄로 줄였습니다(정체성, 넘지 않는 선, 명령, 지금 상태).
   - 상시 로드량이 51KB 에서 4.6KB 로 줄었습니다.
2. **`.claude/rules/` 6개**: 모두 `paths:` 를 달았습니다(luau-style, src-modules, src-containers, src-trait, tests, docs).
   - 해당 경로의 파일을 Read/Write 할 때만 자동 로드됩니다.
3. **`.claude/skills/`**: neg-spike, review-round, classify-container, doc-audit, handover 를 두었습니다. handover 는 사용자 호출 전용입니다.
4. **질문 BI 반영**: AB "예외 없음" 서술과 GEMINI.md 의 AB/BD 확정 서술을 걷고 "전환 중" 으로 다시 적었습니다.
   - AB 원문은 `archive/conventions-2026-11-10.md` 에 있습니다.

## 사용자 결정 (2026-11-10)
- **규칙의 정본은 rules 하나다.** 같은 규칙을 `conventions.md` 에 다시 적지 않는다.
  - `conventions.md` 는 작게 유지하고, rules 의 근거 링크가 가리키는 "왜" 만 남긴다.
  - 초안은 아직 두 곳에 중복이 있다. 반영할 때 conventions 쪽을 걷어 주세요.
- **todos 는 이 세션이 BI 기준으로 갱신한다.** 초안은 충돌을 피하려고 todos 를 건드리지 않았습니다.
- 일반 Luau 지식 23곳에 `<!-- luau-kb 후보 -->` 를 달아 두었습니다.
  - 이것들은 나중에 `/code/Projects/luau-kb` 스킬로 옮겨집니다. 지우지 말고 표시만 유지해 주세요.

## 반영 방법 (권장)
- `conventions.md`, `.claude/tools/doc-check.py` 는 이 세션이 그사이 바꿨을 가능성이 높습니다.
  - rebase 보다는 초안 diff 를 보고 손으로 다시 적용하는 편이 안전합니다: `git diff e77fc03..doctor/diet -- <파일>`
- 다른 파일(rules/, skills/, CLAUDE.md, GEMINI.md)은 cherry-pick 이나 checkout 으로 가져와도 됩니다.
- 반영한 뒤 확인할 것
  - 아무 `.luau` 를 Read 했을 때 rules 가 붙는지
  - `/context` 의 상시 로드량
- 다 끝나면 사용자에게 알려 주세요. `stl-luau-doctor` worktree 정리는 사용자가 합니다.
