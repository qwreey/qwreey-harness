# vitrine 세션에게: 웹 플러그인 도입 (.claude/audit/16)

근거는 `claude-doctor/audit/16-marketplace.md` §2, §8 이다. 반영은 vitrine 세션이 판단한다. 아래 모두 vitrine project 범위다(사용자 레벨에 두면 Luau 저장소에서도 Stop 리뷰가 돈다).

## 1. `vitrine/.claude/settings.json` 에 합칠 조각

```json
{
  "enabledPlugins": {
    "security-guidance@claude-plugins-official": true,
    "frontend-design@claude-plugins-official": true,
    "context7@claude-plugins-official": true,
    "claude-security@claude-plugins-official": true
  },
  "env": {
    "ENABLE_COMMIT_REVIEW": "0"
  }
}
```

- 기존 키가 있으면 합친다(`jq -e` 로 검증).
- 다른 세션과 worktree 를 공유하면 `env` 에 `"ENABLE_STOP_REVIEW": "0"` 도 더한다(security-guidance README 권고).
- context7 은 .claude/audit/16 §7-3 실측 전이라 후보다. 부담되면 뺀다.
- security-guidance 는 첫 세션에 PyPI 에서 venv 를 만든다(네트워크). Stop 리뷰는 턴마다 Opus 를 부른다(약 0.19 USD 상당).
- typescript-lsp, gopls-lsp 는 바이너리 설치와 실측 뒤에 더한다(지금은 넣지 않는다).

## 2. 프로젝트 `CLAUDE.md` 에 넣을 줄

- 새 화면·리디자인은 `/frontend-design:frontend-design` 부터 시작한다. 기존 디자인 토큰(`web/src/styles.css`)이 브리프이므로 새 팔레트를 만들지 않는다.
- 웹·네트워크에 닿는 변경은 커밋 전 `/security-review`. 릴리스 전에는 `/claude-security` 를 수동으로 돌린다.
- React·Vite 버전별 API 가 불확실하면 context7 로 확인한다.

## 3. 참고

- 사용자 레벨 `rules/web-security.md`(정본 `claude-doctor/home/.claude/rules/`)가 `*.ts, *.tsx, **/server/**` 등을 다룰 때 자동 로드된다. 사용자가 `home-sync apply` 하면 적용된다.
- 확인: `python3 -I <claude-doctor>/plugins/q/skills/doctor/scripts/scan.py <vitrine> --only 8` 에서 `WEB-PLUGINS` 정보가 사라지면 끝이다.
