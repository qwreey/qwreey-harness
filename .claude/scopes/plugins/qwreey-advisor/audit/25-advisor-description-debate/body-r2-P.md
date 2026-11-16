# P: 본문 토론 2라운드

**양보**
- 조건 문구는 Q 의 "두 진입점" 틀을 받는다. "commit" 은 이 환경에서 `git commit` 으로 읽힌다. 그러면 fresh 가 `/code-review` 의 커밋 시점으로 다시 끌려간다(추론). 두 시점은 kind(plan/done)에 1:1 로 대응하는 진입점이라 나열이라고 보기 어렵다.
- Q 5번(brief 와 템플릿이 done 전용이다)을 받는다. brief.md 의 "Claims to verify" 앞에 종류별 한 줄을 둔다: plan 은 "the approach I am about to lock in, and the alternatives I dropped", stuck 은 "my current hypothesis". `SKILL.md:33` 에는 "(for plan, state the approach itself, not why you like it)" 를 덧붙인다.
- tier-off 줄은 Q 안(이유와 확인 방법)을 택한다. 근거는 셋이다.
  - (a) off 는 사용자가 이 저장소의 검토 예산을 끈 결정이다.
  - (b) 훅(`nudge.py:166`)은 inherit 를 막지 않으므로, 본문의 이 줄이 유일한 장치다.
  - (c) 이유가 붙어야 description 의 "does not need to ask" 와 충돌하지 않는다.
  - 문구: "If this repo's tier is `off` (`HARNESS_REVIEW_TIERS` in `~/.claude/harness.env`), the user has turned reviews off here; call it only when they ask."
- 고유 항목은 모두 받는다. 덧붙일 것은 둘이다.
  - relaunch 금지의 이유: 리뷰어가 연쇄로 다시 뜨면 비용이 폭주한다(.claude/audit/10 §2.2). 반쪽 결과는 "review incomplete: <what was not seen>" 으로 알리고, 읽은 범위의 발견만 처리한다.
  - ledger 의 이유: 발동률과 채택률을 조정하는 근거가 된다. 다만 doctor 가 실제로 읽는지는 확인하지 않았다(추론).

**반박**
- Q 문구 "…, on a view only you have checked" 는 수식이 매달려 있다. 그래서 "when only you have checked that view" 로 쓴다.
- stuck 을 description 에 넣지 않는 데 찬성한다. off tier 에서 stuck 이 사라지는 것은 의도된 동작이다.

**최종 fresh description (472자)**
"Get a second opinion from fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the user's own words and the files itself, without your assumptions, and tries to refute your view. Where a code review hunts defects in a diff, this tests your approach or claims against what the user asked. Reach for it before you lock in an approach or tell the user work is done, when only you have checked that view; no one needs to ask. 완료 전 검증, 내 주장 반박."

**inherit 와 fresh 중 무엇을 부를지 (description 과 본문 둘 다)**
- description 에는 서로의 이름을 넣지 않고 성질만 쓴다.
  - inherit: "…challenges your reasoning, not your diff; it sees your reasoning but may share your blind spots."
  - fresh: "without your assumptions".
- 본문 Call 절 첫 줄에는 고르는 규칙을 둔다. 기준은 되돌림 비용이다.
  - 되돌릴 수 있는 중간 단계는 inherit 로 간다.
  - 되돌리기 어려운 접근 확정이나 완료 보고는 fresh 로 간다.
- 비용 순서: inherit, fresh, `/code-review`(결함). other-frame 은 사용자 명령이다.
- 확인할 실험: 되돌리기 어려운 형식 결정 장면과 되돌릴 수 있는 중간 결론 장면을 각 N=5 로 돌린다. 고른 쪽이 맞는 비율이 7/10 이상이면 통과다.
