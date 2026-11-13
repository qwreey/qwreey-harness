# qwreey-sessions

세션 기록 자동화 플러그인. 대화를 분리 프로세스가 요약해 저장소 밖에 쌓고, 다음 세션과 compact 뒤에 이어 가게 한다.

## 무엇을 하나
- 훅 `hook.py`: 세션 종료·compact 직전에 트랜스크립트를 증분 요약(분리 워커, 원문과 기계 대조)해 저장소 밖(`~/.local/share/session-log/`)에 기록한다. PreCompact 상기, SessionStart 인계, 가져갈 기록이 쌓였을 때와 커밋 직전 알림을 낸다.
- 훅 `records_read.py`: 세션 기록을 읽을 때 "스냅샷이니 현재 파일로 확인하라" 한 줄(큰 기록은 recall 안내).
- 스킬 `qwreey-sessions:checkpoint`(지금 저장하고 새 미해결·지시와 /compact 인자 초안), `qwreey-sessions:import`(기록을 저장소로 복사), `qwreey-sessions:recall`(옛 논의·결정 이유 찾기).
- 명령 `session-log`(bin, PATH 에 오른다). 자세히: `docs/session-log.md`.

## 비용
- 상시 로드: 스킬 설명 3개(약 1,200자). 훅 8개 이벤트, hot path 는 PreToolUse(Bash·Skill)와 PostToolUse(모든 도구)에서 도는 가벼운 파이썬(판단만, 모델 호출 없음).
- 요약 비용: 백그라운드 haiku 호출. 세션 길이에 비례하고 세션당 수 센트 수준(분리 프로세스라 대화는 안 막힌다). 끄면 0.

## 효과
- 세션을 닫거나 compact 해도 결정과 미해결이 남고, 다음 세션이 이어받는다. 옛 논의는 recall 로 찾는다.

## 왜 택하나, 누구에게 안 맞나
- 택한다: 긴 작업을 여러 세션·compact 로 이어 가고, "전에 뭐라고 정했지"를 자주 묻는 경우.
- 안 맞는다: 짧은 일회성 세션 위주, 대화 내용을 디스크에 요약으로 남기는 것이 싫은 경우, 비용 고지가 번거로운 경우.

## 요구 사항
- Linux·macOS(`fcntl` 을 쓴다. Windows 불가). `python3`, `claude` CLI(요약 호출).

## 끄기
- 환경 변수 `SESSION_LOG_DISABLE=1` 등 설정은 `docs/session-log.md`(harness.env 의 `SESSION_LOG_*`).
- 전부: `claude plugin disable qwreey-sessions@claude-doctor-market`.

## 설치
```bash
claude plugin install qwreey-sessions@claude-doctor-market
```
테스트: `python3 -I plugins/qwreey-sessions/tests/test_session_log.py`
