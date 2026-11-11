# P: 본문 토론 1라운드 (c5e60f5 기준)

## 1. 문제 (심각한 순서)
1. **fresh-advisor 의 description, 본문, 훅이 서로 어긋나 plan 에 닿을 길이 없다.**
   - 위치: `fresh-advisor/SKILL.md:3`, `:20`, `nudge.py:10`.
   - 훅 docstring 은 '접근 확정 전'을 스킬에 맡긴다고 하는데, 맡긴 그 자리에 해당 시점이 없다. ExitPlanMode 훅은 기본값이 꺼짐이고 사용 기록도 0회다.
   - 고칠 것: 판단 하나로 쓴다. "before you commit to an approach or a claim that only you have checked".
2. **done 이 `/code-review` 의 시점·대상과 겹친다.**
   - 위치: `SKILL.md:22` "before completion or commit, diff above threshold", `reviewer.md:36` "missing tests", `:62` "bugs reproduced by a test". 커밋 훅(`nudge.py:141-145`)도 같은 순간에 이 리뷰어를 권한다.
   - 고칠 것: done 을 "claims and the user's requests, not defects in the diff (that is /code-review)" 로 좁힌다. reviewer 에서 missing tests 를 뺀다.
   - 같이 지울 것: "threshold" 는 본문에 정의가 없으니 지운다.
3. **inherit 예시에 `options: reqs` 가 고정으로 박혀 있다**(`:13`).
4. **inherit `:23` 의 tier off 줄이 description 의 "the user does not need to ask" 와 부딪친다.** tier 를 읽는 곳도 inherit 에는 없다.
   - 고칠 것: 읽는 곳과 이유를 적거나, 줄을 지운다. 훅은 inherit 를 막지 않는다.
5. **inherit `:22` "right after your latest response" 는 턴 경계를 전제한다.** 그러면 모델이 결론을 먼저 말한 뒤에 부르게 된다.
   - 고칠 것: "in the same turn, before the next step".
6. **fork 템플릿 `:14` 의 "injection paths" 는 하네스 장면에서 남은 흔적이다.** 전역에서는 보안 injection 으로 잘못 읽힌다(추론).
   - 고칠 것: "(other callers, other users and sessions)".
7. **ledger 예시가 실제 값을 담고 있다**(`fresh :50-51`). 베끼기 쉽고, `--reviewer` 에 허용되는 값이 없으며, 기록하는 이유도 없다. §9 의 `--verdict partial` 과 같은 유형이다.
8. **low tier 의 `skip` 이 무엇을 뜻하는지 불분명하다**(`:18-22`). 고칠 것: "skip = do not call it on your own".
9. **불필요한 문장.** fresh `:16` "The plugin hooks use the same table. The frontmatter default is opus.", `:54` Stats, inherit `:31` 의 괄호.
10. **형제 스킬끼리 지시가 반대인데, 그 이유인 맥락 차이가 드러나지 않는다.** other-frame 의 `--kind inherit --reviewer ctx-*` 도 이름이 맞지 않는다(ledger 호환 때문). 설명 한 마디가 필요하다.

## 2. 전·후 틀
대체로 맞다. fresh 는 앞(접근 확정 전)으로 옮기고, done 은 주장 검증으로 좁혀 남긴다. 스킬을 쪼개지는 않는다.
- `/code-review` 는 일을 마친 뒤의 결함 탐색이다. 커밋 전이 바로 그 자리다.
- fresh 가 실제로 불리는 경로는 커밋 훅의 done 과 실패 훅의 stuck 뿐이라, 사실상 커밋 전 도구로 굳어 있다.
- 독립된 눈이 가장 값진 때는 diff 가 없어 `/code-review` 가 도울 수 없는 접근 확정 전이다. high tier 도 plan 에 opus 를 배정한다.
- done 을 남기는 이유: `/code-review` 는 사용자 원문을 읽지 않는다. reviewer 의 요구 대조와 주장 확인은 고유하다.
- 판정할 실험: plan 직전 장면과 커밋 직전 장면을 만든다. 현재안과 수정안을 각 5회 돌려 fresh 발동률과 `/code-review` 중복 호출률을 잰다.

## 3. 가장 강하게 밀 변경
1번과 2번이다. 훅이 스킬에 맡긴 유일한 시점이 스킬에 없다. 이것은 문구 취향이 아니라 배선 결함이다.
