# qwreey-workspace

여러 저장소에서 세션을 동시에 여러 개 돌릴 때 쓰는 플러그인이다. 켜 두면 Claude 는 이 세션이 맡은 저장소 밖의 다른 저장소를 읽기만 한다. 다른 저장소를 참고로 읽는 것은 자유롭지만, 고치려 하면 먼저 막히고 어느 저장소의 어느 파일을 바꿀지 사용자에게 묻는다. 다른 세션이 그 저장소에서 일하는 중일 수 있어서, 모르는 사이에 덮어쓰거나 누가 쓰고 있는 worktree(작업용 사본 폴더)를 지우는 사고를 막으려는 것이다. 공용 지식은 `*-kb` 저장소를 먼저 보게 해서 같은 것을 저장소마다 다시 찾지 않게 한다.

저장소가 어디에 있든(문서함, 바탕 화면, 아무 폴더) 따로 정할 것이 없다. "다른 저장소" 는 이 세션 저장소 밖의 git 저장소 전부이고, 지도에 보이는 목록은 이 기기에서 Claude Code 를 연 폴더(세션 기록)에서 자동으로 모은다. 못 찾은 것은 설정에서 더하고, 보기 싫은 것은 뺀다.

## 무엇이 달라지나
- 다른 저장소를 고쳐야 할 때 Claude 가 먼저 묻는다. 승인하면 그 범위만 고치고, 따로 말하지 않으면 거기서 커밋·푸시하지 않으며, 무엇을 바꿨는지 알려 준다.
- 다른 저장소를 처음 읽을 때 "읽기는 괜찮고, 고치려면 승인이 필요하다" 는 알림이 한 번 붙는다.
- 이 기기의 저장소 목록을 한 줄씩(`*-kb` 먼저) 보고 어디에 무엇이 있는지 찾는다.
- worktree 를 지우기 전에 잠금 파일과 지금 돌고 있는 세션을 확인하고, 쓰는 중이면 지우지 않고 묻는다.
- 세션을 시작할 때(startup, resume, clear. compact 뒤에는 아님) 이 저장소에 오래(기본 14일) 손대지 않은 worktree 가 있으면 Claude 에게 한 줄 알린다. 잠긴 것과 지금 세션이 안에서 돌고 있는 것은 빼고, 폴더가 이미 사라진 등록(prunable)은 따로 적는다. Claude 는 정리할 만한지 보고 지우기 전에 잠금·세션을 확인한 뒤 사용자에게 묻는다. 훅은 git 을 읽기만 하고 아무것도 지우지 않는다. 세션마다 한 번.
- 이 저장소 기록(`.claude/` 아래)에 다른 저장소의 내부(파일 경로 등)를 적으려 하면, Claude 가 이 저장소가 그 내용을 정말 필요로 하는지(의존 관계)와 그 저장소가 이 저장소만큼 공개인지(remote, LICENSE)를 확인하고, 모르면 사용자에게 묻는다. 아니면 결론만 남긴다. 상시 규약 한 줄에 더해, 기록에 다른 저장소 안 경로가 실제로 들어가면 그 순간 한 줄 알림이 붙는다(파일·저장소마다 한 번).
- 서브에이전트에도 같은 규칙이 실리고, 같은 게이트가 서브에이전트의 쓰기도 막는다.

## 비용
- 늘 드는 것: 규약 네 줄(약 220 토큰)과 스킬 설명 한 줄(약 400자). 훅은 모델을 부르지 않는 짧은 파이썬이다(게이트는 도구 호출마다 약 10 ms, 다른 저장소를 건드릴 때 약 20 ms).
- 오래된 worktree 가 있을 때만: 세션 시작에 한 줄(약 100~200 토큰). 세션 시작마다 git 명령 서너 번(보통 0.1초 안팎, 최대 몇 초로 묶음).

## 요구 사항
- 쓰기 게이트와 형제 저장소 경로 알림은 Rust 바이너리 `native/qwreey-workspace` 를 부른다. 지금은 저장소에서 `cargo build --release -p qwreey-workspace` 로 만들어 그 자리에 복사해야 하고, 없으면 그 훅들이 아무것도 하지 않는다(막지 않는 오류이고, 쓰기 게이트도 서지 않는다). 바이너리는 아직 Linux 판만 있다.
- 세션 시작 안내와 오래된 worktree 알림은 순수 Python 3 이라 OS 무관. 스킬의 살아 있는 세션 확인 명령은 Linux `/proc`, macOS `lsof`.

## 설정
`/plugin configure qwreey-workspace@qwreey-harness` 또는 `/config` 의 플러그인 옵션에서 고친다.

| 옵션 | 기본 | 뜻 |
|---|---|---|
| `harness_workspace_extra` | 없음 | 목록에 더할 저장소, 또는 저장소를 담은 폴더(바로 아래 저장소를 모두). `;` 로 구분. 예: `~/Projects; C:\Users\me\Documents\Projects` |
| `harness_workspace_exclude` | 없음 | 목록에서 뺄 저장소 경로(그 아래 포함)나 `*` 패턴. 뺀 저장소는 게이트도 막지 않는다. 임시 폴더, `~/.cache`, `.claude/worktrees` 아래는 이미 빠진다. 예: `~/scratch; */old-*` |
| `harness_workspace_gate` | 켬 | 다른 저장소 쓰기 게이트 |
| `harness_workspace_sibling_notice` | 켬 | 기록에 다른 저장소 내부 경로를 적을 때의 알림 |
| `harness_workspace_stale_worktrees` | 켬 | 세션 시작의 오래된 worktree 알림 |

- 게이트와 저장소 목록 옵션은 클론한 저장소의 파일로 바꿀 수 없다(남의 저장소가 게이트를 끄지 못하게).
- 한 프로젝트에서만 끄려면: 그 저장소 `.claude/settings.json` 의 `enabledPlugins` 로 끈다.
- 전부 끄기: `claude plugin disable qwreey-workspace@qwreey-harness`.
- 고급: harness.env(`~/.claude/harness.env`, 저장소 `.claude/harness.env`) 에 같은 이름의 대문자 키(`HARNESS_WORKSPACE_GATE=off` 등)와 튜닝 값(`HARNESS_WORKSPACE_STALE_WORKTREE_DAYS`, 상시 안내 `HARNESS_WORKSPACE_AMBIENT=off`)을 둘 수 있다. 옛 `HARNESS_WORKSPACE`(작업공간 폴더)는 그 아래 저장소를 목록에 더하는 데만 쓰인다.

## 설치
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-workspace@qwreey-harness
```

자세한 동작(넣는 규약, 쓰기 판정, 상태 파일, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
