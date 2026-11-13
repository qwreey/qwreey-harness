# Task prompt templates

The script prepends the preamble (working environment rules). The templates here are the body that goes under `# Task`. Pick one, copy it to scratch and fill it in. Write paths relative to the worktree.

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

## B. Narrow bug hunt (agy, worktree)

```markdown
The scope is one: <one mechanism, e.g. nil holes in arrays and the n invariant / operations with itself (aliasing) / unsubscribe during dispatch>.
Target modules: <paths>. Do not sweep every module.

For each defect:
- Reproduction probe (minimal code, command, actual output, exit code)
- Basis for the expected behavior (canonical document section or public contract)
- If you propose a fix, its cost (measure it if it is on a hot path)
If there is no defect, say "no finding" and what you tried.
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

- Give the same body to codex (`--mode empty`), agy (`--mode empty`, or worktree while empty mode is unverified) and a sonnet subagent.
- Compare in one table (converge / diverge, with the reasons). The user decides.

## D. Outside opinion on a design decision (agy, worktree)

```markdown
For the two (or three) branches of decision <ID>, give an opinion as someone who does not know this repository's decision history.
Decision text: <path to the question section>. Related canon: <path>. Already rejected shape: <archive path> - to propose it again, argue what changed.
For each branch say what it blocks (reproduction path), and name blind spots (cases neither branch covers).
```
