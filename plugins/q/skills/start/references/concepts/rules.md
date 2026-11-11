# rules — 특정 파일을 다룰 때만 꺼내 읽는 규칙

> 한 줄: `.claude/rules/` 폴더의 짧은 규칙 파일. `paths:` 를 붙이면 **그 파일을 다룰 때만** 읽혀서, CLAUDE.md 보다 싸다.

## 쉽게 말하면
- CLAUDE.md 가 "회사 전체 공지" 라면, rules 는 "이 작업대에서만 붙여 둔 주의 사항" 이다.
- 예: `*.luau` 파일을 고칠 때만 "Luau 타입 규칙" 을 읽게 한다. UI 이미지를 다룰 땐 안 읽는다.

## 생김새
```markdown
---
paths:
  - "src/**/*.luau"
---
# Luau 규칙
- 전역 변수를 새로 만들지 않는다.
```
- 위치: 프로젝트 `.claude/rules/*.md`, 내 전체 `~/.claude/rules/*.md`

## 언제 읽히나
| 경우 | 읽히는 때 |
|---|---|
| `paths:` 있음 | Claude 가 일치하는 파일을 읽거나 고칠 때 |
| `paths:` 없음 | **세션 시작 때 항상** (CLAUDE.md 와 같은 비용) |
- 그래서 rules 로 옮기기만 하고 `paths:` 를 안 붙이면 비용은 그대로다.
- compact 되면 paths 규칙은 요약에 묻히고, 그 파일을 다시 다룰 때 다시 읽힌다.

## 좋은 규칙
1. **짧게.** 한 파일에 한 주제.
2. **Claude 가 모를 것만.** "코드를 깔끔하게" 같은 말은 효과가 없다. "이 프로젝트는 `task.wait` 대신 `task.delay` 를 쓴다" 처럼 구체적으로.
3. **이유를 한 줄.** 이유가 있으면 비슷한 경우에도 맞게 판단한다.
4. 강조(IMPORTANT, 대문자)를 쌓지 않는다. 공식 문서: 강조를 쌓으면 규칙을 과하게 적용한다. 그래도 안 지키면 훅으로 옮길 신호다.

## 언제 쓰나 (비교)
| 하고 싶은 것 | 쓸 것 |
|---|---|
| 모든 대화에서 지켜야 할 짧은 약속(예: 동의 원칙) | CLAUDE.md 또는 `paths` 없는 rule |
| 특정 파일 종류에서만 필요한 규칙 | `paths` 있는 rule |
| 긴 절차·지식 | 스킬 → `skills.md` |
| 절대 어기면 안 되는 것 | 권한 규칙·훅 → `hooks-and-reminders.md` |

## 주의
- 플러그인으로는 rules 나 CLAUDE.md 를 배포할 수 없다. 그래서 이 온보딩은 동의 원칙 rule 을 **템플릿**으로 주고, 동의받고 복사한다.
- 프로젝트 rules 를 다른 폴더로 심볼릭 링크하면 처음 한 번 승인이 필요하다.

## 1분 실습
- 프로젝트에 `.claude/rules/` 폴더가 있는지 본다. 있으면 각 파일 맨 위에 `paths:` 가 있는지 본다(읽기만).

## 이해 확인 질문 (설명 뒤 하나만 골라 묻는다)
- `paths:` 없는 rule 은 언제 읽히나요?
- Luau 파일에만 필요한 규칙은 어디에 두면 싼가요?

## 근거
- 공식: code.claude.com/docs/en/memory ("path-specific rules", paths 없는 rule 은 시작 시 로드, 심볼릭 링크 승인)
- 공식: context-window (compact 뒤 paths 규칙은 on demand 재로드)
- 공식: best-practices (강조 쌓기, 훅으로 옮길 신호), plugins/components (플러그인 루트 CLAUDE.md 미로드)
