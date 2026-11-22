# qwreey-reply-language

이 플러그인을 켜면 Claude 가 한국어로 묻는 사람에게 영어로 답해 버리는 일이 줄어든다. 긴 작업 끝에 답이 영어로 새면 턴이 끝나기 전에 한 번 막고 같은 내용을 사용자 언어로 다시 쓰게 한다. 사용자는 다시 쓴 답만 본다.

## 무엇이 달라지나
- 답이 사용자 언어(예: 한국어)에서 영어로 새면 Claude 가 같은 내용을 사용자 언어로 다시 쓴다. 코드나 인용한 출력이 많은 답은 사용자 언어 문장이 둘러싸고 있으면 그대로 둔다.
- 사용자가 이번 턴에 영어로만 썼거나 영어로 답하라고 했으면 그대로 둔다.
- 도구를 오래 쓰는 동안 중간 글이 영어로 새거나 도구 호출이 많아지면 Claude 에게만 한 줄로 상기시킨다(사용자에게는 보이지 않는다).
- 사용자 언어는 Claude Code 설정의 `language` 를 따른다. 없으면 첫 답 끝에서 어느 언어로 답할지 한 번 묻고 저장한다.
- 한글, 일본어, 중국어, 키릴 문자처럼 라틴 문자가 아닌 언어만 본다. 스페인어 같은 라틴 문자 언어는 영어와 글자로 가를 수 없어 보지 않는다.

## 비용
- 늘 드는 것: 없다. 스킬, 규칙, 상시 글이 없고 훅은 모델을 부르지 않는다.
- 답이 샜을 때만 다시 쓰는 한 턴이 더 든다(실제 기록에서 한국어 턴의 약 3%).

## 효과
- 실제 기록에서 한국어로 물은 1,264턴 중 35턴이 영어로 답했고, 긴 도구 실행 뒤에 몰렸으며 한번 넘어가면 이어졌다. 이 플러그인은 그런 답이 사용자에게 가기 전에 고쳐 쓰게 한다.
- 글자 비율로 짐작하는 검사라 코드가 대부분인 답에 가끔 걸린다. 그때 Claude 는 고칠 것이 없으면 아무것도 덧붙이지 않는다.

## 왜 택하나
- 영어 답을 읽기 불편하거나, 비프로그래머 동료에게 Claude 를 쓰게 하는 경우.
- 주석·문서 규약(qwreey-conventions) 전체는 필요 없고 답 언어만 지키고 싶을 때. 이 플러그인은 다른 플러그인 없이 혼자 돈다.

## 요구 사항
- 훅은 Rust 바이너리 `native/qwreey-reply-language` 를 부른다. 지금은 저장소에서 `cargo build --release -p qwreey-reply-language` 로 만들어 그 자리에 복사해야 하고, 없으면 훅이 아무것도 하지 않는다(막지 않는 오류). 바이너리는 아직 Linux 판만 있다. python 판(`hooks/reply_language.py`, 표준 라이브러리만)은 Linux, macOS, Windows(Git Bash) 에서 돌고 대조 기준으로 남는다.

## 설정
`/plugin configure qwreey-reply-language@qwreey-harness` 나 `/config` 의 플러그인 옵션에서 고른다. 다음 답부터 적용된다.
- 답변 언어 지키기(`harness_reply_language`): 기본 켜짐. 끄면 언어를 보지 않는다.

고급: 같은 키를 대문자로 `~/.claude/harness.env` 나 저장소 `.claude/harness.env` 에 `HARNESS_REPLY_LANGUAGE=off` 로 적을 수 있다(저장소 파일이 설정보다 이긴다).

## 설치와 끄기
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-reply-language@qwreey-harness
```
- 끄기: 위 설정에서 끄거나 `claude plugin disable qwreey-reply-language@qwreey-harness` (제거는 `uninstall`).

자세한 동작(훅 구성, 판정 문턱, 언어 출처, 기록, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
