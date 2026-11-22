# qwreey-operator

이 플러그인을 켜면 메인 대화의 Claude 는 사용자와 이야기하고 판단하는 쪽에 머물고, 큰 구현은 백그라운드 서브에이전트에게 맡긴다. 코드 파일 3개 이상, 새로 쓸 줄 150줄 이상, 다른 코드나 문서를 많이 읽어야 하는 구현이 그 기준이다. 구현이 도는 동안에도 같은 대화에서 다음 일을 의논할 수 있고, 새로 뜬 수행자는 메인의 설계 가정을 물려받지 않아 같은 착각을 되풀이하지 않는다. 그렇다고 늘 넘기지는 않는다. 작은 수정, 방금 정한 결정 반영, 문서와 설정, 중간에 사용자 답이 필요한 일, 그리고 설계가 되는지부터 시험해 보는 일은 메인이 사용자와 직접 한다. 강제로 막는 장치는 없고, 규약 몇 줄과 알림 하나로 이렇게 움직이도록 이끈다.

## 무엇이 달라지나
- 큰 구현을 시키면 "무엇을, 몇 개, 어떤 모델로, 어느 정도 크기" 를 한 줄로 알리고 백그라운드로 돌린다. 그동안 계속 말을 걸 수 있다.
- 백엔드와 프론트엔드처럼 서로 독립된 부분은 에이전트를 하나씩 붙여 동시에 돌린다. 동시에 몇 개까지 돌릴지 정해 두었으면 그 수를 지킨다.
- 맡길 때 사용자가 한 말을 그대로 넘기고, 애매한 점은 수행자가 혼자 정하지 말고 질문으로 보고하게 한다. 결과는 메인이 테스트를 다시 돌려 확인하고, 큰 변경은 새 리뷰어에게 한 번 더 보인 뒤 메인이 커밋한다.
- 메인이 한 턴에 코드를 많이 직접 쓰기 시작하면(쓰기 12회 또는 파일 8개) "맡기는 게 낫지 않나" 다시 판단하라는 알림이 한 번 뜬다. 거의 끝난 일이면 그대로 마친다.
- 서브에이전트가 자기가 띄운 백그라운드 명령이나 자식 에이전트를 돌려 둔 채 보고를 마치려 하면, 그것들을 거두거나 멈춘 뒤 보고를 다시 내라는 알림이 그 서브에이전트에게 한 번 간다. 메인 대화에는 보이지 않는다.
- 작은 일까지 서브에이전트로 돌리지 않는다. 지시문을 쓰는 품이 일보다 크면 메인이 바로 한다.

## 비용
- 늘 드는 것: 규약 다섯 줄(약 550 토큰)과 모델을 부르지 않는 가벼운 훅 둘. 끝맺음 알림이 울리면 그 서브에이전트가 한 턴 더 돈다.
- 이득은 돈이 아니라 시간과 대화다. opus 수행자에게 넘겨도 비용은 메인이 직접 할 때와 거의 같다. 기본 수행자를 opus 로 두는 것은 싼 모델이 시행착오를 거듭하며 시간과 토큰을 더 쓰고 결과도 나빠지기 쉬워서다. sonnet 은 틀려도 싸고 금방 보이는 가벼운 일에만 쓴다.

## 요구 사항
- Claude Code 서브에이전트가 도는 곳이면 어디서나(구독만으로 충분, 다른 벤더 불필요). Linux·macOS·Windows.
- 세션 시작 안내 훅이 `python3` 를 부른다. Windows 는 Python 3 설치가 필요하다.
- 위임 알림과 서브에이전트 백그라운드 작업 알림은 Rust 바이너리 `native/qwreey-operator` 를 부른다. 지금은 저장소에서 `cargo build --release -p qwreey-operator` 로 만들어 그 자리에 복사해야 하고, 없으면 그 훅들이 아무것도 하지 않는다(막지 않는 오류). 바이너리는 아직 Linux 판만 있다.

## 설정
`/plugin configure qwreey-operator@qwreey-harness` 또는 `/config` 의 플러그인 설정에서 바꾼다.
- 위임 권유 알림(`harness_operator_nudge`, 기본 켜짐).
- 서브에이전트 남은 작업 알림(`harness_operator_subagent_bg`, 기본 켜짐).
- 규약 주입 스위치는 옵션 "상시 규약 싣기"(`harness_operator_ambient`, harness.env 의 `HARNESS_OPERATOR_AMBIENT=off` 도 된다). 고급: 알림 문턱 `HARNESS_OPERATOR_NUDGE_WRITES`, `HARNESS_OPERATOR_NUDGE_FILES` 는 환경 변수다. 목록은 [docs/how-it-works.md](docs/how-it-works.md).

## 끄기
- 알림만: 위 설정에서 끈다.
- 규약 주입만: `/plugin configure qwreey-operator@qwreey-harness` 에서 "상시 규약 싣기"를 끈다.
- 한 프로젝트에서만: 그 저장소 `.claude/settings.json` 의 `enabledPlugins` 로 끄거나, 스위치를 그 저장소 `.claude/harness.env`(팀 공유, 커밋)나 `.claude/harness.local.env`(나만, `.gitignore` 에 넣는다), 또는 settings 의 `env` 에 둔다. local 이 공유 파일을 이기고 환경 변수가 둘 다 이긴다.
- 전부: `claude plugin disable qwreey-operator@qwreey-harness` (제거는 `uninstall`).

## 설치
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-operator@qwreey-harness
```

자세한 동작(넣는 규약, 알림 조건과 문턱, 실측 근거, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
