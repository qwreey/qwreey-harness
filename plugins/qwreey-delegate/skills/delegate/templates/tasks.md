<!--
The XML-tagged block layout and the findings JSON shape in B and E follow the style of OpenAI codex-plugin-cc
(plugins/codex/prompts/adversarial-review.md, schemas/review-output.schema.json), Apache-2.0,
https://github.com/openai/codex-plugin-cc . Wording here is our own. See THIRD_PARTY_NOTICES.md at the repo root.
-->

# Task prompt templates

The driver prepends the preamble (working environment rules). The templates here are the body that goes under `# Task`. Pick one, copy it to scratch and fill it in. Write paths relative to the worktree.

---

## A. Root cause (agy, worktree)

```markdown
Several open questions / review findings seem to come from the same mechanism. Do not treat them as separate defects; find the common root from above.

Read (canonical):
- <ledger path>, items <numbers> - the original text only. The classification table of earlier reviews is deliberately withheld so the frame does not lock in.
- <design source path>
- Code: <paths>, tests: <paths>

Wanted:
1. Root candidates, and for each: the items it explains and the items it does not.
2. Falsifiable evidence per candidate: file:line, and a runnable probe (the command you ran in the worktree and its output).
3. Do not get stuck in this frame - if you see other symptoms of the same root outside the item list, write them down.
If time runs short, look at <what> first.
```

## B. Narrow bug hunt (agy worktree, or codex empty with the code pasted)

Review-like tasks use XML blocks and end with the JSON contract below, so main can reproduce each finding mechanically. For codex `--mode empty`, paste the code numbered with `nl -ba` into `<scope>`.

```markdown
<role>
You are an outside bug hunter. Your job is to find defects in one mechanism, not to confirm the code is fine.
</role>

<task>
Mechanism under test: <one mechanism, e.g. nil holes in arrays and the n invariant / operations with itself (aliasing) / unsubscribe during dispatch>.
Target: <paths, or the pasted code below>. Base commit: <sha>.
</task>

<operating_stance>
Assume the mechanism breaks somewhere. Give no credit for intent or for the happy path working. Try to disprove the invariants the code relies on.
</operating_stance>

<scope>
Only the target modules, only this mechanism. Do not sweep other modules and do not report style, naming or cleanup.
Look first at: <hot spots, retries, empty input, re-entrancy, partial failure, ...>.
</scope>

<finding_bar>
Report a defect only if you can say what input triggers it, what happens, and what the expected behavior is, with its basis (canonical document section or public contract). One solid finding beats several weak ones. If you find none, say "no finding" and list what you tried.
</finding_bar>

<grounding_rules>
No claim without evidence: a file:line you read, or the output of a command you ran (command, actual output, exit code). Do not invent files, lines or behavior. Mark an inference as an inference and lower its confidence. If you propose a fix, say what it costs; measure it when it sits on a hot path.
</grounding_rules>

<structured_output_contract>
End your answer with one fenced ```json block and nothing after it, in this shape:
{
  "verdict": "no-finding" | "needs-attention",
  "summary": "<two sentences: ship or not, and why>",
  "findings": [
    {
      "file": "<path relative to the worktree>",
      "line_start": <int>, "line_end": <int>,
      "confidence": <0..1>,
      "recommendation": "<concrete change, with its cost if measured>",
      "evidence": "<the reproduction: command, actual output, exit code; or the quoted lines that prove it>"
    }
  ],
  "next_steps": ["<what main should check or run next>"]
}
Prose before the block may explain; the block alone is what main reads. Empty `findings` when verdict is "no-finding".
</structured_output_contract>
```

## C. Name review - three families (codex empty / agy / sonnet get the same body)

```markdown
# Naming review - <target in one line>

You are reviewing public API names. Judge them from the point of view of the library's USERS (<who>). Everything you need is below - do not look for files. Reply in Korean, concisely. Put your whole answer in one message.

## Context
- <One paragraph on the library: what it is, the value conventions, the conventions existing names set>
- <Similar existing names and what they mean - collision candidates>

## Names to judge
1. **<slot>.** <Exact behavior - arguments, return, errors, difference from existing ones>. Candidates: `A`, `B`, `C`.
   For each: your pick, a ranked shortlist (you may add one of your own), one or two reasons; flag a name that would mislead.
```

- Give the same body to codex (`--mode empty`), agy (`--mode empty`) and a sonnet subagent.
- Compare in one table (converge / diverge, with the reasons). The user decides.

## D. Outside opinion on a design decision (agy, worktree)

```markdown
For the two (or three) branches of decision <ID>, give an opinion as someone who does not know this repository's decision history.
Decision text: <path to the question section>. Related canon: <path>. Already rejected shape: <archive path> - to propose it again, argue what changed.
For each branch say what it blocks (reproduction path), and name blind spots (cases neither branch covers).
```

## E. Code review of pasted code (codex empty)

```markdown
<role>
You are an adversarial reviewer. Find the strongest reasons this change should not ship yet.
</role>

<task>
Review the change below. Focus: <focus>. Everything you need is in this prompt; do not look for files.
</task>

<operating_stance>
Be skeptical by default. Partial fixes and good intent earn nothing; a path that works only on the happy path is a weakness.
</operating_stance>

<attack_surface>
Weight these, then add what the code shows: <permissions and trust boundaries, data loss or duplication, retries and partial failure, ordering and re-entrancy, empty or timeout behavior, compatibility>.
</attack_surface>

<finding_bar>
Material findings only: what can go wrong, why this path is vulnerable, the likely impact, the smallest fix. No style, naming or speculative concerns. If the change looks safe, say so and return no findings.
</finding_bar>

<grounding_rules>
Every finding cites file:line from the numbered code below, or a quoted line. Do not invent code paths or runtime behavior. State inferences as inferences with lower confidence.
</grounding_rules>

<structured_output_contract>
The same JSON block as in B (verdict, summary, findings[file, line_start, line_end, confidence, recommendation, evidence], next_steps). Since you cannot run commands, `evidence` is the quoted lines and the reasoning chain that triggers the failure. Verdict is "approve" or "needs-attention".
</structured_output_contract>

<code>
<output of nl -ba per file, with a path header>
</code>
```
