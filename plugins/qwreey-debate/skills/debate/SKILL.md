---
name: debate
description: Puts a choice you cannot settle alone, or have not reasoned through, to a debate. Two subagents take opposing stances on shared evidence, dig up what you have not checked (code, records, web), attack the weak grounds of the current proposal, offer alternatives and weigh each with pros and cons; you synthesize a table of disagreements and ready-to-apply wording, and the user decides. Use it for a name, a convention, wording loaded every session, or a design fork with costs on both sides, before fixing global wording, and whenever the user suggests it in plain words; not for facts a measurement or grep answers. 토론 붙여봐, 토론시켜 봐, 찬반 붙여, debate this.
---

# qwreey-debate:debate

Two papers that must each concede something show where the trade-off lies and surface what you did not know, so the user chooses from a table instead of from your single draft.

## When
- Use when you are torn between options, when a choice rests on your first idea and you have not tested it (a name you picked, a rule you drafted), when the answer depends on facts outside what you have read (ecosystem conventions, library behavior, how other projects do it), and when the user suggests a debate.
- Typical subjects: names, conventions, wording that loads in every session or repo, a design fork with costs on both sides.
- Do not use for a question a measurement, grep or probe answers: measure it and put the number in the evidence. Not for a small choice that is cheap to change later, a choice the user already made, a defect hunt or a full audit.
- Before launching, tell the user in one line: the question, the stances, models, rounds, rough cost.

## Positions
- Two stances on the axis where the real cost lies, each a proposal a careful person would hold, not a strawman. Default axis: P minimal (smallest change, fewest always-loaded tokens, no new mechanism) against Q broad (covers every repo and case, enforced by checks). Others: plain files against tool-centric, strict default against per-repo opt-in, keep the current proposal against replace it.
- When there is a current proposal (yours or a draft), both sides start by attacking its weakest grounds, then propose alternatives; each side weighs every alternative on the table, its own and the other's, with pros and cons. Most of a debate's value is this: bad grounds exposed, alternatives named, each with a clear trade-off.
- Do not tell either side which option you prefer; a debater handed your hypothesis tends to return it confirmed.
- sonnet and opus are one model family and share its tendencies and blind spots, so Claude-only debaters can agree on the same miss. If the user has a tool for another model family set up (the `qwreey-delegate:delegate` skill, an MCP server, a CLI), consider adding one voice from it when the question is a name or an ecosystem convention, or when your own framing may be the problem. Not by default; when one is available and you leave it out, say so in the launch line so the user can ask for it. Check that voice's quotes and claims before they reach the synthesis.

## Brief
Fill `${CLAUDE_PLUGIN_ROOT}/skills/debate/templates/brief.md`. Both debaters get the same text except the stance paragraph.
- Shared evidence: paths to read (the proposal under debate, measurements, earlier syntheses), or a dossier you write to `raw/` when the evidence is scattered. Put numbers you measured into it so both sides argue over the same facts.
- Tell them to gather more: read code and records beyond the list, and search the web or official docs when the question turns on outside facts. New evidence comes back with its source.
- The user's words verbatim, and decisions already made under "do not reopen".
- Language: prose in the user's language; proposed wording in the language it will be written in (English for a skill or rule, the records language for a record).
- opus for wording and design; sonnet is enough for one narrow name. Launch both at once; in round 1 neither sees the other.

## Rounds
- One round is the default: from two independent papers you can usually pick a side per issue.
- Add a rebuttal round only when a split turns on a fact one side can check in the other's paper (a number, a path, a measurement), or each side holds half of a better answer. Continue each debater in its own context with the other's round-1 paper and your fact check. Each round roughly doubles the cost.
- When the split is a measurable fact, measure instead of a second round (replay recent commits, a probe, a trigger test). If the measurement cannot separate the options, follow the user's stated preference rather than debating more.

## Synthesis
You synthesize; the debaters do not vote. Fill `${CLAUDE_PLUGIN_ROOT}/skills/debate/templates/synthesis.md`:
- Facts both sides confirmed (including new evidence you checked), then what both accept.
- A table of disagreements: issue, P, Q, chosen side and why.
- Alternatives raised, each with its pros and cons as the papers argued them.
- The proposed wording in a code block, ready to apply.
- What you did not accept and why; what the debate found to fix regardless of the outcome.
- Questions for the user with plain options. New names, fields, mechanisms and conventions go to the user even when the evidence leans one way.

Show it to the user in their language before applying anything.

## Record
- `.claude/audit/NN-<topic>/synthesis.md` (next free NN), unless the repo's `.claude/README.md` says otherwise. It is a snapshot: frontmatter `format: 1`, `title`, `description` (the conclusion), the snapshot header line, and a line naming the stances, the models, the rounds and the user's verbatim answer. Write it after the user answers, since snapshots are not edited later.
- Papers, rebuttals and the dossier go to `raw/` beside it. Check that `raw/` is git-ignored (`.claude/**/raw/`) and add the pattern if not. `raw/` is not committed, so the synthesis quotes whatever it relies on instead of pointing into `raw/`.
- Add the folder to `.claude/audit/README.md` if the repo keeps one. The decision itself lands in the living doc it changes (a plan, a decision record, the target file).

## Cost
Two opus debaters, one round: about $1; two rounds: about $2-3. These are estimates; web research adds to them. An external voice runs against that tool's own quota.

## Failure modes
- Both sides converge on an answer a grep of the ecosystem disproves. Agreement is a claim to check, not proof.
- A paper rests on a wrong number, path or source (it measured the wrong root, a path lost a folder, a web claim misread its page). Check every number, path and source the synthesis relies on.
- A side reopens a settled decision or re-proposes a rejected one; the "do not reopen" list stops most of it.
- You take part as a voice and read the papers first. Write your own view to `raw/` before reading theirs.
- Votes tie, and users overturn majorities; reasons decide.
