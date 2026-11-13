# qwreey-workspace

같은 작업공간에 형제 저장소가 여럿일 때, 이 세션의 저장소 밖을 읽기 전용으로 지키는 게이트와 지도 플러그인.

## 무엇을 하나
- 세션·서브에이전트 시작에 규약 세 줄을 넣는다(형제 저장소는 승인 없이 고치지 않음, 지식은 `*-kb` 먼저, worktree 삭제 전 잠금 확인).
- 훅 `workspace_gate.py`: `HARNESS_WORKSPACE/<X>` 의 형제 저장소에 쓰기(Edit·Write, 쓰기로 분류된 Bash)가 오면 스킬 `qwreey-workspace:workspace` 를 로드하기 전까지 거절한다. 읽기는 compact 회차마다 한 번 알린다.
- 스킬 `qwreey-workspace:workspace`: 형제 저장소 한 줄 지도(`*-kb` 먼저), 살아 있는 세션 확인, worktree 잠금 확인, 승인 뒤 절차.

## 비용
- 상시 로드: 규약 세 줄(약 150 토큰)과 스킬 설명 한 줄(약 400자). 훅 두 종류: 거의 모든 도구 호출 전(PreToolUse 넓은 matcher)에 파이썬이 잠깐 돌고(순수 문자열 판정, 모델 호출 없음), Skill 호출 뒤와 슬래시 확장에 한 번씩 돈다.

## 효과
- 다른 세션이 작업 중인 형제 저장소를 실수로 덮어쓰거나 worktree 를 지우는 사고를 막는다.

## 왜 택하나, 누구에게 안 맞나
- 택한다: 저장소 여러 개를 한 작업공간(`HARNESS_WORKSPACE`)에 두고 세션을 동시에 여러 개 돌릴 때.
- 안 맞는다: 단일 저장소, `HARNESS_WORKSPACE` 를 설정하지 않는 경우(설정이 없으면 게이트는 꺼진다).

## 요구 사항
- 훅은 순수 Python 3 이라 OS 무관. 스킬의 live-session 확인 명령은 Linux `/proc`, macOS `lsof`.
- `~/.claude/harness.env` 의 `HARNESS_WORKSPACE`(작업공간 루트).

## 끄기
- 게이트만: `HARNESS_WORKSPACE_GATE=off`. `HARNESS_WORKSPACE` 가 비어도 꺼진다.
- 전부: `claude plugin disable qwreey-workspace@claude-doctor-market`.

## 설치
```bash
claude plugin install qwreey-workspace@claude-doctor-market
```
테스트: `python3 -I plugins/qwreey-workspace/tests/test_workspace_gate.py`
