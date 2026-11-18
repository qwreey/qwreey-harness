# qwreey-reply-language 동작 상세

구성: 훅 스크립트 하나(`hooks/reply_language.py`)를 세 이벤트에 건다(`hooks/hooks.json`). 스킬, 규칙, 상시 주입 글은 없다. 메인 대화만 보고(`agent_id` 가 있으면 건너뜀), 모델을 부르지 않으며, 실패하면 조용히 통과한다. 메시지는 영어 `<harness-hook name="reply-language" level="…">` 에 세션 nonce 를 단다.

## 훅
| 이벤트 | 하는 일 |
|---|---|
| UserPromptSubmit | 언어를 알 수 없으면 세션당 한 번 info: 요청에 먼저 답하고, 답 끝에서 어느 언어로 답할지 물어 `set` 명령으로 저장하게 한다. 첫 요청을 질문으로 막지 않으려고 action 이 아니다 |
| Stop | 마지막 답이 이탈이면 `decision: block` 으로 다시 쓰게 한다 |
| PostToolBatch | 도구 호출 사이 글이 이탈이면 info(쿨다운), 한 요청의 도구 호출이 10회, 이후 15회마다 info 한 줄 |

## 언어 출처
좁은 쪽이 이긴다: 프로젝트 `.claude/settings.local.json` > `.claude/settings.json` > 사용자 `settings.json` 의 `language`, 없으면 `${CLAUDE_PLUGIN_DATA}/language.json`. 둘 다 없으면 위 UserPromptSubmit 알림이 묻게 한다.

저장: `python3 -I hooks/reply_language.py set <language> [--data <dir>]`. Bash 에는 `CLAUDE_PLUGIN_DATA` 가 없어서 알림이 데이터 폴더 경로를 적어 준다. `--data` 가 없으면 `<설정 폴더>/plugins/data/qwreey-reply-language*` 를 찾는다.

## 이탈 판정
- 코드 블록, 인라인 코드, URL, 경로를 뗀 뒤 목표 문자 체계 글자와 라틴 글자를 센다. 목표 문자 비율이 0.25 미만이고 라틴 글자가 20자 이상이면 이탈이다. 실제 기록에서 한글 프롬프트 1,264턴 중 35턴(2.8%)이 영어로 답했고 비율 분포가 이봉이라 이 문턱이 깨끗하게 가른다.
- 보는 문자 체계: 한글, 일본어, 한자, 키릴, 아랍, 히브리, 타이, 그리스, 데바나가리. 라틴 문자 언어(영어, 스페인어 등)는 감지하지 않는다(Stop 에서 기록만 남긴다).
- Stop: `stop_hook_active` 면 통과한다(루프 방지). block 직전에만 트랜스크립트 끝에서 마지막 실제 사용자 프롬프트를 읽어, 코드·붙여 넣은 글·URL·경로를 뗀 뒤 목표 글자가 3개 미만이면(사용자가 영어로만 썼다) 통과한다. 사용자가 이번 턴에 다른 언어를 명시한 경우는 코드가 못 가리므로 사유 문구가 "그대로 두라" 고 한다.
- PostToolBatch: 트랜스크립트를 저장된 오프셋부터 읽고 개행으로 끝난 줄만 소비한다(기록은 한 걸음 늦다). 서브에이전트(sidechain) 줄은 뺀다.

## 상태와 기록
- 세션 상태(물었는지, 오프셋, 도구 호출 수): `tempfile.gettempdir()/claude-conventions-lang/<세션>.json`.
- 기록: `${CLAUDE_PLUGIN_DATA}/drift.jsonl` 에 감지와 조치마다 한 줄(ts, session, kind, ratio, length). 답 본문은 남기지 않는다.

## 설정
- 옵션 `harness_reply_language`(기본 켜짐) = `HARNESS_REPLY_LANGUAGE`. 층: 사용자 `~/.claude/harness.env` < 플러그인 옵션(`/config`) < 저장소 `.claude/harness.env` < `.claude/harness.local.env` < 환경 변수. 값이 `off` 일 때만 꺼진다. 층 읽기가 실패하면 켜짐으로 돈다(`hooks/reply_env.py`).

## 플랫폼
표준 라이브러리 Python 3 만 쓴다. Linux, macOS, Windows(Git Bash) 에서 돈다.

## 테스트
```bash
python3 -I plugins/qwreey-reply-language/tests/test-reply-language.py
```
모델을 부르지 않는다.
