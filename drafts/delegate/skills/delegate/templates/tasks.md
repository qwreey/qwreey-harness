# 과제 프롬프트 틀

스크립트가 머리말(작업 환경 규칙)을 앞에 붙인다. 여기 있는 틀은 `# 과제` 아래에 들어갈 본문이다. 하나를 골라 스크래치에 복사해 채운다. 경로는 worktree 안 기준 상대 경로로 쓴다.

---

## A. 근본 원인 찾기 (agy, worktree)

```markdown
열린 문항 / 리뷰 발견 여러 개가 같은 메커니즘에서 나온 것 같다. 이것들을 개별 결함으로 보지 말고, 공통 뿌리를 위에서 찾아라.

읽을 것(정본):
- <원장 경로>의 <번호들> — 문항 원문만. 앞선 리뷰의 분류표는 일부러 주지 않는다(틀이 고정되지 않게).
- <설계 정본 경로>
- 코드: <경로들>, 테스트: <경로들>

원하는 것:
1. 뿌리 후보와, 각 후보가 설명하는 문항 / 설명하지 못하는 문항.
2. 후보마다 반증 가능한 근거: 파일:줄, 그리고 실행 가능한 프로브(worktree 안에 만들어 돌린 명령과 출력).
3. 이 틀에 갇히지 말 것 — 문항 목록 밖에서 같은 뿌리의 다른 증상이 보이면 적어라.
시간이 모자라면 <무엇>을 먼저 본다.
```

## B. 좁은 버그 사냥 (agy, worktree)

```markdown
범위는 하나다: <메커니즘 하나 — 예: 배열의 nil 구멍과 n 불변식 / 자기 자신과의 연산(별칭) / 발화 중 구독 해제>.
대상 모듈: <경로들>. 전 모듈을 훑지 말 것.

결함마다:
- 재현 프로브(최소 코드, 실행 명령, 실제 출력, exit code)
- 기대 동작의 근거(정본 문서 절 또는 공개 계약)
- 처방을 제안한다면, 그 처방의 비용(핫 경로라면 측정)
결함이 없으면 "발견 없음"과 무엇을 시도했는지.
```

## C. 이름 검토 — 세 계열 대조 (codex empty / agy / sonnet 에 같은 본문)

```markdown
# Naming review — <대상 한 줄>

You are reviewing public API names. Judge them from the point of view of the library's USERS (<누구>). Everything you need is below — do not look for files. Reply in Korean, concisely. Put your whole answer in one message.

## Context
- <라이브러리 한 단락: 무엇이고, 값 규약, 기존 이름들이 정한 관례>
- <비슷한 기존 이름과 그 뜻 — 충돌 후보>

## Names to judge
1. **<자리>.** <동작을 정확히 — 인자, 반환, 에러, 기존 것과의 차이>. Candidates: `A`, `B`, `C`.
   For each: your pick, a ranked shortlist (you may add one of your own), one or two reasons; flag a name that would mislead.
```

- 같은 본문을 codex(`--mode empty`), agy(`--mode empty` — 미검증이면 worktree), sonnet 서브에이전트에 준다.
- 메인은 표 하나로 대조한다(수렴 / 갈림 + 각 근거). 결정은 사용자가 한다. 선례는 `quad/.claude/audit/naming-devui-2026-10-20/`.

## D. 설계 결정에 대한 바깥 의견 (agy, worktree)

```markdown
결정 <ID>의 갈래 둘(또는 셋)에 대해, 이 저장소의 결정 이력을 모르는 사람의 눈으로 의견을 달라.
결정 원문: <question.md 절 경로>. 관련 정본: <경로>. 이미 기각된 모양: <archive 경로> — 그것을 다시 제안하려면 무엇이 달라졌는지 근거를 대라.
갈래마다 무엇이 막히는지(재현 경로), 그리고 사각지대(갈래 어느 쪽도 다루지 않는 경우)를 적어라.
```
