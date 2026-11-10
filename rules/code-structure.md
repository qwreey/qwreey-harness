---
paths:
  - "**/*.luau"
  - "**/*.lua"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.go"
---
# 코드 구조 (파일 길이·폴더·데이터)

> 정책: 확정(D-13, 사용자 결정 2026-11-10). 저장소의 `.claude/rules/`·`conventions.md`·`.claude/structure.json` 이 다르게 정하면 그쪽을 따른다.

- 기능을 더하기 전에 대상 파일의 줄 수를 본다. 800줄을 넘으면 떼어 낼 묶음을 작업 보고에 한 줄로 적고, 1,500줄을 넘으면 덧붙이기 전에 분리안을 사용자에게 묻는다(테스트는 두 배, 생성물·순수 데이터 모듈 제외). 분리안은 `split-plan.py` 로 묶음을 뽑아 다듬는다. → [structure§2](../skills/luau-style/references/structure.md), [splitting§0](../skills/luau-style/references/splitting.md)
- 확실한 이유(타입 한계, 생성물, 순수 데이터)로 기준을 넘겨 둘 때는 파일 머리 `--@structure-exempt: <사유>` 나 `structure.json` 의 `exempt` 에 이유를 남긴다. 이유 없는 예외("나중에", "귀찮아서")는 두지 않는다. → [structure§2a](../skills/luau-style/references/structure.md)
- 나눌 때는 "옮기기만" 커밋을 먼저 하고 고치기는 다음 커밋에 한다. 옮긴 뒤에는 문서의 옛 경로를 고치고 이음매 감사를 돌린다. → [structure§4](../skills/luau-style/references/structure.md)
- 같은 폴더에 같은 접두를 가진 파일이 셋 이상이 되면 `접두/` 폴더(입구 `init.luau`)로 묶는다. 한 폴더에 종류가 다른 소스가 15개를 넘으면 묶음을 제안한다. → [structure§5](../skills/luau-style/references/structure.md)
- 항목마다 모양이 같은 것(요청 이름·인자·비용·권한, 세트 배치)은 한 곳의 표로 두고 코드는 그 표를 읽는다. 같은 변수를 문자열로 8갈래 넘게 분기하면 표로 바꿀지 본다. → [structure§6](../skills/luau-style/references/structure.md)
- 툴이 만든 데이터는 생성기 경로와 "손으로 고치지 않는다" 머리를 단 별도 파일에 둔다. 다른 패키지에서 복사한 파일에는 원본 경로를 적고 같은지 보는 검사를 둔다. → [structure§6](../skills/luau-style/references/structure.md)
