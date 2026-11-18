# qwreey-license

이 플러그인을 켜면 Claude 가 라이선스 파일을 기억으로 쓰지 않는다. LICENSE 를 만들거나 고칠 때, 다른 프로젝트의 코드·문서·에셋을 가져올 때 스킬 `qwreey-license:license` 를 불러 정본 텍스트를 받아 쓰고 대조한다. "라이선스 파일 만들어 줘", "라이선스 정해야 하는데", "서드파티 고지 넣어 줘" 처럼 말하면 된다.

## 무엇이 달라지나
- **고르기**: 무엇을(코드, 문서, 게임 에셋) 어디에(공개, 비공개) 어떻게(저장소, 패키지, 빌드된 게임) 내보내는지 한 번에 하나씩 묻고, 해당하는 주의점만 짧게 알려 준다(MIT·BSD 의 고지 유지, Apache-2.0 의 NOTICE 와 변경 표시, GPL 계열이 의존성이나 가져온 코드로 들어올 때, 문서·에셋의 CC-BY 출처 표시, 라이선스 파일이 없으면 아무도 쓸 수 없다는 뜻). 고르는 것은 사용자다.
- **쓰기**: GitHub licenses API 에서 정본을 받고, 안 되면 SPDX 라이선스 목록에서 받는다. 연도와 저작권자(기본은 `git config user.name`, 사용자에게 확인)를 채우고, 채우지 못한 자리가 남으면 쓰지 않는다. 둘 다 받지 못하면 멈추고 알린다(기억으로 대신 쓰지 않는다).
- **대조**: 이미 있는 LICENSE 를 정본과 단어 단위로 비교해 다른 곳을 보여 주고, 같은 폴더의 `package.json`, `pyproject.toml`, `Cargo.toml`, `.claude-plugin/plugin.json` 의 license 필드가 파일과 맞는지 본다.
- **서드파티 고지**: 가져온 코드·에셋의 출처, 파일 목록, 라이선스 전문을 `THIRD_PARTY_NOTICES.md` 에 한 절로 더한다. 같은 절을 두 번 넣지 않는다.

## 쓰지 않는 때
- 의존성 전체의 라이선스 호환성 검사(npm license-checker, pip-licenses, cargo-deny 같은 도구의 일). 법률 자문도 아니다.

## 비용
- 늘 드는 것: 스킬 설명 한 줄(약 480자). 훅 없음.
- 실행: 스크립트가 정본을 받는 HTTP 요청 한두 번. 모델 호출은 대화 안에서만.

## 요구 사항
- Python 3.11 이상(`python3` 이라는 이름으로, Windows 는 루트 README 의 Windows 절). 표준 라이브러리만 쓴다. Linux·macOS·Windows.
- 인터넷(api.github.com 또는 raw.githubusercontent.com). GitHub API 는 인증 없이 시간당 60번이라 넘으면 SPDX 로 넘어간다.

## 끄기
- `claude plugin disable qwreey-license@qwreey-harness` (제거는 `uninstall`). 훅이 없어 끄면 바로 멈춘다.

## 설치
```bash
claude plugin marketplace add <qwreey-harness 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin install qwreey-license@qwreey-harness
```
