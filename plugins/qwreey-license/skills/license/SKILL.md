---
name: license
description: Writes and checks license files from canonical text, never from memory. Helps the user choose a license, fetches the GitHub or SPDX text with year and holder filled, compares an existing LICENSE and manifest license fields with it, and appends third-party notices. Use when choosing a license, writing or changing LICENSE, NOTICE or THIRD_PARTY_NOTICES, or bringing in code, docs or assets from another project. 라이선스 파일 만들기, 라이선스 정하기, 오픈소스 고지, 서드파티 고지.
---

# qwreey-license:license

Never write license or notice text from memory: a remembered text drifts by a word or a clause and nobody compares it. Fetch it with the script.

Script: `python3 -I -X utf8 "${CLAUDE_SKILL_DIR}/../../scripts/license_text.py" <command>` (below: `license_text.py`). It needs network access to api.github.com or raw.githubusercontent.com. Exit 0 ok, 1 refused or mismatch, 3 fetch failed.

## Choose (the user decides)
Ask one question at a time and explain in plain words, in the user's language:
1. What is licensed: code, docs, game assets (models, images, sound), or a mix.
2. Public or private. With no license file nobody else may use the work (all rights reserved); a private repo may need none.
3. How it ships: source repo, package, built game or plugin, internal only.

Then give only the cautions that apply, briefly, and let the user pick:
- MIT, BSD, ISC: permissive; whoever copies the work must keep the copyright and license notice.
- Apache-2.0: permissive with a patent grant; redistributors keep the NOTICE file and mark files they changed.
- GPL, LGPL, AGPL in a dependency or vendored code: the combined work may have to ship under the same license with its source (AGPL also when used over a network). Raise it before such code enters a game or closed product.
- MPL-2.0: copyleft per file; changed MPL files stay open.
- Docs and assets: CC-BY requires credit where the work is used; Creative Commons advises against CC licenses for code. CC0 and Unlicense give up rights (public domain dedication).

## Write a LICENSE
1. Holder: propose `git config user.name` (the script's default) or the studio name and confirm with the user. Year defaults to this year.
2. `license_text.py fetch <SPDX-id> --year Y --holder "NAME" --out LICENSE`. It refuses if a placeholder is left or the file exists; pass `--force` only after the user agrees to replace the file.
3. Apache-2.0 and the GNU licenses have no copyright line to fill. Their how-to-apply section is a template for file headers and stays verbatim (`--fill-appendix` fills it); put the copyright notice where that section says.
4. Set the manifest `license` field to the same SPDX id (package.json, pyproject.toml, Cargo.toml, .claude-plugin/plugin.json).
5. Run `check`.

## Check an existing file
`license_text.py check [LICENSE] [--id ID]` compares with the canonical text ignoring whitespace, the title line and the year and holder, prints each differing span, and checks the manifest `license` fields in the same folder. Show the user any difference; whether to restore the canonical text is their call.

## Third-party notices
When code, docs or assets from another project enter the repo:
1. Read the upstream license and copyright line in the upstream repository's LICENSE file.
2. `license_text.py notice --name "<project>" --url <source URL> --id <SPDX-id> --files a,b --copyright "<upstream copyright line>"` appends a section to THIRD_PARTY_NOTICES.md (created if missing). If the upstream LICENSE differs from the canonical text, save it and pass `--text-file <file>` instead.
3. Apache-2.0 upstream: also carry the upstream NOTICE file's content. GPL-family upstream: tell the user before it enters the repo.

Re-running with the same name changes nothing; a section of that name with different content is left alone and reported.

## Offline
If the fetch fails (exit 3), tell the user and stop; retry when the network is back.
