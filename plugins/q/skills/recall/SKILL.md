---
name: recall
description: Find what earlier sessions discussed or decided, using the saved session records, without reading them in the main context. Use for "what did we decide before", "what problem did we have with X", "why is X this way", "find the earlier discussion of Y". Not for facts that git log or the current files already answer.
---

# /q:recall — look things up in session records

Records are **snapshots** of what was discussed at that time. They may be stale; reading them is slow and heavy, so do it only for a specific need, and never read whole records in the main session.

Skip this skill when the answer is in `git log` / `git log -S` or the current files: look there first.

## Flow
1. **Locate** with a read-only haiku agent (location only, no judging). Brief:
   > Find candidate sections in session records for this need: `<need, with keywords and identifiers verbatim>`.
   > Sources: coderag global docs if available; otherwise `grep -rn -i` over `<store records dir>` (`session-log home` / the hook text give paths: `~/.local/share/session-log/<project-key>/records/`) and the repo records home (`session-log home`). Records have `## <date time> · <trigger>` section headings, an `id: … note: L<a>–L<b>` meta line, and `### …` parts.
   > Return at most 8 lines: `file | section heading | line range in the file | one-line reason it may matter`. Do not read whole files, do not judge whether anything is true, do not draw conclusions.
2. **Read and summarize** with a sonnet agent given only the located sections. Brief:
   > Read only these sections: `<file + line ranges>`. Need: `<need>`. Summarize what the need requires.
   > Records are snapshots: for every decision or fact give the date of the record, cite the record line and its transcript ref `(L…)`, and where cheap check it against the current files and `git log` and mark it `still true`, `changed` (say how) or `unverified`. Quote user directives verbatim. Do not add anything the sections do not say.
3. **Main session**: verify the claims you will act on yourself before acting. `unverified` is not a fact.

Notes: `⚠` items failed the mechanical source check; treat them as unverified. Records still pending import are in the external store, imported ones in the repo records home; search both.
