---
name: agent-docs
description: Conventions for documents a model reads to act, such as CLAUDE.md, SKILL.md, references, agent definitions and rules. Keep current facts, instructions and a one-sentence why; move history (who decided and when, audit or round numbers, measurement tags, change narration, correction banners) to the commit message or an existing ledger. Use it whenever you write or edit such a file, when a qwreey-conventions hook notice names lines you added, and before committing doc edits. 문서 규칙, 스킬 문서 정리, 모델용 문서 정리.
argument-hint: "[file or note]"
---

# qwreey-conventions:agent-docs

A model reads these files to decide what to do next. Every sentence should change that decision.

Test: if deleting a sentence would not change what the model does, it does not belong here.

## When a hook notice arrives

The notice names a file and the line numbers you added, with the category. Fix those lines in the same pass:

1. Decide per line with the test above. A sentence that changes behavior stays, rewritten as a present-tense fact.
2. A sentence that only records how the rule came about moves out (below).
3. Do not touch lines you did not add, and do not start a cleanup of the whole file unprompted. Bulk cleanup is for when the user signals there is room for it. Old problems in the files you edited are counted quietly and shown to the user once at turn end as one Korean line; the hook shows it, you do not repeat it.

For a cleanup the user asked for, `python3 -I "${CLAUDE_SKILL_DIR}/../../scripts/conventions-scan.py" scan [paths]` lists every flagged line in whole documents, so you need not read each file to find them; its `fix` only removes invisible characters from prose, and the history lines are yours to rewrite.

If the flagged text is a deliberate exception (for example a trigger phrase that must be quoted), leave it and mention it once in your final report.

Example. Before: `Since 2026-11-10 (audit/18) the hook only reads added lines; previously it scanned whole files.` After: `The hook reads only the lines added by the current edit.` The dates, the audit path and the old behavior go to the commit message.

## What stays

- Current facts and instructions in the present tense.
- One sentence of why when the reason changes behavior ("because the cache is shared, runs must lower their OOM rank first").
- Pointers the model would open or run during the task: a reference file, a snippet, a script, a section of a reference. Routing by section number is a pointer and is fine.
- Version scope stated as a fact ("Requires luau 0.742 or later"). Confirmation metadata (`last_confirmed`) lives in frontmatter, or in one `status:` line per section. A `status:` line is not checked.
- Public ids and standard numbers.
- Quoted user wording only when the wording itself is the instruction, such as a trigger phrase or an exact output string.

## What moves out

- Who decided something and when; dates in the body.
- Audit, round and session numbers and paths; measurement-source tags; decision ids.
- Change narration: `previously X`, `recently`, `as of` without a version, `last week`. Rewrite it as the current fact.
- Correction banners (`fact fix`, `correction:`). Apply the correction to the text and drop the banner.
- User quotes that explain history rather than instruct.

**Move, do not delete.** Deleting provenance loses what a later maintainer may need to trace a decision, so put the history in a place that already exists: the commit message (the default), a ledger or decisions file the repo keeps, or a CHANGELOG. Do not create a new file just to hold history. If a sentence is both history and useful, split it: the fact stays, the provenance moves.

## Entry documents and references

| Kind | Files | Flagged |
|---|---|---|
| Entry | CLAUDE.md, SKILL.md, agents, rules, other files under a skill outside `references/` | dates, `audit/`, `session/`, `handoff/` paths, round numbers, decision phrases, measurement tags, change narration, a ledger id with no `.md` path on the same line |
| Reference | `skills/**/references/*.md` | decision phrases, round numbers, `audit/<n>` provenance, measurement tags, correction banners |

References may carry dates, ids and `previously X` because their job includes explaining old patterns. The entry document is what is loaded every time, so it stays lean.

Text inside frontmatter, code fences, inline code, URLs and path tokens is not checked: a date in a path or a quoted command is data.

## Ledger ids

A ledger or decision id stays only on a line that also names its file (a `.md` path), and only when that file ships together with the document: same skill or plugin root. An id that points outside what travels with the file is a dead end for a reader, so give the id and its file, or drop the id.

The hook checks that the line names a `.md` file that exists inside the plugin holding the document (the repo, outside a plugin), looked up from the document's folder, the plugin root or the repo root.

Research ledgers whose numbers are the structure (numbered entries that other documents cite) are not checked. An entry document may point to such a ledger by number.

## Shape of the text

- Skill description: what it does plus when to use it, in English, third person, a little pushy so it is not under-triggered, with a few Korean trigger phrases at the end. The body is usage: how to call, what comes back, what to do next.
- Exception: a skill with `disable-model-invocation: true` gets a menu-line description (any language, no trigger phrases), since the model does not see it; only the user reads it in the `/` menu.
- Text that passes between models (skills, agent prompts, hook messages) is English. Only wording meant for the user is Korean.
- The hook checks the first three on lines you add: a `SKILL.md` description that is not English before its trailing Korean trigger phrases, has no when-clause or speaks in the first or second person, and a mostly Korean line in a model document that is not already written in Korean.
- Explain the principle once rather than listing cases; the model generalizes.
- Rationale for maintainers goes in the skill's own `references/rationale.md` (opened on demand, linked in one line from the body) or in a docs folder outside the skill, not in the body.
