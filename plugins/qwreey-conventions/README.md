# qwreey-conventions

이 플러그인을 켜면 Claude 가 남기는 코드 주석과 CLAUDE.md·스킬 같은 모델용 문서가 덜 지저분해진다. 주석에는 "지금 왜 이렇게 되어 있나" 만 남고 날짜, 작업 이력, 결정 번호는 커밋 메시지로 간다. 이력이 쌓인 주석은 읽는 사람에게 잡음이고, 모델용 문서는 매번 읽히므로 한 줄 한 줄이 비용이기 때문이다. 같은 값이 여러 곳에 복사돼 어긋나거나 한 파일이 끝없이 길어지는 것도 일찍 알린다. 쓰는 법은 스킬과 규칙 파일이 맡고, 훅은 방금 추가한 줄이 벗어난 것 같을 때만 Claude 에게 한 줄로 알린다. 답변 언어를 빼면 막지 않으며, 기존 줄을 몰래 일괄 정리하지도 않는다.

## 무엇이 달라지나
- 주석이나 모델용 문서에 날짜, 이력, 키보드로 치지 않는 기호, 보이지 않는 문자가 들어가면 Claude 가 알림을 받고 방금 쓴 그 줄을 고친다. 같은 파일·같은 종류는 한 번만 알린다.
- 코드 파일 하나가 800줄을 넘으면 알리고, 1,500줄을 넘으면 더 덧붙이기 전에 어떻게 나눌지 사용자에게 묻는다.
- 같은 목록이나 값의 사본(`@copy-of` 표시)이 원본과 달라지면 알린다.
- 답이 사용자 언어(예: 한국어)에서 영어로 새면 고쳐 쓰게 한다. 언어 설정이 없으면 첫 답 끝에서 어느 언어로 답할지 한 번 묻는다.
- 턴이 끝날 때 손댄 파일에 전부터 있던 문제를 한 줄로 보여 준다. 고치지는 않는다. 고치려면 "기존 문제도 정리해줘" 라고 하면 된다. 그러면 Claude 가 파일 전체 검사 도구(`scripts/conventions-scan.py`)로 문제를 찾고, 판단이 필요 없는 기호와 보이지 않는 문자는 주석 안에서만 일괄로 바꾼 뒤 코드가 그대로인지 기계적으로 확인한다.
- Claude 가 자기 메모(auto memory)에 저장소 지식을 적으면 저장소 문서로 옮기라고 알린다. 메모는 그 컴퓨터에만 있어 동료에게 가지 않는다.

## 비용
- 늘 드는 것: 스킬 설명 3개(영문 약 1,550자). 훅은 모델을 부르지 않는다.
- 규칙 본문은 맞는 파일을 처음 열 때 하나씩 실린다(규칙당 약 200~650 토큰, compact 뒤 다시).
- 답이 다른 언어로 샜을 때만 다시 쓰는 한 턴이 더 든다.

## 요구 사항
- 훅이 `python3` 를 부른다(표준 라이브러리만). Linux·macOS 에서 쓴다.

## 끄기
- 주석·문서·사본 알림: `CONVENTIONS_CHECK=off`. 파일 길이: `STRUCTURE_REMINDER=off`. 답변 언어: `HARNESS_REPLY_LANGUAGE=off`. 규칙 주입: `HARNESS_CONVENTIONS_RULES=off`. 메모 알림: `MEMORY_PLACEMENT=off`. 모두 환경 변수다.
- 전부: `claude plugin disable qwreey-conventions@claude-doctor-market` (제거는 `uninstall`).

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-conventions@claude-doctor-market
```

자세한 동작(훅 구성, 검사 항목, 저장소 설정, 남은 문제 보고, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
