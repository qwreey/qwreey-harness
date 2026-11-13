# web-security

웹·서버·인프라 코드를 다루는 저장소에서 켜는 보안 지식 팩이다. 켜 두면 Claude 가 TypeScript·JavaScript·Go 서버 코드, Caddy·nginx 설정, Dockerfile·compose, 셸 스크립트를 열 때 보안 원칙 스무 줄 남짓(실패하면 닫힌 쪽으로, 허용 목록, 주입, SSRF, 경로, 비밀, 상한, 헤더, 의존성)을 함께 보고, 엔드포인트·로그인·프록시·명령 실행·파일 경로·외부 연결을 만들거나 보안 리뷰를 할 때는 상황별 체크리스트를 꺼내 본다. 체크리스트 항목은 모두 실제로 한 번 배포됐던 실수에서 나왔다. Roblox 게임 코드(Luau)만 있는 저장소에는 필요 없다. 기본으로 꺼져 있어서 저장소가 켜기 전에는 아무것도 싣지 않는다.

## 무엇이 달라지나
- 서버 코드나 설정 파일을 처음 열면 보안 규칙이 한 번 실리고, 그 뒤 Claude 가 쓰는 코드가 그 규칙을 따른다(예: 실패하면 거부, 사용자 입력으로 만든 경로나 명령은 검증).
- 엔드포인트, 인증, 프록시, exec, 업로드, 서버 쪽 fetch 같은 작업이나 "보안 리뷰해 줘" 에서 `web-security:hardening` 체크리스트를 불러 하나씩 대조한다.
- 다른 저장소에서는 켜지지 않는다.

## 비용
- 켠 저장소에서만: 스킬 설명 한 줄(영문 약 460자), 맞는 파일을 처음 열 때 규칙 본문 한 번(약 800 토큰, compact 뒤 다시).
- 훅이 없고, 체크리스트는 부를 때만 읽는다.

## 요구 사항
- 규칙 주입은 coderag 플러그인(`coderag@coderag-market`)과 coderag 설정이 한다. 이 팩만 켜면 스킬만 쓰인다.

## 끄기
- 그 저장소의 `coderag.toml` 에서 `[[packs]] name = "web-security"` 를 지우고 `coderag adapt --harness claude` 를 다시 돌린다.

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin marketplace add <coderag 폴더>
claude plugin install coderag@coderag-market
claude plugin install web-security@claude-doctor-market
```
기계마다 한 번 `~/.coderag/coderag.toml` 에 팩 위치를 등록하고, 쓸 저장소의 `coderag.toml` 에 아래를 적은 뒤 `coderag adapt --harness claude` 를 돌린다.
```toml
[[packs]]
name = "web-security"
```

자세한 동작(주입 방식, 대상 파일, 체크리스트 구성, 테스트): [docs/how-it-works.md](docs/how-it-works.md)
