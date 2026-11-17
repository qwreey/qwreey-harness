# .claude records

Agent records for claude-doctor, laid out per the `coderag:agent-records` skill. `PLAN.md` stays at the repo root.
- [plan/](plan/) - open decisions (`decisions/Q<n>-*.md`) and the current plan (`now.md`), written by the desk (qwreey-desk); answered ones in `archive/plan/decisions/`
- [base/](base/) - settled decisions (`decisions/D-xx`)
- [research/](research/) - open drafts
- [audit/](audit/) - point-in-time measurements, reviews, debates (snapshots)
- [handoff/](handoff/) - handoffs to other sessions (snapshots)
- [sessions/](sessions/) - imported session records (snapshots, no README)
- [archive/](archive/) - living records that left active (no longer a current source)
- [scopes/](scopes/) - records about one plugin, pack or `home/` part, under its repo path (`scopes/plugins/q/audit/`, `scopes/packs/luau-kb/`, `scopes/home/.claude/audit/`), with the same folders inside

Old paths: before 2026-11-12 these lived at the repo root (`audit/`, `decisions/`, `drafts/`, `handoff/`); the old-to-new map is [audit/39-records-experiment/move-map.tsv](audit/39-records-experiment/move-map.tsv). Other repos may still cite the old paths.
