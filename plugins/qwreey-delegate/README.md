# qwreey-delegate

이 플러그인을 켜면 Claude 가 다른 회사의 모델(Gemini `agy`, OpenAI `codex`)에게 좁은 질문 하나를 맡길 수 있다. "제미니한테도 물어봐", "codex랑 agy 써서 작명 논의해봐" 처럼 말하면 되고, Claude 가 같은 원인을 계속 놓친다고 볼 때 스스로 꺼내기도 한다. Claude 의 모델들(sonnet, opus)은 뿌리가 같아 어휘와 판단 습관을 공유하므로 "외부자 시선으로 봐" 라고 시켜도 같은 데서 막히기 쉽다. 다른 계열은 다른 각도에서 보지만 단정적으로 틀리는 일도 잦아서, 돌아온 답은 발견일 뿐 결정이 아니다. Claude 가 하나하나 확인한 뒤에만 쓰고, 새 이름이나 새 구조 같은 제안은 사용자에게 묻는다. 리뷰를 여러 차례 돌리거나 전체를 감사하는 일, 결정, 저장소에 그대로 넣을 결과에는 쓰지 않는다. 설정에 Linux 루트 권한이 필요해 비개발자 동료에게는 권하지 않는다.

## 무엇이 달라지나
- 맡기기 전에 무엇을 물을지 한 줄로 알린다. 답은 백그라운드로 돌고 끝나면 알림이 온다.
- 다른 모델은 저장소의 격리된 사본(worktree)이나 빈 폴더에서, 저장소·모델마다 따로 둔 권한 없는 사용자로 돈다. 원래 저장소를 고치거나 커밋할 수 없다.
- 작업 폴더와 결과는 저장소 옆이 아니라 상태 폴더(기본 `~/.local/state/qwreey-delegate`)에 생긴다. 끝나면 보고서·변경분·로그를 결과 폴더(`runs/<저장소>/<날짜>-<이름>/`)에 모아 확인한 뒤 작업 폴더를 지운다. 결과는 14일 뒤 정리 명령(`gc`)이 지우므로, 남길 보고서는 Claude 가 검증을 붙여 저장소 `.claude/audit/` 로 옮긴다.
- Claude 의 보고는 "다른 모델의 주장 / Claude 가 확인한 것 / 사용자가 정할 것" 으로 나눠 온다. 결함 주장은 재현 테스트부터 쓰고, 재현되지 않으면 그렇게 적는다.
- 같은 모델에는 동시에 한 건만 맡긴다(각 구독의 사용 한도를 아끼려고). agy 와 codex 는 동시에 돌 수 있다.

## 비용
- 늘 드는 것: 스킬 설명 한 줄(영문 약 800자). 훅 없음.
- 실행: Claude 쪽은 지시문 작성과 검증 정도. 본 비용은 각 벤더 구독 한도에서 나간다(agy 는 flash 만, codex 는 Plus 한도가 작아 사용자가 사용량을 확인).

## 요구 사항
- Linux, root(`setpriv`, 저장소·모델별 uid, `choom`), Python 3.11 이상. Windows·macOS 와 root 가 없는 Linux 에서는 실행을 거절한다(모드와 상관없이). root 없이 도는 판은 계획 중이다(`.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/driver-design.md` M3).
- `agy` 또는 `codex` CLI 설치와 각자 구독. 저장소 루트에 `AGENTS.md`, uid 표 등록(`python3 -I <스킬>/scripts/delegate.py register <저장소>`, 처음에는 Claude 가 알리고 한다).
- uid 표는 등록할 때 고쳐 쓰므로 내가 가진 파일이어야 한다. 아래 설정의 "uid 표 파일" 에 경로를 적으면 처음 등록할 때 만든다. 비워 두면 플러그인에 든 표를 읽기만 하고 등록은 거절한다(플러그인을 갱신하면 그 폴더가 바뀐다).

## 설정
`/plugin configure qwreey-delegate@claude-doctor-market` 또는 `/config` 의 플러그인 설정에서 바꾼다.
- uid 표 파일(`harness_delegate_registry`): 비우면 플러그인에 든 표(읽기만).
- agy 모델(`harness_delegate_agy_model`, 기본 `gemini-3.8-flash-high`), codex 모델(`harness_delegate_codex_model`, 기본 `gpt-6-luna`). 저장소 `.claude/harness.env` 가 바꿀 수 있고 `run --model` 이 이긴다.
- agy 실행 파일(`harness_delegate_agy_bin`), codex 실행 파일(`harness_delegate_codex_bin`): 비우면 PATH 에서 찾는다.
- 고급: 동시 실행 수, 결과 보존 일수, 상태 폴더, 격리 스위치는 `~/.claude/harness.env` 키다(저장소 파일로는 바꾸지 못함). 목록은 [docs/how-it-works.md](docs/how-it-works.md).

## Windows·비개발자 동료
- 이 delegate 는 Linux root 가 필요해 Windows 동료에게는 맞지 않는다. 현실적인 선택은 OpenAI 공식 플러그인 codex-plugin-cc(Apache-2.0, https://github.com/openai/codex-plugin-cc)다. 설치는 저장소 README 의 줄을 따른다(`claude plugin marketplace add openai/codex-plugin-cc`, `claude plugin install codex@openai-codex`, 그다음 `/codex:setup`).
- Stop-gate(리뷰 게이트)는 켜지 않는다. 턴마다 Codex 를 불러 비용이 계속 나간다.
- `/codex:rescue` 는 기본으로 저장소에 직접 쓴다. 쓰면 안 되는 일이면 읽기 전용으로 시키거나 `/codex:review` 를 쓴다.
- 결과는 검증 없이 원문 그대로 나온다. Claude 에게 "이 결과 확인해줘" 라고 따로 시켜야 한다.
- 둘은 함께 설치할 수 있다. 겹치는 점: 같은 Codex 사용 한도를 나눠 쓰고, "코덱스한테 물어봐" 에 양쪽이 다 후보가 된다. 격리와 검증이 필요하면 delegate, 읽기 전용 리뷰는 공식 플러그인으로 나누면 된다.

## 끄기
- `claude plugin disable qwreey-delegate@claude-doctor-market` (제거는 `uninstall`). 훅이 없어 끄면 바로 멈춘다. 상태 폴더에 남은 결과는 지우지 않으니 필요 없으면 손으로 지운다.

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-delegate@claude-doctor-market
```

자세한 동작(격리 방식, 실행 흐름, 설정 변수, 작업 폴더): [docs/how-it-works.md](docs/how-it-works.md)
