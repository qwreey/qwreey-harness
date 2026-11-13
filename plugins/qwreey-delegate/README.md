# qwreey-delegate

이 플러그인을 켜면 Claude 가 다른 회사의 모델(Gemini `agy`, OpenAI `codex`)에게 좁은 질문 하나를 맡길 수 있다. "제미니한테도 물어봐", "codex랑 agy 써서 작명 논의해봐" 처럼 말하면 되고, Claude 가 같은 원인을 계속 놓친다고 볼 때 스스로 꺼내기도 한다. Claude 의 모델들(sonnet, opus)은 뿌리가 같아 어휘와 판단 습관을 공유하므로 "외부자 시선으로 봐" 라고 시켜도 같은 데서 막히기 쉽다. 다른 계열은 다른 각도에서 보지만 단정적으로 틀리는 일도 잦아서, 돌아온 답은 발견일 뿐 결정이 아니다. Claude 가 하나하나 확인한 뒤에만 쓰고, 새 이름이나 새 구조 같은 제안은 사용자에게 묻는다. 리뷰를 여러 차례 돌리거나 전체를 감사하는 일, 결정, 저장소에 그대로 넣을 결과에는 쓰지 않는다. 설정에 Linux 루트 권한이 필요해 비개발자 동료에게는 권하지 않는다.

## 무엇이 달라지나
- 맡기기 전에 무엇을 물을지 한 줄로 알린다. 답은 백그라운드로 돌고 끝나면 알림이 온다.
- 다른 모델은 저장소의 격리된 사본(worktree)에서 권한 없는 별도 사용자로 돈다. 원래 저장소를 고치거나 커밋할 수 없다.
- Claude 의 보고는 "다른 모델의 주장 / Claude 가 확인한 것 / 사용자가 정할 것" 으로 나눠 온다. 결함 주장은 재현 테스트부터 쓰고, 재현되지 않으면 그렇게 적는다.
- 같은 모델에는 동시에 한 건만 맡긴다(각 구독의 사용 한도를 아끼려고).

## 비용
- 늘 드는 것: 스킬 설명 한 줄(영문 약 800자). 훅 없음.
- 실행: Claude 쪽은 지시문 작성과 검증 정도. 본 비용은 각 벤더 구독 한도에서 나간다(agy 는 flash 만, codex 는 Plus 한도가 작아 사용자가 사용량을 확인).

## 요구 사항
- Linux, root(`setpriv`, 저장소별 uid, `choom`). Windows·macOS 불가.
- `agy` 또는 `codex` CLI 설치와 각자 구독. 저장소 루트에 `AGENTS.md`, uid 표 등록(`delegate.sh register`).
- uid 표 `registry.tsv` 는 고쳐 쓰므로 `HARNESS_DELEGATE_REGISTRY`(`~/.claude/harness.env`)가 이 클론의 `skills/delegate/registry.tsv` 를 가리켜야 한다.

## 끄기
- `claude plugin disable qwreey-delegate@claude-doctor-market` (제거는 `uninstall`). 훅이 없어 끄면 바로 멈춘다.

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-delegate@claude-doctor-market
```

자세한 동작(격리 방식, 실행 흐름, 설정 변수, 작업 폴더): [docs/how-it-works.md](docs/how-it-works.md)
