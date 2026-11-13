# qwreey-workspace

여러 저장소를 한 작업공간 폴더에 두고 세션을 동시에 여러 개 돌릴 때 쓰는 플러그인이다. 켜 두면 Claude 는 이 세션이 맡은 저장소 밖을 읽기만 한다. 다른 저장소를 참고로 읽는 것은 자유롭지만, 고치려 하면 먼저 막히고 어느 저장소의 어느 파일을 바꿀지 사용자에게 묻는다. 다른 세션이 그 저장소에서 일하는 중일 수 있어서, 모르는 사이에 덮어쓰거나 누가 쓰고 있는 worktree(작업용 사본 폴더)를 지우는 사고를 막으려는 것이다. 공용 지식은 `*-kb` 저장소를 먼저 보게 해서 같은 것을 저장소마다 다시 찾지 않게 한다. 작업공간 폴더(`HARNESS_WORKSPACE`)를 정하지 않았거나 저장소가 하나뿐이면 아무 일도 하지 않는다.

## 무엇이 달라지나
- 다른 저장소를 고쳐야 할 때 Claude 가 먼저 묻는다. 승인하면 그 범위만 고치고, 따로 말하지 않으면 거기서 커밋·푸시하지 않으며, 무엇을 바꿨는지 알려 준다.
- 다른 저장소를 처음 읽을 때 "읽기는 괜찮고, 고치려면 승인이 필요하다" 는 알림이 한 번 붙는다.
- 작업공간의 저장소 목록을 한 줄씩(`*-kb` 먼저) 보고 어디에 무엇이 있는지 찾는다.
- worktree 를 지우기 전에 잠금 파일과 지금 돌고 있는 세션을 확인하고, 쓰는 중이면 지우지 않고 묻는다.
- 서브에이전트에도 같은 규칙이 실리고, 같은 게이트가 서브에이전트의 쓰기도 막는다.

## 비용
- 늘 드는 것: 규약 세 줄(약 150 토큰)과 스킬 설명 한 줄(약 400자). 훅은 모델을 부르지 않는 짧은 파이썬이다.

## 요구 사항
- 훅은 순수 Python 3 이라 OS 무관. 스킬의 살아 있는 세션 확인 명령은 Linux `/proc`, macOS `lsof`.
- `~/.claude/harness.env` 의 `HARNESS_WORKSPACE`(작업공간 루트).

## 끄기
- 게이트만: `HARNESS_WORKSPACE_GATE=off`. `HARNESS_WORKSPACE` 가 비어도 꺼진다.
- 상시 안내만: `HARNESS_WORKSPACE_AMBIENT=off`.
- 한 프로젝트에서만: 그 저장소 `.claude/settings.json` 의 `enabledPlugins` 로 끄거나, 상시 안내 스위치를 그 저장소 `.claude/harness.env`(팀 공유, 커밋)나 `.claude/harness.local.env`(나만, `.gitignore` 에 넣는다), 또는 settings 의 `env` 에 둔다. local 이 공유 파일을 이기고 환경 변수가 둘 다 이긴다. 게이트 스위치와 `HARNESS_WORKSPACE` 는 저장소 파일로 바꿀 수 없다(클론한 저장소가 게이트를 끄지 못하게).
- 전부: `claude plugin disable qwreey-workspace@claude-doctor-market`.

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-workspace@claude-doctor-market
```

자세한 동작(넣는 규약, 쓰기 판정, 상태 파일, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
