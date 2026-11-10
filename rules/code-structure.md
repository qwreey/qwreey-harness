---
paths:
  - "**/*.luau"
  - "**/*.lua"
---
# 코드 구조 — 정본 안내

- 정본은 사용자 레벨 `~/.claude/rules/code-structure.md` 다(claude-doctor `home/.claude/rules/code-structure.md` 가 관리하고 툴킷과 무관하게 적용된다). 파일 길이·분리 절차·예외 표식·데이터 표 규칙은 거기서 읽는다.
- Luau 세부(줄 수 기준의 근거, `split-plan.py`, `--@structure-exempt`, 옮기기만 커밋)는 [structure](../skills/luau-style/references/structure.md)·[splitting](../skills/luau-style/references/splitting.md) 에 있다.
- Luau 고유: 같은 접두 파일을 `접두/` 폴더로 묶을 때 입구는 `init.luau` 로 두고, 폴더 안 형제는 `@self/` 로 부른다. → [structure§5](../skills/luau-style/references/structure.md)
