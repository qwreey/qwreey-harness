---
format: 1
title: 라이선스 작성 스킬과 알림 훅 초안
description: 레지스트리에 라이선스 스킬은 많지만 정본 텍스트를 받아 오는지 확인된 것이 없어, GitHub licenses API 나 SPDX 사본에서 받아 연도·소유자를 채우고 정본과 대조하는 작은 스킬을 먼저, LICENSE·벤더 파일 쓰기 알림 훅은 다음에 만든다
status: active
---
# 라이선스 작성 스킬과 알림 훅 초안

계기: 메인이 MIT LICENSE 를 기억으로 썼다(GitHub `/licenses/mit` 원문과 대조해 일치는 확인, 67a529d). 사용자: "차라리 라이선스 파일을 쓸 때 쓸 수 있는 도구를 얹어주는게 맞아보이고 검색으로 찾아봄직 하기도 하네.. 유의점이나 확인할 점을 알려주면서 동시에 프로젝트에 심긴 라이선스를 보고 사용 가능 관련 확인 훅을 주거나, 라이선스 authoring 스킬이 있으면 괜찮겠다 싶은데 이건 이미 수요가 있어서 분명 있을듯 한데". 서브에이전트(sonnet)가 웹 조사했고 메인이 기록했다.

## 이미 있는 것 (2026-11-17)
- anthropics/claude-for-legal `ip-legal:oss-review`: 의존성·외부 공개 코드의 OSS 라이선스를 배포 방식에 맞춰 분류. 별 10.0k, Apache-2.0. 배포 방식별 기준(게임 배포에 AGPL 등)을 참고할 만하다.
- charlesjones-dev/claude-code-plugins-dev `ai-compliance`(NOTICE·ATTRIBUTION 생성, 의존성 감사), melodic-software license-compliance, majiayu000 license-file-generator, kevinslin `dev.add-license`, danielrosehill license-populator 등 레지스트리 항목 다수. 코드는 읽지 않았고 정본을 받아 오는지, 훅을 주는지 확인된 것은 없다.
- 표준 도구: GitHub `GET /licenses/<id>`(본문에 `[year] [fullname]` 꼴 자리표시, 비인증 시간당 60회, 설치 0), SPDX license-list-data(v3.29.0, 오프라인 사본에 좋음), REUSE(`reuse download <id>` 로 `LICENSES/` 에 정본, `reuse lint`), licensee(Ruby), ScanCode(무거움), 생태계별 의존성 검사기(npm license-checker, pip-licenses, cargo-deny, go-licenses), Syft/Trivy.

## 검사로 만들 만한 것
- MIT·BSD 고지 유지, Apache-2.0 NOTICE 와 변경 표시, GPL·LGPL·AGPL 이 의존성·벤더 코드로 들어올 때 경고, CC-BY 등 문서·에셋 출처, 헤더 없는 벤더 파일, manifest `license` 필드(plugin.json, package.json, pyproject)와 LICENSE 일치, 선택 SPDX 헤더.

## 설계 (권고)
1. 스킬(먼저, 작게): 사용자와 라이선스·공개 여부·배포 방식을 정하고 주의점을 알림. 본문은 GitHub API, 실패하면 `lib/` 의 SPDX 사본에서 받음("기억으로 쓰지 않는다" 한 줄). 연도·소유자는 `git config` 나 사용자 답으로, 자리표시(`[year]`, `[fullname]`, `[yyyy]`)가 남지 않았는지와 정본 줄 대조. 필요하면 NOTICE·THIRD_PARTY 항목.
2. 훅(다음): PostToolUse info. LICENSE·NOTICE 를 쓰면 정본·자리표시·manifest 필드 확인; 벤더 폴더나 의존성 manifest 에 새 항목이 생기면 출처·라이선스·고지 갱신 확인. 막지 않는다.
3. 의존성 호환성 스캔은 필요할 때(oss-review 기준 참고나 선택 안내).
