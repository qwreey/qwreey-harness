---
name: debate
description: Settle a decision with real trade-offs (wording loaded in every session, a convention, a name, a design fork) by having two subagents argue opposing stances from the same evidence, then synthesizing agreements, a table of disagreements with the chosen side and why, and ready-to-apply wording for the user to decide. Use it when the user asks for a debate, and before fixing global wording or a convention; not for facts a measurement or grep answers. 토론 붙여봐, P/Q 토론, 찬반 토론, 문구 토론.
---

# debate - two opposing stances, one synthesis, the user decides

Two papers that must each concede something show where the trade-off lies, and the user chooses from a table instead of from your single draft.

## When
- Use for wording that loads in every session or repo, conventions, names, a design fork with costs on both sides, and whenever the user says to settle something by debate.
- Do not use for a question a measurement, grep or probe answers: measure it and put the number in the evidence. Not for a choice the user already made, a defect hunt or a full audit.
- Before launching, tell the user in one line: the question, the two stances, models, rounds, rough cost.

## Positions
- Two stances on the axis where the real cost lies, each a proposal a careful person would hold, not a strawman. Default axis: P minimal (smallest change, fewest always-loaded tokens, no new mechanism, low cost for the writer) against Q broad (covers every repo and case, enforced by checks). Other axes that worked: plain files against tool-centric, strict default against per-repo opt-in.
- Do not tell either side which one you prefer; a debater handed your hypothesis tends to return it confirmed.
- A third voice earns its place when the question is a name or an ecosystem convention, or when your own framing may be the problem: one other model family through `qwreey-delegate:delegate` (codex for names with the whole context in the prompt, agy for a root cause outside the frame). sonnet and opus count as one family. Check its quotes before they reach the synthesis; it invents and overstates more often.

## Brief
Fill `templates/brief.md`. Both debaters get the same text except the stance paragraph.
- Shared evidence: paths to read (the draft under debate, measurements, earlier syntheses), or a `dossier.md` you write when the evidence is scattered. Put numbers you measured into it so both sides argue over the same facts.
- The user's words verbatim, and decisions already made under "do not reopen".
- The answer shape and a word cap; read-only; every claim cites a file:line or a command and its output.
- opus for wording and design; sonnet is enough for one narrow name. Run both in the background at once; in round 1 neither sees the other.

## Rounds
- One round is the default: from two independent papers you can usually pick a side per issue.
- Add a rebuttal round only when a split turns on a fact one side can check in the other's paper (a number, a path, a measurement), or each side holds half of a better answer. Continue each debater in its own context with the other's round-1 paper and your fact check. Each round roughly doubles the cost.
- When the split is a measurable fact, measure instead of a second round (replay recent commits, a probe, a trigger test). If the measurement cannot separate the options, follow the user's stated preference rather than debating more.

## Synthesis
You synthesize; the debaters do not vote. Fill `templates/synthesis.md`:
- Facts both sides confirmed, then what both accept.
- A table of disagreements: issue, P, Q, chosen side and why.
- The proposed wording in a code block, ready to apply.
- What you did not accept and why; what the debate found to fix regardless of the outcome.
- Questions for the user with plain options. New names, fields, mechanisms and conventions go to the user even when the evidence leans one way.

Show it to the user in their language before applying anything.

## Record
- `.claude/audit/NN-<topic>/synthesis.md` (next free NN): a snapshot with frontmatter `format: 1`, `title`, `description` (the conclusion), the snapshot header line, and a line naming the stances, the models, the rounds and the user's verbatim answer. Write it after the user answers, since snapshots are not edited later.
- Save the papers (`round1-P.md`, `round1-Q.md`, `round2-*`, `dossier.md`) when the synthesis cites them; otherwise the synthesis alone is the record. Add the folder to `.claude/audit/README.md`.
- The decision itself lands in the living doc it changes (PLAN, a decision record, the target file).

## Cost
Two opus debaters, one round: about $1. Two rounds: about $2-3. A third voice adds one external run against that tool's quota.

## Failure modes
- Both sides converge on an answer a grep of the ecosystem disproves. Agreement is a claim to check, not proof.
- A paper rests on a wrong number or path (it measured the wrong root, a path lost a folder). Check every number and path the synthesis relies on.
- A side reopens a settled decision or re-proposes a rejected one; the "do not reopen" list stops most of it.
- You take part as a voice and read the papers first. Write your own view to a file before reading theirs.
- Vote counts tie, and the user has overturned majorities; reasons decide.
