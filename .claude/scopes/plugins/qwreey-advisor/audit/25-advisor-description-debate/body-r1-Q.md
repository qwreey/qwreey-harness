# Q: 본문 토론 1라운드 (c5e60f5 기준)

## 1. 문제 (심각한 순서)
1. **fresh-advisor 의 plan·stuck 종류는 description 에 없어서 발동할 길이 없다.**
   - description 은 "Reach for it before you tell the user that something only you have verified is done or true" 로 완료만 말한다. 본문 `fresh-advisor/SKILL.md:18-22` 는 plan|stuck|done 세 종류를 둔다.
   - 훅이 잡는 것은 stuck 과 done 뿐이다. 훅 docstring(`nudge.py:10`)은 '접근 확정 전'은 잴 수 없어서 메인 판단에 맡긴다고 하고, ExitPlanMode 사용은 0회다.
   - 그러면 plan 의 신호는 description 뿐인데, description 이 그 시점을 말하지 않는다. plan 경로는 사실상 죽어 있다.
2. **inherit 호출 예시가 선택 옵션을 기본값으로 박는다.** `inherit-advisor/SKILL.md:13` 의 예시에 `\noptions: reqs` 가 항상 들어 있다. 모델은 예시를 그대로 복사한다.
   - 고칠 것: 예시에서 이 줄을 빼고, 21행에만 적는다.
3. **inherit 22행의 호출 시점이 사람의 턴 경계를 전제한다.** "Call it right after your latest response" 와 description 의 "before you act on a conclusion" 이 어긋난다.
   - 고칠 것: "Call it at the decision point, before the step it guards; the fork is cheap only while the cache is warm."
4. **inherit 23행의 tier off 규칙에 이유가 없다.** 확인 방법도 fresh 쪽에만 있다. 이유와 확인 방법을 적는다.
5. **fresh 의 brief 와 템플릿이 done 전용이다.** `SKILL.md:32` 와 `templates/brief.md:11` 이 그렇다. 33행 "Leave out … the reasoning behind your conclusion" 을 따르면 plan 에서 정작 봐야 할 접근이 brief 에서 빠진다.
   - 고칠 것: 종류별 주장을 한 줄씩 둔다. plan 은 the approach I am about to lock in, stuck 은 my current hypothesis.
6. **`/code-review` 와 겹친다.**
   - `agents/reviewer.md:31,36` 에서 done 리뷰어가 테스트를 돌리고 missing tests 까지 본다.
   - 커밋 훅(`nudge.py:141-145`)도 `/code-review` 와 같은 시점에 이 리뷰어를 권한다.
   - 고칠 것: done 은 말한 것 대 한 것, 요구 대조표, 다른 세션과 정본 동기화로 좁힌다. 결함 사냥은 `/code-review` 에 넘긴다.
7. **두 스킬의 정반대 지시에 이유가 한쪽에만 있다.** inherit 20행은 "Leave your suspicions out", fresh 34행은 "Include the part you are least sure about" 이다. fresh 쪽에 "the reviewer cannot see your doubts otherwise" 를 덧붙인다.
8. **불필요한 문장.** inherit 31행의 되풀이. fresh 16행은 사실을 적는 대신 "always pass model" 이라는 지시로 바꾼다. fresh 54행 Stats 는 rationale 로 옮긴다.
9. **장부 기록에 이유가 없다.** inherit 34행, fresh 47행. 자율 호출에서 가장 빠뜨리기 쉬운 단계다.
10. **fresh 26행 "do not relaunch it" 에 이유가 없다.** 반쪽 결과를 들고 어떻게 진행할지도 없다.

## 2. 사용자의 '전·후' 틀
- 절반은 맞다.
  - plan 시점은 훅이 잴 수 없고 description 도 말하지 않는다. 그래서 '확정 전' 검토는 아무도 밀지 않는다.
  - 커밋 직전 diff 검토는 `/code-review` 의 시점이다.
- 그러나 done 을 버리면 안 된다. "요청대로 됐다" 도 '내 견해'이고, 사용자 원문과 대조하는 것은 reviewer 뿐이다.
- 나누는 축은 시간이 아니라 질문이다. "내 견해가 맞나" 를 plan(접근)과 done(완료 주장)에서 묻는다. 스킬은 쪼개지 않는다.
- description 조건 제안: "Reach for it before you lock in an approach, or tell the user work is done, on a view only you have checked." stuck 은 훅이 맡는다.
- 판정할 시험: 접근 선택 직전 장면에서 plan 호출률. 각 N=10.

## 3. 가장 강하게 밀 변경
fresh-advisor description 에 접근 확정 전 시점을 넣고, done 을 "사용자 요구 대비 주장" 으로 좁혀 `/code-review` 와 가른다(1·5·6 을 함께 해결).
