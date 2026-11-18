# qwreey-sessions

이 플러그인을 켜 두면 대화가 백그라운드에서 저절로 요약돼 저장소 밖에 쌓인다. 세션을 닫거나 compact 해도 사용자 지시, 결정, 미해결이 남아서, 새 세션은 직전 세션이 하다 만 일을 이어받고 compact 직전에는 놓치면 안 되는 지시를 다시 떠올린다. "전에 뭐라고 정했지", "그때 왜 바꿨지" 를 물으면 옛 기록에서 찾아 준다. 요약은 별도 프로세스가 작은 모델(haiku)로 하므로 대화가 멈추지 않고, 요약 속 인용과 숫자는 원문과 기계로 대조해 원문에 없는 인용은 뺀다. 늘 끼어들지는 않는다. 이어서 연 세션(resume)은 맥락이 그대로라 인계를 생략하고, 다른 세션이 아직 일하는 중이면 그 세션의 인계도 넣지 않으며, `claude -p`·SDK 로 돌린 자동 세션은 기본으로 기록하지 않는다. 저장소 안에는 사용자가 가져오기로 정했을 때만 들어간다.

## 무엇이 달라지나
- 새 세션을 열면 직전 세션의 미해결 몇 줄이 인계로 들어가, 처음부터 다시 설명하지 않아도 된다.
- compact 직전에 사용자 지시 원문, 결정, 미해결을 다시 짚고, compact 뒤에는 이 세션 기록이 어디 있는지 알려 준다. compact 뒤에는 방금 요약된 구간에서 사용자가 한 말 원문과 바뀐 파일, 커밋, 오류 첫 줄, 결정 번호 목록도 다시 넣어(모델 호출 없음, 약 8,000자 이하), 요약이 흘린 정확한 값을 되살린다(설정에서 끌 수 있다).
- 커밋하려 할 때 저장소로 아직 가져오지 않은 기록이 있으면 알려 준다(막지 않음). 보관할 폴더가 정해지지 않았으면 에이전트가 위치를 제안한다.
- 옛 기록을 열면 "그 시점의 기록이니 지금 파일로 확인하라" 는 한 줄이 붙어, 낡은 내용을 사실로 믿지 않게 한다.
- 직접 부를 수 있는 명령: `/qwreey-sessions:checkpoint`(지금 저장하고 /compact 인자 초안), `/qwreey-sessions:import`(기록을 저장소로 가져오기), `/qwreey-sessions:recall`(옛 논의·결정 이유 찾기). 말로 "전에 뭐라고 정했지" 라고 해도 된다.

## 비용
- 늘 드는 것: 스킬 설명 3개(약 1,000자). 훅은 모델을 부르지 않는다.
- 요약: 백그라운드 haiku 호출로 세션당 수 센트 수준, 세션 길이에 비례한다. 끄면 0.

## 요구 사항
- Linux·macOS(`fcntl` 을 쓴다. Windows 불가). `python3`, `claude` CLI(요약 호출).

## 설정
`/plugin configure qwreey-sessions@qwreey-harness` 또는 `/config` 의 플러그인 설정에서 바꾼다.
- 세션 기록(`session_log`, 기본 켜짐): 끄면 훅이 모두 아무것도 하지 않는다. 옛 키 `SESSION_LOG_DISABLE=1` 도 harness.env 와 환경 변수에서 그대로 끈다.
- 요약 모델(`session_log_model`, 기본 `haiku`).
- 기록 보관 폴더(`session_log_home`): 비우면 `~/.local/share/session-log`.
- compact 뒤 원문 되살리기(`session_log_compact_anchors`, 기본 켜짐).
- 큰 기록 통째 읽기 막기(`session_log_read_gate`, 기본 켜짐).
- 고급: 쿨다운, 분량, 인계 길이 같은 튜닝 값은 `~/.claude/harness.env` 나 저장소 `.claude/harness.env` 키다(목록 [docs/session-log.md](docs/session-log.md)).

## 끄기
- 기록만: 위 설정의 "세션 기록 끄기".
- 전부: `claude plugin disable qwreey-sessions@qwreey-harness`.

## 설치
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-sessions@qwreey-harness
```

자세한 동작: [docs/how-it-works.md](docs/how-it-works.md)(훅 구성, compact 처리, 플랫폼, 테스트), [docs/session-log.md](docs/session-log.md)(요약 흐름, 저장 위치, 알림 표, 명령, 설정 키)
