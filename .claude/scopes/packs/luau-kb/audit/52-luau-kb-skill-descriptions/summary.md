---
format: 1
title: luau-kb skill description shrink
description: luau-kb skill descriptions cut from 6,420 to 3,647 chars keep sonnet recall (89% -> 92%, 0/17 false triggers); cut to 1,898 chars, symptom-phrased questions (engine-en, net-en) drop to 0/3
---
> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

Question: can the always-loaded luau-kb skill descriptions be shortened without losing auto-invocation (open item 9 of `audit/41-knowledge-packs-debate/synthesis.md`). Measured by a subagent (opus) with `claude -p --max-turns 1` per question, sonnet, hit = expected skill called in the first turn. Cost about USD 5.5. Raw outputs and scripts: `raw/` (git-ignored), also `/tmp/luau-kb-desc/`.

| variant | description chars | always-on tokens | sonnet recall | recall w/o docs-ko2 | near-miss false triggers | haiku recall (1 run) |
|---|---|---|---|---|---|---|
| base (current) | 6,420 | ~2,691 | 73/82 (89%) | 69/74 (93%) | 0/17 | 26/36 |
| v1 | 3,647 (57%) | ~1,771 | 109/118 (92%) | 103/107 (96%) | 0/17 | 29/36 |
| v2 (aggressive) | 1,898 (30%) | ~1,155 | 34/46 (74%) | 34/41 (83%) | 0/17 | 28/36 |

- v1 keeps concrete API/tool names, a "Use when <symptom>" clause, the Korean trigger phrases and a one-phrase boundary to the neighbor skill. v2 failed exactly where it dropped the symptom clause and API names (`engine-en` Tween Completed after Destroy, `net-en` RemoteFunction/BindableEvent limits: 0/3 each, base and v1 3/3).
- Misses in every variant: `docs-ko2` names no API (question flaw); `types-ko2` unstable. `engine-ko2` under v1 also calls roblox-net (a fair answer).
- No variant fired on the 17 near-miss questions (incl. 6 new: Neovim init.lua, LOVE2D dt, LuaJIT metatable bench, Lua 5.4 coroutine traceback, OpenResty shared dict, Unity Rigidbody).
- Samples are small (6-13 runs per skill): v1 shows "no measurable drop", not "better".
- Found: `packs/luau-kb/.claude-plugin/plugin.json` `defaultEnabled: false` makes `--plugin-dir` load the pack disabled, so `.claude/scopes/packs/luau-kb/evals/triggers/run.py` silently records "no trigger"; fix with a work-dir `.claude/settings.json` `{"enabledPlugins":{"luau-kb@inline":true}}` and `--setting-sources project`.
- Not measured: competition with other plugins' skills, the "real Luau repo" context condition.
- Proposed v1 text (not applied): `raw/v1-descriptions.diff`, `raw/v1.json`.
