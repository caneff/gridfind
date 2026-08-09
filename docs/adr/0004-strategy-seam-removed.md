# ADR-0004: the witness-search strategy seam is removed

- **Status:** Accepted
- **Date:** 2026-08-09
- **Decides:** reopens [spec #4](https://github.com/caneff/gridfind/issues/4),
  decisions 30 and 33 (`gridfind.strategy`, the `Strategy` protocol, and
  `verdict`'s `strategy` keyword argument).

## Context

Decisions 30 and 33 gave `verdict`'s witness-search a `Strategy` seam on
purpose: pure-satisfaction was expected to be the core's own strategy, and a
downstream variant — quad-rank was named explicitly — was expected to
contribute a second, objective-guided strategy without a core rewrite. Map
decision 15a records the same reasoning: the racer "does not hardwire
pure-satisfaction — it takes a witness-search strategy."

That expected second occupant never arrived, and a later decision removed its
reason to. `CONTEXT.md`'s Verdicts section states plainly that the core races
a broke-proof against a witness-find, "never an objective solve," and that
**unknown** "carries no near-miss and no rank-error (both dropped with the
objective solve; map #1, out of scope)." Near-miss and rank-error were the
seam's expected second occupant's whole value — an objective-guided search
only pays for itself when its output feeds a rank or a near-miss. With both
out of scope, there is no result shape left for a second strategy to produce.

What remained was `gridfind/strategy.py`: a `Strategy` protocol with one
method, `PureSatisfaction`, whose `configure` body is `pass`, a
`PURE_SATISFACTION` singleton, and a `strategy` keyword argument on `verdict`
that every caller left at its default. No second implementation exists
anywhere in the tree, and no test exercised the seam directly — it was pure
surface with nothing behind it.

## Decision

1. **The strategy module is deleted.** `gridfind/strategy.py` — the `Strategy`
   protocol, `PureSatisfaction`, and `PURE_SATISFACTION` — is removed
   entirely, not deprecated.

2. **`verdict` drops the `strategy` parameter.** The witness-search runs
   CP-SAT's default search directly; there is no gridfind-side call that
   configures it, because there is nothing left to configure.

   `strategy=` shipped under `py.typed`, but it was internal-only in
   practice: three references in the whole tree, all inside gridfind
   (`strategy.py`, `verdict.py:25`, `verdict.py:66`), and no external caller.
   `py.typed` makes the removal type-visible to a downstream `ty`/`mypy` run,
   but there is no external usage for it to break — so the removal needs no
   changelog entry or version note.

3. **Decisions 30 and 33 are reopened, not erased.** They were the right call
   when made — the seam existed to host a concrete, named second occupant.
   The occupant's reason to exist left with the objective solve; the seam
   should have left with it too.

## When to revisit

Reintroduce the seam when a second strategy actually exists and needs to
shape the interface: a downstream layer that both (a) implements an
alternate witness-search and (b) has a result shape for that search's output
to feed (a near-miss, a rank, or similar) to fit through. A speculative
"someday a variant might want this" is not the trigger — a concrete second
implementation is. Until one lands, `verdict` runs pure-satisfaction search
directly, which is what `CONTEXT.md` already says it does.
