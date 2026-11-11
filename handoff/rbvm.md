# rbvm 세션에게: 프로젝트 settings 의 `git push` deny 제거 제안

- 위치: `rbvm/.claude/settings.json:25` 의 `"Bash(git push:*)"`(`permissions.deny`).
- 근거: 사용자 메모리 원칙 "git push / .env deny 는 이 sandbox 에서 부적절"(git 계정은 에이전트 전용, 사용자가 pull 해서 업스트림에 push). 사용자 레벨 deny 는 이미 뺐다. 2026-11-11 사용자가 "추천대로"로 승인했다.
- 요청: 그 한 줄을 빼는 것을 검토해 반영한다. `git remote add` 와 `Read(./.git/config)` deny 는 이 안건이 아니다. (claude-doctor 는 읽기만 했고 수정하지 않았다.)
