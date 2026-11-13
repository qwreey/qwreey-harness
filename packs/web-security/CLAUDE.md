# web-security (pack development)

Default-off domain pack: one path-scoped rule (`rules/web-security.md`), one skill (`skills/hardening/`, checklists in `references/`), and `coderag.toml`. How it is enabled and injected: `docs/how-it-works.md`; pack conventions for all packs: `packs/README.md`.

## Tests
`timeout 120 python3 -I tests/test-web-security.py </dev/null` (exit 0 = pass). The injection cases need the coderag binary and are skipped without it.

## Rules for this pack
- No `hooks/` folder: coderag injects the rule, and a pack hook would inject it twice. The test asserts this.
- The pack folder ships whole into the plugin cache, so it holds only what runs plus README, docs and this file. Development material goes in the repo's `.claude/packs/web-security/`.
- The rule body is English, one principle per line with a link to its checklist reference; facts and examples stay in `references/`. Keep it about 20 lines, since it is injected on every matching file open.
- A checklist item is a mistake that really shipped; add new ones with that bar.
- Bump `version` in `.claude-plugin/plugin.json` when the payload changes, so hosted installs update.
