# qwreey-delegate

다른 모델 계열(Gemini `agy`, OpenAI `codex`)에게 좁은 질문을 맡기는 스킬 `qwreey-delegate:delegate`.

## 무엇을 하나
- 근본 원인 찾기, 틀 밖 시선, 발견 묶기, 이름 객관성 확인, 한 메커니즘 버그 사냥을 저장소별 비특권 uid 의 격리 worktree 에서 다른 계열 모델에게 시키고, 결과는 메인이 검증한 뒤에만 쓴다.
- "codex랑 agy써서 작명 논의해봐", "제미니한테도 물어봐" 같은 말로도 불린다. 리뷰 라운드·전체 감사·결정에는 쓰지 않는다.

## 비용
- 상시 로드: 스킬 설명 한 줄(약 150 토큰). 훅 없음.
- 실행: Claude 토큰은 지시문 작성과 검증 정도. 본 비용은 각 벤더 구독 한도에서 나간다(agy 는 flash 만, codex 는 Plus 한도가 작아 사용자가 확인). 백엔드마다 동시에 1건.

## 효과
- sonnet 과 opus 는 같은 뿌리라 어휘와 선택 편향을 공유한다. 다른 계열은 다른 각도에서 보지만 단정적이고 틀린 말과 부작용도 더 많아서, 결과는 발견일 뿐 결정이 아니다.

## 왜 택하나, 누구에게 안 맞나
- 택한다: 같은 계열이 계속 놓치는 원인을 다른 시선으로 보고 싶을 때, 작명 같은 객관성 확인.
- 안 맞는다: agy·codex 구독이 없거나, 루트 권한·uid 격리 설정을 감당하기 어려운 경우(비개발자 동료에게는 권하지 않음).

## 요구 사항
- Linux, root(`setpriv`, 저장소별 uid, `choom`). Windows·macOS 불가.
- `agy` 또는 `codex` CLI 설치와 각자 구독. 저장소 루트에 `AGENTS.md`, uid 표 등록(`delegate.sh register`).
- uid 표 `registry.tsv` 는 고쳐 쓰므로 `HARNESS_DELEGATE_REGISTRY`(`~/.claude/harness.env`)가 이 클론의 `skills/delegate/registry.tsv` 를 가리켜야 한다.

## 끄기
- `claude plugin disable qwreey-delegate@claude-doctor-market` (제거는 `uninstall`). 훅이 없어 끄면 바로 멈춘다.

## 설치
```bash
claude plugin install qwreey-delegate@claude-doctor-market
```
