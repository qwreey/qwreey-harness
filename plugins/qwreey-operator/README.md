# qwreey-operator

메인 대화는 말하고 판단하고, 큰 구현은 백그라운드 서브에이전트에게 맡기는 규약 플러그인.

## 무엇을 하나
- 세션 시작과 compact 뒤마다 규약 다섯 줄을 모델에게 넣는다. 기본 Claude 에 없는 것만 담는다: 넘길 경계(코드 3개+ 파일, 새 줄 150+, 많은 읽기; 설계가 가능한지 보는 프로브는 메인이 사용자와), 독립된 부분(백엔드·프론트엔드 등)은 나눠 병렬로(사용자가 정한 동시 상한을 따름), 수행자 모델(opus 기본), 지시문에 더할 것(사용자 원문, 테스트 명령이 든 완료 기준, 미결 질문 보고), worktree 와 커밋, 확인 방법. 지시문 기본 항목·백그라운드 실행·SendMessage 는 Claude Code 기본 지침에 있어 넣지 않는다.
- 훅 `delegate-nudge`: 메인이 한 턴에 코드를 12회 쓰거나 서로 다른 파일 8개를 쓰면 "위임을 고려하라"는 알림 한 번. 다음 턴에 이어 쓰면 한 번 더 상기. 막지 않는다. `.md .json .toml .yaml .txt` 와 /tmp 는 세지 않는다.

## 비용
- 상시 로드: 규약 다섯 줄(약 550 토큰), 스킬 없음. 훅은 모델 호출이 없고 도구 호출마다 파이썬이 잠깐 돈다.
- 실행 비용(100줄당, 실측 평균): 메인이 직접 $0.63, opus 서브 $0.60, sonnet 서브 $0.19. 돈은 sonnet 으로 내릴 때만 줄고 opus 로 넘기면 거의 같다.
- 그래도 기본 수행자는 opus 다. sonnet 은 시행착오가 늘어 시간과 토큰을 더 쓰고 결과가 나빠지기 쉽다(보안, 얽힌 이론, 틀리면 비싼 일). sonnet 은 문서·기계적 수정처럼 틀려도 싸고 금방 보이는 일에만.

## 효과
- 주 효과는 비용이 아니라 대화 유지와 fresh 맥락이다: 구현이 도는 동안 사용자와 계속 말할 수 있고, 수행자는 메인의 설계 가정을 물려받지 않는다.
- 근거: `.claude/research/drafts/main-delegate-evidence.md`.

## 왜 택하나, 누구에게 안 맞나
- 택한다: 한 번에 큰 구현을 시키고 그 사이에 의논을 이어 가고 싶을 때.
- 안 맞는다: 작은 수정 위주, 구현 중 계속 사용자 확인이 필요한 일, 서브에이전트 비용 고지를 번거롭게 느끼는 경우.

## 요구 사항
- Claude Code 서브에이전트가 도는 곳이면 어디서나(구독만으로 충분, 다른 벤더 불필요). Linux·macOS·Windows.
- 훅이 `python3` 를 부른다. Windows 는 Python 3 설치가 필요하다.

## 끄기
- 알림만: 환경 변수 `HARNESS_OPERATOR_NUDGE=off` (문턱은 `HARNESS_OPERATOR_NUDGE_WRITES`, `HARNESS_OPERATOR_NUDGE_FILES`).
- 전부: `claude plugin disable qwreey-operator@claude-doctor-market` (제거는 `uninstall`).

## 설치
```bash
claude plugin install qwreey-operator@claude-doctor-market
```
테스트: `python3 -I plugins/qwreey-operator/tests/test_delegate_nudge.py`
