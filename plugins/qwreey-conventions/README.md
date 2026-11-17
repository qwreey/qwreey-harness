# qwreey-conventions

이 플러그인을 켜면 Claude 가 남기는 코드 주석과 CLAUDE.md·스킬 같은 모델용 문서가 덜 지저분해진다. 주석에는 "지금 왜 이렇게 되어 있나" 만 남고 날짜, 작업 이력, 결정 번호는 커밋 메시지로 간다. 이력이 쌓인 주석은 읽는 사람에게 잡음이고, 모델용 문서는 매번 읽히므로 한 줄 한 줄이 비용이기 때문이다. 같은 값이 여러 곳에 복사돼 어긋나거나 한 파일이 끝없이 길어지는 것도 일찍 알린다. 쓰는 법은 규칙 파일이 맡고, 훅은 방금 추가한 줄이 벗어난 것 같을 때만 Claude 에게 그 줄과 고치는 법을 한 줄로 알린다. 답변 언어를 빼면 막지 않으며, 기존 줄을 몰래 일괄 정리하지도 않는다.

## 무엇이 달라지나
- 주석이나 모델용 문서에 날짜, 이력, 키보드로 치지 않는 기호, 보이지 않는 문자가 들어가면 Claude 가 알림을 받고 방금 쓴 그 줄을 고친다. 같은 파일·같은 종류는 한 번만 알린다. Claude 가 편집 도구 대신 셸 명령(heredoc, `sed -i`, 스크립트)으로 쓴 파일도 명령 전후를 비교해 같은 검사를 하고, 그 파일에 맞는 규칙을 보여 준다.
- 코드 파일 하나가 800줄을 넘으면 알리고, 1,500줄을 넘으면 더 덧붙이기 전에 어떻게 나눌지 사용자에게 묻는다. luau-kb 플러그인이 설치돼 있으면 `.luau` 파일에는 분리 계획기 명령도 함께 준다(없으면 그 줄만 빠진다).
- 스킬 설명(description)이 영어로 무엇과 언제를 말하지 않거나, 영어로 쓰는 모델용 문서에 한국어 문장이 섞이거나, 결정 번호가 플러그인 밖 파일을 가리키면 알린다.
- 같은 목록이나 값의 사본(`@copy-of` 표시)이 원본과 달라지거나, 표시를 읽히지 않는 자리(문서 주석, HTML 주석, JSON)에 두거나 형제 저장소 경로 꼴을 섞으면 알린다. 다른 저장소의 원본(`<저장소>:<경로>`)은 지금 저장소 옆의 같은 이름 폴더에서, 없으면 이 컴퓨터에서 Claude Code 로 연 저장소 가운데 이름이 같은 것에서 찾는다. 못 찾으면 비교하지 않는다.
- 답이 사용자 언어(예: 한국어)에서 영어로 새면 고쳐 쓰게 한다. 언어 설정이 없으면 첫 답 끝에서 어느 언어로 답할지 한 번 묻는다.
- 턴이 끝날 때 손댄 파일에 전부터 있던 문제를 한 줄로 보여 준다. 고치지는 않는다. 주석을 정리하려면 `/qwreey-conventions:comments-cleanup [경로]` 를 부른다. 그러면 Claude 가 파일 전체 검사 도구(`scripts/conventions-scan.py`)로 문제를 찾고, 판단이 필요 없는 기호와 보이지 않는 문자는 주석 안에서만 일괄로 바꾼 뒤 코드가 그대로인지 기계적으로 확인하고, 이력처럼 판단이 필요한 줄은 직접 고쳐 쓴다. CLAUDE.md·스킬 같은 모델용 문서는 `/qwreey-conventions:docs-cleanup [경로]` 가 같은 도구로 이력 줄을 지금의 사실로 다시 쓰고, 옮길 이력은 커밋 메시지에 담도록 모아 보고한다.
- Claude 가 자기 메모(auto memory)에 저장소 지식을 적으면 저장소 문서로 옮기라고 알린다. 메모는 그 컴퓨터에만 있어 동료에게 가지 않는다.
- (선택, 기본 꺼짐) 읽기 좋은 코드 규약: 켜면 Claude 가 함수 안 단계를 빈 줄로 나누고 짧은 영어 라벨을 달며, 남이 부르는 함수에는 편집기 호버에 보이는 문서 주석을 단다. 새로 쓰거나 크게 키운 함수가 빈 줄 없이 길면 숫자와 함께 알린다. 개인 취향이 담긴 규약이라 기본은 꺼져 있고, 쓰고 싶은 사람이 설정(아래)에서 켠다. 켠 사람도 저장소가 `.claude/harness.env` 에 `HARNESS_READABLE_CODE=off` 를 두면 그 저장소에서는 꺼진다.

## 비용
- 늘 드는 것: 스킬 설명 1개(`code-reuse`, 영문 약 520자). 사용자 명령 `comments-cleanup`, `docs-cleanup` 은 모델에게 실리지 않는다. 훅은 모델을 부르지 않는다.
- 규칙 본문은 맞는 파일을 처음 열 때 하나씩 실린다(규칙당 약 200~650 토큰, compact 뒤 다시). 읽기 좋은 코드 규약을 켜면 코드 파일에서 하나(약 600 토큰)가 더 실린다.
- 답이 다른 언어로 샜을 때만 다시 쓰는 한 턴이 더 든다.

## 요구 사항
- 훅이 `python3` 를 부른다(표준 라이브러리만). Linux·macOS 에서 쓴다.

## 설정
`/plugin configure qwreey-conventions@claude-doctor-market` 나 `/config` 의 플러그인 옵션에서 고른다. 다음 파일을 열거나 다음 답부터 적용된다.
- 읽기 좋은 코드 규약(`harness_readable_code`): 기본 꺼짐.
- 규약 자동 주입(`harness_conventions_rules`): 기본 켜짐. 끄면 규약 글은 빠지고 줄 알림은 그대로다.
- 답변 언어 지키기(`harness_reply_language`): 기본 켜짐.
- 줄 단위 규약 검사(`conventions_check`), 파일 길이·구조 알림(`structure_reminder`), memory 자리 알림(`memory_placement`): 기본 켜짐.

고급: 같은 키를 대문자로 `~/.claude/harness.env` 나 저장소 `.claude/harness.env` 에 적을 수 있다(저장소 파일이 설정보다 이긴다). luau-kb 팩을 고치는 사람은 `HARNESS_LUAU_KB=<팩 폴더>` 로 설치본 대신 작업 사본의 계획기를 쓴다.

## 끄기
- 알림 하나씩: 위 설정에서 끈다(환경 변수 `CONVENTIONS_CHECK=off` 등도 된다).
- 전부: `claude plugin disable qwreey-conventions@claude-doctor-market` (제거는 `uninstall`).

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-conventions@claude-doctor-market
```

자세한 동작(훅 구성, 검사 항목, 남은 문제 보고, 테스트): [docs/how-it-works.md](docs/how-it-works.md). 주석 알림의 뜻, 기호 대체 표, 저장소 설정(`.claude/conventions.json`), 기존 주석 정리: [docs/comments.md](docs/comments.md). 모델용 문서에 남길 것과 옮길 것, 문서 알림, 기존 문서 정리: [docs/agent-docs.md](docs/agent-docs.md). 값의 정책·불변식 표와 사본 검사 설정(`reuse`): [docs/code-reuse.md](docs/code-reuse.md)
