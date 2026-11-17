# qwreey-license (plugin development)

One model-invoked skill, `qwreey-license:license` (`skills/license/SKILL.md`), and its script `scripts/license_text.py` (fetch, check, notice; usage in the module docstring). No hooks, no ambient, no agents. `README.md` is for people deciding whether to install.

## Tests
`python3 -I -X utf8 tests/test_license_text.py` (exit 0 = pass). It never touches the network: `http_get` is replaced by a reader of `tests/fixtures/` (`api/` holds GitHub licenses API bodies, `spdx/` SPDX license-list-data texts, both saved as fetched). `LICENSE_TEXT_LIVE=1` adds a live fetch of MIT and Apache-2.0 that also flags when the API text drifts from the fixtures. After a change, also run `claude plugin validate plugins/qwreey-license` from the repo root.

## Rules for this plugin
- The script must never produce license text that was not fetched: no bundled or remembered fallback. When both sources fail it exits 3. A bundled SPDX copy would need its own refresh path and is not built yet.
- Placeholders are filled only before the how-to-apply section (Apache APPENDIX, GNU "How to Apply These Terms"), which stays verbatim by default because it is a template for file headers; `check` accepts it filled or not.
- `check` treats every placeholder slot as a wildcard, so extra words next to the holder (a second copyright line) pass; every other word must match after whitespace is collapsed.
- Stdlib only, Python 3.11+ (`tomllib`), run as `python3 -I -X utf8` so Windows code pages do not matter; files are written UTF-8 with `\n`.
- The notice section format follows the repo root `THIRD_PARTY_NOTICES.md` (`## name`, `Files:` list, `Source:` line, fenced text).
- Choosing a license is the user's decision; the skill gives cautions, never a pick. Keep the description's Korean trigger phrases.
