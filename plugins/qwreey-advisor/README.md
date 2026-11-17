# qwreey-advisor

이 플러그인을 켜면 Claude 는 일이 끝났다고 말하기 전이나 되돌리기 어려운 방향을 정하기 전에, 스스로 "다른 눈" 에게 검토를 받는다. 오래 한 작업일수록 Claude 는 자기 가정에 익숙해져 같은 착각을 못 보기 때문이다. 검토는 두 가지다. 대화를 이어받은 분신이 "내 추론이 맞나" 를 따지는 가벼운 검토, 그리고 아무 맥락 없는 새 리뷰어가 파일과 사용자가 한 말만 읽고 반박해 보는 검토. 늘 돌리지는 않는다. 작업 단위마다 마무리 검토는 한 번이고, 기계적인 변경이나 문서만 고친 일, 이미 검토한 일은 건너뛰며, 막는 장치도 없다.

## 무엇이 달라지나
- "다 됐습니다" 전에 검토가 한 번 돌고, Claude 가 받아들인 지적과 버린 지적을 1~3줄로 알려 준다. 사용자가 "검토해 줘" 라고 하면 보고 전문을 한국어로 보여 준다.
- 같은 실패가 두 번 나면 세 번째로 같은 시도를 하기 전에 검토를 고려하라는 알림이 Claude 에게 뜬다.
- 큰 변경을 커밋하려 하면(기본 200줄, 중요 저장소로 정한 곳은 40줄) 검토를 고려하라는 알림이 뜬다. 최근 90분 안에 검토를 받았으면 뜨지 않는다. `git add ... && git commit ...` 처럼 한 명령에서 스테이징해도 그 범위까지 잰다.
- 서브에이전트가 돌려준 보고에 추천안이나 사용자에게 물을 질문이 있으면, 넘기기 전에 검토할 수 있다는 한 줄이 뜬다(에이전트마다 한 번).
- 리뷰어는 읽기 전용이다. 파일 수정, 커밋 같은 git 변경, 패키지 설치, Roblox Studio 조작이 막힌다.
- 저장소마다 검토 등급(high, mid, low, off)을 정할 수 있다. 중요한 저장소는 opus 로 더 촘촘하게, off 로 둔 곳은 알림이 멈춘다.

## 비용
- 늘 드는 것: 한 줄 규약과 스킬 설명 두 개(영문 약 950자). 훅은 모델을 부르지 않는다.
- 검토 한 번: 분신 검토 약 $0.5~0.6(대화가 길 때, opus 기준), 새 리뷰어 opus 약 $1, sonnet 약 $0.4, 2~3분. 그래서 자주 부르지 않는다.
- 내장 `advisor` 도구는 값에 비해 얻는 것이 적어 사용자가 요청할 때만 쓴다.

## 요구 사항
- 훅이 `python3` 와 `git` 을 부른다. Linux·macOS 에서 쓴다.

## 설정
`/plugin configure qwreey-advisor@claude-doctor-market` 또는 `/config` 의 플러그인 설정에서 바꾼다.
- 검토 등급(`harness_review_default`, 기본 `mid`): high, mid, low, off 가운데. 저장소별 등급이 없는 저장소에 쓴다.
- 턴 끝 검토 권고(`harness_review_stop`, 기본 켜짐): 커밋하지 않은 변경이 등급 기준보다 크면 턴을 끝내기 전에 검토를 권한다. 같은 변경에는 한 번만, 권한 뒤 90분은 다시 권하지 않는다.
- 계획 검토(`harness_review_plan`, 기본 `warn`): high 등급 저장소에서만 쓰인다. `warn` 은 권하고, `deny` 는 검토 표시 없이 계획 모드를 나가지 못하게 한다(막는 쪽이라 저장소가 고른다), `off` 는 끈다.
- 서브에이전트 보고 알림(`harness_review_handback`, 기본 켜짐).
- 고급: 저장소별 등급 `HARNESS_REVIEW_TIERS="저장소이름=high 다른저장소=off"`, 줄 수 임계, 최근 검토 시간은 `~/.claude/harness.env` 키다. 한 저장소에서만 바꾸려면 그 저장소 `.claude/harness.env`(공유)나 `.claude/harness.local.env`(나만, `.gitignore` 에 넣는다)에 같은 키를 둔다. 목록은 [docs/how-it-works.md](docs/how-it-works.md).

## 끄기
- 알림만: 설정의 검토 등급을 `off` 로. 한 저장소만이면 `HARNESS_REVIEW_TIERS` 에서 그 저장소를 `off` 로.
- 전부: `claude plugin disable qwreey-advisor@claude-doctor-market` (제거는 `uninstall`).

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-advisor@claude-doctor-market
```

자세한 동작(훅 구성, 알림 조건과 설정, 읽기 전용 가드, 기록, 테스트): [docs/how-it-works.md](docs/how-it-works.md). 설계 근거와 비용 실측: [docs/rationale-fresh-advisor.md](docs/rationale-fresh-advisor.md), [docs/rationale-inherit-advisor.md](docs/rationale-inherit-advisor.md)
