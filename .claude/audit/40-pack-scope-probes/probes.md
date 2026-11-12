# 40 도메인 팩 범위 실측: 스킬 paths 와 defaultEnabled

> Snapshot 2026-11-12. Claude Code 2.1.316, `claude -p --model sonnet --plugin-dir /tmp/probe-skp/plug`, 프로젝트는 빈 git 저장소 `/tmp/probe-skp/proj`(파일 `x.zzz`). 비용 합계 약 $0.35(7회).

프로브 플러그인: 스킬 `zz-always`(설명에 ALPHA-ALWAYS, 트리거 pineapple)와 `zz-pathed`(설명에 BRAVO-PATHED, 트리거 mango, `paths: ["**/*.zzz"]`).

| # | 조건 | 결과 |
|---|---|---|
| A | 파일을 읽지 않음, 모델에게 목록에 마커가 있는지 물음 | 둘 다 YES |
| B | `x.zzz` 를 Read 한 뒤 같은 질문 | 둘 다 YES |
| A2 | 읽지 않음, BRAVO-PATHED 설명을 그대로 인용하라 | `probe-skp:zz-pathed: Probe skill BRAVO-PATHED. Use when the user says mango.` 를 그대로 인용 |
| C | plugin.json `defaultEnabled: false` | init 의 skills 와 plugins 에 없음(플러그인 꺼짐) |
| D | C + 프로젝트 `.claude/settings.json` `{"enabledPlugins":{"probe-skp@inline":true}}` | 두 스킬 모두 있음(켜짐) |
| E | defaultEnabled 없음(기본 켜짐) + 프로젝트 `enabledPlugins` false | 스킬 없음(꺼짐) |

## 결론
- 스킬 frontmatter 의 `paths` 는 스킬 설명을 처음 목록에서 빼지 않는다. 설명은 파일을 건드리기 전부터 모델 맥락에 있다. 그래서 팩의 상시 비용(스킬 설명)은 플러그인을 끄는 것으로만 줄인다.
- `defaultEnabled: false` 는 사용자가 따로 정하지 않으면 플러그인을 끈다. 프로젝트 `enabledPlugins: true` 가 이를 켜고, 기본 켜짐 플러그인도 프로젝트 `false` 로 끌 수 있다. 본체 설명: "Explicit enabledPlugins values always win, and a plugin required by an enabled dependent is enabled regardless of this value."
- `--plugin-dir` 플러그인의 키는 `<이름>@inline` 이다. 마켓 설치본은 `<이름>@<마켓>` 이고 본체의 같은 함수(enabled 판정에 manifest.defaultEnabled 를 넘김)를 탄다. 마켓 설치본으로는 재지 않았다(`~/.claude` 설치 상태를 바꿔야 해서).

다시 재기: `/tmp/probe-skp` 를 위 표대로 만들고 `claude -p "Reply with just OK." --plugin-dir <plug> --output-format stream-json --verbose` 의 `system/init` 이벤트에서 `skills` 를 본다.
