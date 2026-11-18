---
description: 코드 구조 규칙의 Luau 세부 위치 안내. 정본은 qwreey-conventions 플러그인의 code-structure rule
paths:
  - "**/*.luau"
  - "**/*.lua"
---
# Code structure - pointer to the canonical rules

- The canonical rules are the `code-structure` rule of the qwreey-conventions plugin (qwreey-harness `plugins/qwreey-conventions/rules/code-structure.md`, injected when a matching file is opened; applies to every toolkit). File length, split procedure, exemption markers, and data-table rules are there.
- Luau details (rationale for the line limits, `split-plan.py`, `--@structure-exempt`, move-only commits) are in [structure](../skills/luau-style/references/structure.md) and [splitting](../skills/luau-style/references/splitting.md).
- Luau-specific: when grouping same-prefix files into a `prefix/` folder, make the entry `init.luau` and require siblings inside the folder as `@self/`. → [structure§5](../skills/luau-style/references/structure.md)
