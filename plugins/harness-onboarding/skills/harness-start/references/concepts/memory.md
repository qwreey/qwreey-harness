# memory — 매번 자동으로 읽히는 메모 (CLAUDE.md 와 auto memory)

> 한 줄: Claude 는 대화가 끝나면 다 잊는다. 다음에도 알게 하려면 **파일에 적어 두고, 시작할 때마다 다시 읽게** 한다. 그 파일이 memory 다.

## 두 종류
| | CLAUDE.md | auto memory |
|---|---|---|
| 누가 쓰나 | 사람(나, 팀) | Claude 가 스스로 |
| 무엇을 | 지시·규칙·프로젝트 설명 | 내 교정·선호, 진행 중인 결정, 외부 자료 위치 |
| 언제 읽히나 | 매 세션 시작 | 매 세션 시작 (MEMORY.md 앞 200줄 또는 25KB 까지) |
| 어디에 | `~/.claude/CLAUDE.md`(나 전체), 프로젝트 `CLAUDE.md`, 회사 관리 CLAUDE.md | `~/.claude/projects/<프로젝트>/memory/` (이 컴퓨터에만) |

- CLAUDE.md 는 여러 겹이다: 회사 관리용(IT 가 배포) → 내 사용자용 → 프로젝트용 → 개인 로컬용(`CLAUDE.local.md`).
- auto memory 는 기본으로 켜져 있다. `/memory` 에서 켜고 끄고, 내용을 열어 볼 수 있다.

## 왜 "기억" 되나
- 모델이 배워서가 아니다. **파일이 남아 있고, 새 세션이 시작될 때 그 파일을 다시 책상에 올리기 때문**이다.
- 그래서 파일을 지우거나 고치면 "기억" 도 바로 바뀐다. 다른 컴퓨터에는 auto memory 가 따라가지 않는다.

## 커지면 왜 나쁜가
1. **매 메시지마다 비용.** 항상 책상에 올라가므로 길수록 모든 대화가 조금씩 비싸진다.
2. **덜 지킨다.** 공식 문서: 긴 CLAUDE.md 는 지시를 덜 지키게 한다. 권장은 파일당 200줄 미만.
3. **잘린다.** MEMORY.md 는 앞 200줄(또는 25KB)만 읽힌다. 뒤에 적힌 건 시작할 때 안 보인다.
4. **낡은 메모가 거짓말을 한다.** "다음 주 마감" 같은 메모가 몇 달 뒤에도 남아 판단을 흐린다. 서로 다른 메모가 부딪히기도 한다.
5. `@다른파일` 로 불러와도 비용은 줄지 않는다(불러온 파일도 같이 실린다).

## 이렇게 하면 좋다
- CLAUDE.md 에는 **Claude 가 스스로 알아낼 수 없는 것**만 짧게: 금지 사항, 팀 약속, 자주 틀리는 것.
- 일부 파일에서만 필요한 규칙은 rules(paths)로 옮긴다. → `rules.md`
- 긴 절차·지식은 스킬로 옮긴다(필요할 때만 읽힘). → `skills.md`
- 가끔 `/memory` 로 열어 보고 낡은 줄을 정리한다(정리도 파일 쓰기라 동의 후).
- "이거 기억해" 를 남발하지 않는다. 정말 반복되는 것만.

## 흔한 오해
- "CLAUDE.md 에 쓰면 반드시 지킨다" → 권고일 뿐이다. 반드시 지켜야 하는 건 설정(권한)이나 훅으로 막는다. → `hooks-and-reminders.md`
- "memory 는 회사 서버에 저장된다" → auto memory 는 이 컴퓨터의 파일이다(공식: machine-local).

## 이해 확인 질문 (설명 뒤 하나만 골라 묻는다)
- Claude 가 지난주 일을 '기억' 하는 진짜 이유는?
- MEMORY.md 가 300줄이면 무슨 일이 생기나요? (답: 앞 200줄만 읽힌다)

## 근거
- 공식: code.claude.com/docs/en/memory (CLAUDE.md vs auto memory 표, 200줄 권장, MEMORY.md 200줄/25KB, 4 종류 type, machine-local, `/memory`, 관리 CLAUDE.md 위치)
- 공식: code.claude.com/docs/en/best-practices ("CLAUDE.md is for guidelines... make it a hook")
