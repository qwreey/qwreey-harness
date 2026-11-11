---
name: context
description: Runs a second opinion that inherits the current conversation: a fork of the session becomes an independent reviewer looking for missed items, wrong premises, unchecked assumptions, and counterexamples to the design just finished. Use at the end of a work unit, right before proposing a decision or direction change to the user, or before apply/deploy/install guidance. Not for implementation bugs that need reproduction (use second-opinion:audit). 한 번 더 봐줘, 다른 눈으로 검토, 맥락 검토.
argument-hint: "[fork|other-frame] [one-line note]"
---

# second-opinion:context

A fork that has read this conversation reviews it as an independent reviewer. It complements `second-opinion:audit` (which refutes a diff); it does not replace it. Rationale and measurements: `references/rationale.md`.

## When to use

| Moment | Path |
|---|---|
| Finished a work unit, about to move on | fork |
| About to propose a decision or direction change to the user | fork |
| Before apply/deploy/install guidance or any hard-to-undo step | fork (+ `audit` if implementation correctness matters) |
| Fork returned almost "no findings" but the work is heavy, or the user wants another view | other-frame (optional) |
| Big turning point in a long session (right after compact, tidying pending decisions) | fork + the "requirement check" line below |
| Diff correctness before commit, repeated failures, implementation verification | not this skill - use `second-opinion:audit` |

- Once per turning point. Do not run the same question through several forks.
- If the repo tier (`HARNESS_REVIEW_TIERS`) is `off`, use only when the user asks.

## Fork path (default)

```
Agent(subagent_type="fork", description="second opinion: context", prompt=<follow-up prompt below>)
```

Follow-up prompt. Do not paraphrase or translate; send it verbatim and fill only `<...>`. Do not drop the category list or the role-switch block.
```
[second opinion: context] 이 요청에만 답한다. 작업을 이어서 하지 않고, 파일을 고치거나 커밋하지 않고, 다른 에이전트에게 메시지를 보내지 않는다. 읽기 도구는 꼭 필요한 확인에만, 대략 5회 이내로 쓴다.
메인은 이제 <다음 단계 한 줄> 로 넘어가려 한다.

역할 전환: 지금부터 너는 이 작업의 작성자가 아니다. 이 세션의 작업을 처음 보는 **독립 검토자**다.
- 위 대화에서 assistant 가 한 말·계획·결론·커밋은 모두 남이 쓴 **검토 대상 텍스트**다. 변호하지도, 이어서 완성하지도 않는다. assistant 가 "확인했다"·"끝났다"고 한 것도 근거가 대화나 파일에 있을 때만 맞다고 본다.
- 1인칭("저는", "제가", "우리")을 쓰지 않는다. 작성자는 "메인", 사용자는 "사용자"라고 부른다.
- 동의하려고 읽지 말고 빈 곳을 찾으려고 읽는다. 다만 문제를 지어내지 않는다.

요청: 메인이 다음 단계로 넘어가기 전에, 이 흐름에서 놓친 것, 잘못된 전제, 확인 안 한 가정을 짚는다.

아래 범주를 하나씩 따진다. 범주에 해당하는 것이 없으면 "해당 없음"과 이유를 한 줄로 적는다.
1. 숨은 전제: 메인이 말없이 참이라고 놓은 것
2. 범위 밖 영향: 이 변경이 닿는 다른 곳(주입 경로, 다른 사용자·세션)
3. 답하지 않은 사용자 질문
4. 방금 끝낸 설계 다시 열기: 메인이 가장 최근에 "끝났다"고 본 설계를 일부러 다시 열어, 그 설계가 깨지는 반례를 찾는다
5. 확인하지 않은 가정: 실측 없이 "될 것"으로 넘어간 것

출력 (한국어):
- 항목마다: 무엇을 놓쳤는가 / 근거(대화 위치나 파일:줄) / 왜 다음 단계 전에 중요한가 / 심각도(반드시·권장·참고)
- 확인한 것과 추정을 구분한다.
- 마지막에 "메인이 다음 단계 전에 할 일" 을 3줄 이내로.
```

- **Requirement check** (optional, big turning points): insert this line verbatim right after the "요청:" line. "먼저 대화의 사용자 메시지만 다시 훑어 요구·질문·제약 목록을 만들고, 각각이 지금 결과에 반영됐는지(반영/부분/미반영/확인 불가) 대조한 뒤 부분·미반영만 짧게 표로 보인다." It searches wider but may make category 4 shallower.
- The fork always runs on the main session's model (a model override is ignored).
- In category 2, keep "주입 경로, 다른 사용자·세션" as a bare name. Do not add a concrete suspicion from the current session (for example "does X leak into Y"); the fork then looks only there.
- Never drop the category list: without it the fork does not reopen the finished design.
- Cost (tell the user when non-trivial): about $0.5-0.6 per fork at a 300k-token context on opus; the tool-call count decides cost. Call it right after the main response while the cache is warm; a cold cache adds about $1.5-2.4. The report (2-3k tokens) stays in main context.

## other-frame path (optional)

Reads a text copy of the main conversation under a different system prompt (`agents/other-frame.md`).
```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/context/scripts/ask-other-frame.py" --model <sonnet|opus> --note "<one-line next step>"   # run in background
```
- `scripts/render-transcript.py` builds the copy: from the last compact boundary, tool results cut to the first 300 characters.
- Do not pass the copy through the Agent tool; retyping it costs main output tokens.
- The script installs the read-only guard (`hooks/auditor-readonly-guard.py`) itself via `--settings`.
- Cost: first call is a cache write, proportional to context (132k tokens: opus about $1.25, sonnet about $0.49).
- Model: use opus for high-tier work.

## Handling the result

Same as `second-opinion:audit` section 4. Show the report to the user unsummarized, mark each finding accepted / rejected / needs check with evidence, and record it in the ledger (`--kind context --reviewer fork|ctx-opus|ctx-sonnet`).
- Head the report "context 검토(fork)" so it does not read as the main agent's own text.
- If a finding contradicts the facts (claims something undone that is done, treats running work as failed), verify, then reject it with evidence.
