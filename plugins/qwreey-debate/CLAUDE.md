# qwreey-debate (plugin development)

One model-invoked skill, `qwreey-debate:debate`, with two templates (`skills/debate/templates/brief.md`, `synthesis.md`). No hooks, no ambient, no agents. The procedure the model follows is `skills/debate/SKILL.md`; flow, records and the evidence behind the defaults: `docs/how-it-works.md`. `README.md` is for people deciding whether to install.

## Tests
No automated test. After a change, run `claude plugin validate plugins/qwreey-debate` from the repo root.

## Rules for this plugin
- Model-facing text (SKILL.md, templates) is English and follows `plugins/qwreey-conventions/rules/agent-docs.md`. Provenance (audit numbers, which debate showed what) goes in `docs/how-it-works.md` or the commit message, not in the skill.
- Do not restate what Claude Code's Agent tool description already covers (writing a brief, background runs, notifications, SendMessage). The skill adds only the debate shape: stances, shared evidence, rounds, synthesis, records.
- No hard dependency on another plugin. An external model voice is optional and goes through whatever tool the user has set up; `qwreey-delegate:delegate` is one example, not a requirement.
- The defaults (two opus debaters, one round, synthesis only in `.claude/audit/NN-<topic>/`, papers in git-ignored `raw/`) are user decisions; change them only with the user.
- Keep the description's Korean trigger phrases; users usually suggest a debate in plain words.
