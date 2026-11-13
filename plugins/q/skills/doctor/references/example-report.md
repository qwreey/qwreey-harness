# 모델 판정 예

scan 결과는 후보다. 원문을 읽고 판정한 예를 든다(luau 저장소 table-sim, stl-luau-doctor).

| scan 결과 | 원문 대조 | 판정 |
|---|---|---|
| `RULE-DUP` `src-containers.md:12 ↔ conventions.md:126` (0.94) | 둘 다 "새 균형 방식은 `src/Trees/`에 파일 하나 + `const _balance…`" | **중복**. conventions 쪽 문장을 걷고 '왜'만 남긴다 |
| `RULE-DUP` `docs.md:8 ↔ conventions.md:9` (0.66) | conventions 쪽은 "언어 규칙은 루트 CLAUDE.md '언어'"라는 포인터뿐이다 | **중복 아님** |
| `RULE-DUP` `src-modules.md:17 ↔ conventions.md:31` (0.62) | conventions 쪽에 `At`·`IndexOf`·`CountBelow` 어휘가 더 있다 | **중복이자 누락**. 빠진 어휘를 rule로 옮기는 안도 낸다 |
| `SKILL-SIDEFX` delegate-agy (`setpriv`) | 별도 uid로 agy를 띄우고 worktree를 만든다 | **판단이 갈림**. 사용자에게 묻는다(사용자 전용으로 할지) |
| `TOOL-CLAIM` table-sim `mise.toml:3` | "핀은 형제(quad·tbox·stl-luau)와 같은 값"이라는데 stl은 0.742 / 1.70.1이다 | **참**(`<doctor>/.claude/base/decisions/README.md` 낡은 서술 목록과 같다). 이유 중심으로 다시 쓰는 안을 낸다 |
| `LOAD-TODOS-DONE` table-sim | "된 것" 절 16,962 B | **고칠 안**: D-07대로 import되지 않는 파일로 옮기고 `todos.md:5` 규칙 문장도 바꾼다(승인 필요) |
| `DRIFT-HOOKDUP` table-sim | 사용자 레벨 heavy-proc-guard가 실제 `~/.claude`에 이미 등록돼 있다 | **고칠 안**: 프로젝트 settings의 hooks 항목을 걷는다(승인 필요). 훅 파일 삭제는 HUMAN_TODO로 |

대상 저장소 계열에 세션이 있으면(`SESSION-SIBLING`) 고칠 안은 모두 `인계`로 분류하고 `<doctor>/.claude/handoff/<repo>.md`에 덧붙인다.
