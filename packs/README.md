# Packs

A pack is a domain-knowledge plugin in the `claude-doctor-market` marketplace with `"defaultEnabled": false`,
so it stays off everywhere until a repo turns it on. Skill `paths` do not hide a skill's description, so
scoping by project settings is what keeps a pack out of unrelated repos.

A repo turns a pack on in its `coderag.toml`: `[[packs]]` with `name = "<pack>"`. Then `coderag adapt --harness claude` adds
`"<pack>@claude-doctor-market": true` to `enabledPlugins` in `.claude/settings.json` (skills load) and never overrides an explicit `false`.
The pack's path-scoped `rules/*.md` are injected by the coderag plugin (`coderag@coderag-market`, PostToolUse `hook post-tool`) only for packs the
project lists; a pack ships no hooks of its own, so enabling the plugin alone injects nothing.
coderag resolves a listed name through the user's coderag config (`~/.coderag/coderag.toml`, or `$CODERAG_HOME`): each machine registers
every pack once with `[[packs]]`, `name = "<pack>"`, `path = "<pack folder>"`. An unregistered name is skipped silently, so doctor reports it.
`q:doctor` compares the two switches and recommends packs from toolkit markers (`PACK-MISSING`, `PACK-DRIFT`, `PACK-UNUSED`, `PACK-USER-LEVEL`, `PACK-NO-CODERAG`, `PACK-UNREGISTERED`).

Current packs: `web-security`, `luau-kb`.

A pack folder holds only what runs (skills, rules, tools, snippets, typedefs, and `coderag.toml`/`taxonomy.toml`,
which coderag reads from the pack root), because the plugin cache copies the whole folder per version. Development material that
nothing in the payload cites lives in `.claude/scopes/packs/<pack>/` (for luau-kb: `evals/`).
