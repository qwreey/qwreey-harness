# harness-onboarding

Claude Code 를 처음 쓰거나 잘 모르는 동료를 위한 온보딩 플러그인이다. 설계와 실측 기록은 `audit/20-onboarding.md`.

## 쓰는 법
Claude Code 에서 `/harness-start` 를 입력한다. 다른 형태:
- `/harness-start context` — 그 개념 설명부터
- `/harness-start 진단` — 개념 설명을 건너뛰고 지금 환경 진단부터

진행: 역할·경험 묻기 → 개념 체크리스트 → 모르는 개념만 쉽게 설명 → 지금 환경을 **읽기만** 해서 진단 → 개선안을 하나씩 제안 → **동의한 것만** 적용.

## 설치
```bash
claude plugin marketplace add <claude-doctor 저장소 주소 또는 폴더>
claude plugin install harness-onboarding@claude-doctor-market
```

## 구성
| 위치 | 무엇 |
|---|---|
| `skills/harness-start/SKILL.md` | 진입 스킬(사용자 호출 전용). 동의 원칙이 맨 위에 있다 |
| `skills/harness-start/references/concepts/` | 개념 설명 15편(쉬운 한국어, 공식 문서 근거와 미확인 표시) |
| `skills/harness-start/references/diagnose.md` | 읽기 전용 진단 절차와 보고 형식 |
| `skills/harness-start/references/improvements.md` | 개선안 목록 A~J 와 적용 방법 |
| `skills/harness-start/templates/` | 배포용 동의 원칙: `CLAUDE.fragment.md`(CLAUDE.md 조각) 또는 `rules/consent.md`(rule). 둘 중 하나만 |

플러그인은 CLAUDE.md 나 rules 를 직접 배포할 수 없다(공식 제약). 동의 원칙을 늘 적용하려면 템플릿을 회사 관리 CLAUDE.md 나 각자의 `~/.claude/` 에 넣는다.
