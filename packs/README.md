# Packs

A pack is a domain-knowledge plugin in the `claude-doctor-market` marketplace with `"defaultEnabled": false`,
so it stays off everywhere until a repo turns it on. Skill `paths` do not hide a skill's description, so
scoping by project settings is what keeps a pack out of unrelated repos.

A repo enables a pack in `.claude/settings.json`: `"enabledPlugins": {"<pack>@claude-doctor-market": true}`.
`q:doctor` recommends packs from toolkit markers (`PACK-MISSING`, `PACK-UNUSED`, `PACK-USER-LEVEL`).

Current packs: `web-security`, `luau-kb`.

A pack folder holds only what runs (skills, rules, hooks, tools, snippets, typedefs, `.lsp.json`, and `coderag.toml`/`taxonomy.toml`,
which coderag reads from the pack root), because the plugin cache copies the whole folder per version. Development material that
nothing in the payload cites lives in `.claude/packs/<pack>/` (for luau-kb: `evals/`).
