---
format: 1
title: Starlight 문서 사이트 스킬 초안
description: 저장소의 README·docs 를 git 에서 빠진 생성 사본으로 Starlight 사이트에 싣는 스킬(docs-site 팩 후보); 스크래치에서 Starlight 0.43.1·Astro 7.4.12 로 claude-doctor 문서 23개를 손 복사 없이 빌드하고 링크 검사 통과, 사본 없는 loader 방식은 링크 검사와 상대 이미지가 깨져 버림
status: active
---
# Starlight 문서 사이트 스킬 초안

사용자 (2026-11-17): "퍼블리시 하고 빌드 하는건 나름 내가 할 수 있는데 이렇게 starlight 로 사이트를 빌드업 하는건 스킬로 둬도 될듯? 나름 다른 팀원분들도 도움이 될만한것 같기도 하고 우리쪽도 각 플러그인 설명이나 스크린샷을 내가 넣으면서 문서화 해본다면 스킬 사용의 테스트로 사용할 수도 있겠거든. 다만 퍼블리시 하고 나서 생각해봐도 될것 같긴한데, 스킬 자체는 지금 연구를 하고 있어도 괜찮지 않을까 싶어." 서브에이전트(opus)가 조사·실험했고 메인이 기록했다. 실험 사이트(node_modules 뺌): `/code/.claude/jobs/394d4744/tmp/starlight/site/`(작업 끝나면 지워짐; 템플릿 원형 `scripts/sync-repo-docs.mjs`, `docs-sources.mjs`, `astro.config.mjs`).

## 근거
- quad `docs/site`(읽기만): 원본 `docs/<트랙>/*.md` 를 `sync-docs.py` 가 사이트 사본으로(첫 H1 제거, 상대 `.md` 링크를 사이트 경로로, GitHub 경고 블록을 aside 로, `<picture>` 다크/라이트, 바뀐 파일만 씀). 한국어 root 로케일(`defaultLocale: 'root'`), 폴더별 autogenerate 사이드바, 105쪽에서 `starlight-sidebar-topics`. `check-mermaid.mjs`(jsdom 위 `mermaid.parse()`)는 그대로 일반화 가능. `DEPLOY.md` 가 1회 준비와 매번 할 일을 나눔, `site` 는 `DOCS_SITE` 환경 변수.
- quad 전용: Luau 스니펫 검사(`scripts/doc-snippets.py`, luau-kb 쪽 일), 퀴즈 MDX, MDX 재파싱 우회, 버전 배지, changelog, 직접 짠 스크립트, 프록시 호스트, bash·python 에 기댄 `dev.sh`.
- devplorer `docs/`: 줄인 판, 스크린샷 `src/assets/screens/*.png`, `scripts/crop.mjs`(sharp).
- 예전 논의: `.claude/audit/06-docs-and-canon.md` 대안 B(공유 Starlight preset, 스니펫 CI), `.claude/audit/03-quad-family.md` §3, `.claude/archive/plan/PLAN-2026-11.md` P5 "문서 정본"(나중에). 포크는 지금 quad, devplorer 둘이고 stl-luau 문서 계획이 세 번째.
- quad 의 어긋남(quad 세션 몫): `watch-docs.py` TRACKS 에 `agents` 빠짐, DEPLOY.md 의 mermaid 11 핀 문구가 낡음, Starlight 0.43.0 이 `scopedStyleStrategy` 를 `"where"` 로 강제하지 않게 바뀌어(BREAKING) STYLING.md 의 "해시 specificity 0" 전제가 깨짐(올릴 때 명시 필요).

## 실험 (스크래치)
- Starlight 0.43.1, Astro 7.4.12(Node 22.23.4 이상), starlight-links-validator 0.27, astro-mermaid 2.2. 한국어 UI 문자열 내장(`lang="ko"`, "검색").
- 사본 없는 loader(`context.renderMarkdown`): links-validator 가 `src/content/docs` 밖 페이지를 몰라 정상 링크 14개를 실패로 냈고, 상대 이미지가 `__ASTRO_IMAGE_` 로 남음. 버림.
- 생성 사본(git 제외, 첫 줄에 원본 경로): claude-doctor 문서 23개가 25쪽, dist 6 MB, 링크 검사 통과, 이미지 webp 최적화. 채택.

## 설계
- 기본 꺼짐 팩 `docs-site`, 스킬 `starlight`(이름 미정). templates 는 사이트에 그대로 복사되는 파일(package.json, astro.config.mjs, docs-sources.mjs, sync·mermaid·crop 스크립트, 한국어 i18n, index, 첫 가이드, theme.css, .gitignore, DEPLOY.md, 동료용 README, page.md). references 는 mapping, components, styling(0.43 반영), versions, deploy, optional-plugins.
- 매핑 규칙: 사본은 `src/content/docs/<slug>.md`; title 은 frontmatter 아니면 첫 H1, description 은 frontmatter 아니면 첫 문단; 매핑된 문서 링크는 slug 로, 그 밖은 `repoUrl` 로(없으면 글자만); 상대 이미지는 `src/assets/repo/` 로; README 는 `plugins/<p>/index`(라벨 "소개").
- 스크립트는 Node 만(Windows 동료의 `npm run dev`). `.claude/`, PLAN, HUMAN_TODO, 세션 기록은 싣지 않는다.
- 스크린샷: README 그림은 원본 옆 `docs/images/`, 사이트 전용은 `src/assets/screens/<주제>/`; PNG, 1600px 이하, kebab-case, 한국어 alt. 터미널 출력은 그림보다 ```text 블록.
- 몫: 동료는 페이지 복사·작성, 그림 넣기, `npm run dev`; 에이전트는 스캐폴드, 매핑, 사이드바, 검사 실패 수정, 버전; 배포는 사용자.
- 시험: 첫 실사용은 claude-doctor `docs/site`(플러그인·팩 README 와 docs, 사용자 스크린샷; 손 복사 0, 링크 검사 통과, README 수정이 dev 에 바로 반영); 새 맥락 sonnet 에이전트에게 "qwreey-desk 페이지에 이 스크린샷 넣어줘" 만 주고 스킬로 해내는지; 두 번째는 stl-luau 나 devplorer; `claude plugin eval` 트리거; Windows 동료 `npm run dev`.

## SKILL.md 초안 description
```
Builds and maintains a Starlight (Astro) documentation site in a repo's docs/site: scaffolds it from templates, shows existing READMEs and docs as generated pages without duplicating them, sets up the sidebar, the Korean root locale, screenshots, mermaid and link checks, and runs build and preview; publishing stays with the user. Use when a repo needs a public or team docs website, when adding a page, screenshot or section to such a site, or when its build, links or diagrams break. 문서 사이트 만들기, 스타라이트, 페이지 추가, 스크린샷 넣기, 사이트 빌드.
```
본문 초안의 절: Layout, New site(제목·도메인·대상 파일·언어를 묻고, 템플릿 복사, `npm view` 로 버전 확인, `npm run check`), Showing existing docs(`docs-sources.mjs` 에 추가, 생성 페이지는 고치지 않음), Pages·sidebar·language, Screenshots, Diagrams and checks(dev 중에 build 하지 않음), Publishing(사용자 몫, wrangler·DNS 는 실행 안 함), Helping someone who does not code.

## 열린 질문
- 위치: 기본 꺼짐 팩 `packs/docs-site`(추천) / 항상 켜진 qwreey-* 플러그인(설명 약 500자가 모든 저장소에) / quad.
- 이름: `docs-site:starlight` / `starlight-site` / `qwreey-docsite`.
- 공유 preset 패키지: 아직 아니오(세 번째 사이트가 생기면 다시).
- 도메인과 Cloudflare Pages 이름, 공개 전엔 로컬 미리보기만인지(공개 전 `repoUrl` 은 바깥에서 404).
- 영어 병행, how-it-works 같은 개발자 문서 포함, `.md.txt`/`llms.txt`, quad 어긋남 전달, quad-site-tester 식 브라우저 실측 일반화.
