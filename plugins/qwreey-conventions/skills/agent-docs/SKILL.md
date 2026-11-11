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
3. Do not touch lines you did not add, and do not start a cleanup of the whole file unprompted. Bulk cleanup is for when the user signals there is room for it.

If the flagged text is a deliberate exception (for example a trigger phrase that must be quoted), leave it and mention it once in your final report.

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

**Move, do not delete.** Put the history in a place that already exists: the commit message (the default), a ledger or decisions file the repo keeps, or a CHANGELOG. Do not create a new file just to hold history. If a sentence is both history and useful, split it: the fact stays, the provenance moves.

## Entry documents and references

| Kind | Files | Flagged |
|---|---|---|
| Entry | CLAUDE.md, SKILL.md, agents, rules, other files directly under a skill | dates, `audit/`, `session/`, `handoff/` paths, round numbers, decision phrases, measurement tags, change narration, a ledger id with no `.md` path on the same line |
| Reference | `skills/**/references/*.md` | decision phrases, round numbers, `audit/<n>` provenance, measurement tags, correction banners |

References may carry dates, ids and `previously X` because their job includes explaining old patterns. The entry document is what is loaded every time, so it stays lean.

Text inside frontmatter, code fences, inline code, URLs and path tokens is not checked: a date in a path or a quoted command is data.

## Ledger ids

A ledger or decision id stays only on a line that also names its file (a `.md` path), and only when that file ships together with the document: same skill or plugin root. An id that points outside what travels with the file is a dead end for a reader, so give the id and its file, or drop the id.

The hook only checks the syntax: it looks for a `.md` path on the same line. Whether that file really ships with the document is your judgment.

Research ledgers whose numbers are the structure (numbered entries that other documents cite) are not checked. An entry document may point to such a ledger by number.

## Shape of the text

- Skill description: what it does plus when to use it, in English, third person, a little pushy so it is not under-triggered, with a few Korean trigger phrases at the end. The body is usage: how to call, what comes back, what to do next.
- Text that passes between models (skills, agent prompts, hook messages) is English. Only wording meant for the user is Korean.
- Explain the principle once rather than listing cases; the model generalizes.
- Rationale for maintainers goes in a docs folder outside the skill, not in the body.
