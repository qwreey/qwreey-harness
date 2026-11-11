# 토론 자료: second-opinion 두 스킬의 description (2026-11-11)

## 쟁점
`second-opinion:inherit-advisor` 와 `second-opinion:fresh-advisor` 의 description 을 무엇으로 할 것인가. 특히 **마지막의 사용 조건 문장**("Reach for it whenever …")이 쟁점이다.
이 플러그인은 모든 저장소의 모든 세션에 전역으로 깔린다. 같은 문장이 매 세션 스킬 목록에 실리고 매번 발동 판단에 쓰이므로, 문장 하나의 작은 차이가 누적된다.

## 후보
- **A (2단계 직후, 사용자가 "모양은 이게 맞다"고 한 틀)**
  - inherit: "Get a second opinion on your own thinking. Forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and looks at your work from another angle. Reach for it whenever you want another view on your reasoning or want to check what you might have missed; no need to wait for a review request. 한 번 더 봐줘, 다른 눈으로 검토."
  - fresh: "Get a second opinion from a reviewer with fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the changes and the user's own words itself and tries to refute your claims. Reach for it whenever you want your claims about the work tested by someone who does not share your assumptions. 커밋 전 검토, 완료 전 검증."
- **B (현재 커밋 d6dfb99)**
  - inherit: "A self-check you run on your own initiative, for your own use: forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and challenges your reasoning (premises, missed requests, the design you just called done). Reach for it whenever you want another view on your own thinking, whether or not the user asked; the findings feed your next step, not a report. 한 번 더 봐줘, 다른 눈으로 검토."
  - fresh: "A self-check you run on your own initiative, for your own use: spawns a read-only reviewer in a new context that gets your claims in a short brief, reads the changes and the user's own words itself, and tries to refute what you say is done or true. Where a code review hunts defects in a diff, this tests your claims against what the user asked. Reach for it whenever you want your claims tested by someone who does not share your assumptions. 커밋 전 검토, 완료 전 검증."
- 참고(더 이전, 4c9d6d6): 시점을 나열한 판("Call it right before telling the user a conclusion, decision, or direction change, before moving on …, and before hard-to-undo steps such as apply or install guidance"). 사용자가 "나열은 좁힌다"며 버렸다.

## 사용자가 밝힌 요구 (원문 취지)
1. 앞 문장은 A 의 "Get a second opinion …" 모양이 낫다. B 의 "A self-check you run …" 보다.
2. 가장 중요한 것은 맨 끝의 **사용 조건**이다.
3. 이 검토는 **사용자 의사와 무관한 자율 검토**다. 사용자가 요청할 필요가 없다는 점이 핵심이다. A 의 "no need to wait for a review request" 는 의도가 살짝 불분명하다.
4. 발동 조건은 사용자 기준("사용자가 기댈 것")이 아니라 **에이전트 자신의 필요**여야 한다. fork 로 나온 하위 어드바이저는 '나'에게서 나온다는 맥락이 깔려 있고, '내'가 검토하고 싶은 것을 밀어 주는 방향이다.
5. `/code-review` 같은 내장 스킬도 모델이 스스로 부를 수 있다. 그것과 무엇이 다른지가 드러나야 한다.
6. 공식 원칙:
   - "Claude is already very smart"
   - 선택지나 상황을 많이 나열하지 않는다
   - 이유를 설명한다
   - skill-creator 는 Claude 가 스킬을 덜 부르는 경향이 있으니 description 을 "a little pushy" 하게 쓰라고 한다
   - description 은 "무엇 + 언제", 본문은 사용법

## 실측 사실 (작은 표본)
- 지식 스킬(luau-kb 12개, 증상형 질문): 단발 24/24, 맥락 있음 12/12 발동.
- 옛 `second-opinion:audit`(diff 검토): `claude -p` 단발에서 "커밋 전에 검토해 줘" 류 0/2, 바꾸기 전 description 도 0/1. 모델이 스킬 없이 직접 diff 를 읽었다.
- inherit-advisor: 맥락 있는 장면에서 스스로 부름 1/1(2단계). 3단계 합성 장면에서는 0/4. 이때 모델은 혼자 약점을 짚고 결론을 보류해 부를 필요가 생기지 않았다.
- 다른 세션(quietcode)에서는 실사용 중에 리뷰어를 스스로 부른 사례가 있다.
- 두 스킬 모두 CLAUDE.md(전역)에 이름과 성격이 한 줄씩 있다. description 만이 유일한 발동 신호는 아니다.

## 읽을 것
- 현재 스킬:
  - `/code/Projects/claude-doctor/plugins/second-opinion/skills/inherit-advisor/SKILL.md`, `fresh-advisor/SKILL.md`
  - 템플릿: `inherit-advisor/templates/fork-prompt.md`
- 감사와 원칙: `/code/Projects/claude-doctor/audit/24-skill-audit.md` §4, §7~§9
- 공식:
  - platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
  - skill-creator `/code/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/SKILL.md` (description 절)
- 이 환경에서 모델이 부를 수 있는 공식 스킬의 description 예시는 세션 시작 때 스킬 목록에 있다. 예: code-review, simplify, security-review.
