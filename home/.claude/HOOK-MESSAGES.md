# 훅 메시지 규약 (모델에게 들어가는 텍스트)

MANIFEST 대상 아님. 근거 실측: `audit/17-hook-messages.md`. 세션 기록 플러그인 등 새 훅도 이 규약을 따른다.

## 규칙
1. **영어, 짧게.** 모델이 읽고 행동을 바꾸는 텍스트(additionalContext, deny 사유)는 영어. 문서·주석·사용자 대상 안내는 한국어.
2. **감싼다.** 본문 전체를 `<harness-hook name="<훅 이름>">\n…\n</harness-hook>` 한 덩어리로 감싼다. `[hook-name]` 접두는 쓰지 않는다.
   - 실측: 하네스는 additionalContext 를 `<system-reminder>` 로 감싸지 **않고**(트랜스크립트 `rendered` 에만 있음), `PreToolUse:Bash hook additional context: ` 접두만 붙여 system 위치로 넣는다. SessionStart·UserPromptSubmit 은 사용자 턴 안에 일반 텍스트로 붙는다. 그래서 우리 태그가 필요하다.
3. **배경 설명은 사용자 레벨 CLAUDE.md 정본(`home/.claude/CLAUDE.md` "훅 메시지")에 2줄.** 태그 안에서 반복하지 않는다.
4. 본문은 지시가 아니라 **관찰 + 권고**로 쓴다(무엇이 일어났는지, 왜 중요한지, 할 일). 의미 없는 인사·반복 금지.
5. **deny 사유** (`permissionDecisionReason`)도 같은 태그로 감싼 영어. 모델에게는 `<error>PreToolUse:Bash hook error: …</error>` 도구 결과로 들어간다.
6. PreToolUse/PostToolUse 의 **일반 stdout 은 모델에게 가지 않는다**(실측). 모델에게 보일 말은 JSON `additionalContext` 로 낸다.

## dedup 단위 = session_id + compact 회차
"세션당 한 번" 알림은 session_id 만 키로 쓰면 안 된다. `/compact` 는 session_id 를 유지하는데 요약 과정에서 이전 알림이 맥락에서 사라진다(실측).
- 공용 함수: `~/.claude/lib/compact_epoch.py` (정본 `home/.claude/lib/compact_epoch.py`)
  - `state_path(namespace, session_id)` → `$TMPDIR/<namespace>/<sid>.c<회차>.json`. 디렉터리도 만든다.
  - `epoch(session_id)`, `bump(session_id)`.
- 회차는 `hooks/rearm-on-compact.py` 가 SessionStart(matcher `compact`)에서 올린다(settings.json 에 등록됨). 실측: compact 때 PreCompact → SessionStart(source=compact) → PostCompact 가 모두 불리고 session_id 는 같다.
- 사용(경로로 모듈 적재, harness_env 와 같은 방식):
  ```python
  spec = importlib.util.spec_from_file_location("compact_epoch", home / "lib" / "compact_epoch.py")
  ce = importlib.util.module_from_spec(spec); spec.loader.exec_module(ce)
  state_file = ce.state_path("claude-my-hook", data["session_id"])
  ```
  구현 예: `hooks/bash-bypass-reminder.py` 의 `dedup_path`. lib 가 없으면 session_id 키로 되돌아간다.
- 테스트: `hooks/tests/test-compact-rearm.py`.
- 참고: 회차가 오르면 structure-reminder 의 "이번 세션 성장" 기준점도 새로 잡힌다.
