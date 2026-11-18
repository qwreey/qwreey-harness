# compact — 대화를 요약해서 책상 비우기

> 한 줄: 대화가 길어지면 지금까지의 대화를 **요약본으로 바꿔** 자리를 비운다. 편하지만 세부가 빠질 수 있다.

## 쉽게 말하면
- 회의록 50쪽을 1쪽 요약으로 바꾸고 원본은 치우는 것과 같다.
- 컨텍스트가 한계에 가까워지면 **자동으로** 일어난다(auto-compact). 직접 `/compact` 로 할 수도 있다.
- 한 시간쯤 자리를 비운 긴 대화는 다음 메시지 때 요약본으로 보내는 기능(idle compaction)도 있다. 기본으로 켜져 있다.

## 요약 뒤에 남는 것과 사라지는 것 (공식 표 요지)
| 무엇 | compact 뒤 |
|---|---|
| CLAUDE.md(프로젝트 루트), paths 없는 rules, auto memory | 파일에서 다시 읽어 넣는다 |
| 최근 읽거나 고친 파일 | 최대 5개를 다시 읽는다(큰 파일은 경로만) |
| 실행한 스킬 본문 | 다시 넣되 스킬당·전체 크기 제한이 있다(앞부분 우선) |
| paths 가 있는 rules, 하위 폴더 CLAUDE.md | 요약에 묻히고, 해당 파일을 다시 다룰 때 다시 읽힌다 |
| 훅이 넣었던 알림, 대화 중 내가 한 지시 | **요약에 섞인다.** 세부 문구는 사라질 수 있다 |

## 왜 조심해야 하나
- 대화 중에 말로만 한 중요한 지시("이 폴더는 건드리지 마")는 요약에서 약해질 수 있다. 계속 지켜야 할 것은 CLAUDE.md 에 적는다(동의 필요).
- compact 자체도 **큰 요청**이다. 요약하려면 긴 대화를 한 번 다 읽어야 하기 때문이다.
- 반면 `/clear` 는 비용이 들지 않는다. 이어 갈 필요가 없으면 `/clear` 가 낫다.

## 이렇게 하면 좋다
- 큰 일을 시작하기 전에 직접 요약 방향을 준다: `/compact 지금까지 정한 UI 배치 결정만 남겨 줘`
- 프로젝트 CLAUDE.md 에 `# Compact instructions` 절을 두면 자동 요약 때도 무엇을 남길지 알려 줄 수 있다.
- 일부만 요약하려면 `/rewind` 에서 메시지를 골라 "여기부터 요약" 을 고른다.
- 진행 상황을 파일(예: 작업 메모)에 적어 두고 `/clear` 하는 방식이 길게 compact 로 끌고 가는 것보다 안정적이라는 의견이 많다.

## 흔한 오해
- "compact 하면 다 기억한다" → 요약이다. 숫자, 정확한 문구, 작은 결정이 빠질 수 있다.
- "compact 는 공짜다" → 긴 대화일수록 compact 한 번이 비싸다.

## 역할별 예
- 비프로그래머: 하루 종일 한 대화로 이것저것 시키다 보면 몇 번씩 compact 된다. 아침에 정한 규칙이 오후에 흐려지면 이것 때문일 수 있다.
- 개발자: 긴 디버깅 중 compact 되면 "이미 해 본 시도" 를 다시 하는 일이 생긴다. 시도 목록을 파일로 남기자.

## 이해 확인 질문 (설명 뒤 하나만 골라 묻는다)
- compact 뒤에도 남는 것과 흐려질 수 있는 것을 하나씩 말해 보세요.
- 이어 갈 필요 없는 일이면 compact 와 `/clear` 중 무엇이 싼가요?

## 근거
- 공식: code.claude.com/docs/en/context-window ("What survives compaction", "When your context fills up")
- 공식: code.claude.com/docs/en/costs ("Compaction: /compact reads the conversation...", "# Compact instructions" 예시)
- 공식: settings-reference `idleCompaction` (기본 true, v2.1.290 이상) — qwreey-harness .claude/audit/19-external/05 #4 에서 확인
- 미확인: 자동 compact 가 시작되는 정확한 비율(모델·설정마다 다름, model-config 문서 참고)
