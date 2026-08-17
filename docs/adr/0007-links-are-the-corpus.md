# ADR-0007: real links are the front-door corpus — the by-construction `populations/` corpus retires

- **Status:** Accepted
- **Date:** 2026-08-10
- **Decides:** what the standing verdict corpus is, now that real SudokuMaker
  links drive the full front door (spec [#185](https://github.com/caneff/gridfind/issues/185),
  E2E suite [#186](https://github.com/caneff/gridfind/issues/186)) and the
  `populations/` corpus predates it.

## Context

Two corpora assert the same thing by different roads. `populations/*.json` holds
by-construction `Puzzle` + `WorkingState` pairs whose verdict is named by the
filename, run straight through `verdict()` — no decode, no link. `links/*.txt`
holds real SudokuMaker share links, driven through `cli.main`, the actual front
door: decode, then `verdict`, then the printed witness checked back against the
puzzle by `validate_witness`.

An overlap pass settled what `populations/` buys over `verdict_test.py`. Of its
17 cases, 13 already have an exact or isomorphic `.kind` assertion in
`verdict_test.py` — the corpus was carrying duplicates. The remaining 4 test
**working-state breaks**: a placement outside its own candidate set, givens and
a placement and a candidate agreeing, a row repeat forced through candidate
sets, and the line-count too-few direction. Those 4 are the only real coverage
in the corpus, and a share link can never carry them — a link serializes givens
and constraints, never a `WorkingState`. So links cannot replace them, and
`verdict_test.py` should hold them as plain code, where every other working-state
assertion already lives.

That leaves `populations/` as 13 duplicates plus a small harness. A real link is
the stronger corpus for everything a link *can* express: it exercises the decode
path the by-construction JSON skips, and a found link pairs with a witness that a
human can confirm in SudokuMaker itself — the app is the oracle, not our own
`verdict`.

## Decision

1. **Real links are the standing corpus.** Every verdict a link can express is
   asserted through `links/` and `cli.main`, not through a parallel
   by-construction JSON corpus.

2. **`populations/` and `population_test.py` retire.** The 4 working-state cases
   move into `verdict_test.py` as code; the 13 duplicates and the harness are
   deleted.

3. **Every link-reachable variant owes a found link and a broke link.** The six
   today are classic, jigsaw, XV, kropki, cage, and Schrödinger. An E2E test
   enforces it: it loops the one-to-one `DECODER_REGISTRY` wire types (kropki,
   XV, cage) and carries a short explicit list for the ones that are not
   one-to-one — classic and jigsaw both ride wire type 1, and Schrödinger
   arrives by the `--schrodinger` flag, not a wire type. A new decoder shipped
   without its two links turns the suite red.

4. **The witness is verifiable by hand.** `scripts/verify_links.py` (fronted by
   `just verify-links`) writes a found link's witness back into the link's own
   document as givens and re-encodes it into an openable solution-link. One click
   shows the completed grid on the real puzzle; SudokuMaker validates what
   `verdict` claimed.

## Considered options

- **Keep both corpora.** Rejected: 13 of the 17 by-construction cases are
  duplicate assertions, and the 4 that are not belong in `verdict_test.py` as
  code, next to every other working-state test. Two roads to one assertion is
  maintenance with no coverage to show for it.

- **Fold everything into `links/`, delete `populations/` outright.** Rejected:
  the 4 working-state cases test breaks a share link cannot serialize. Deleting
  them loses real coverage; they move to code instead of vanishing.

- **Bind the found-and-broke policy to the granular layer.** Rejected: `board`,
  `rows-distinct`, and `cols-distinct` have no wire type — a link emits all three
  implicitly and none exists on its own, so there is no "rows-distinct-only"
  link to demand. The policy binds to the **link-reachable variant**, the grain a
  link can actually express.

## Consequences

- **Retracted:** `line-count-distinct` now decodes through the somedoku
  global-flag component and owes (and carries) a `found-*`/`broke-*` pair
  under the policy like any other link-reachable variant — see ADR-0017.

- **`board`, `rows-distinct`, `cols-distinct` are covered incidentally.** They
  ride inside every classic link and never carry their own, so the policy does
  not name them — classic's pair exercises them.

- **Link authorship is a human step.** A real link is born in the SudokuMaker
  app. The agent decodes, verifies, and can synthesize a full openable document
  where it knows the wire format; a link it cannot make, the setter provides. The
  corpus grows on demand, same as the supported puzzle set.

- **Current gaps become backfill work.** Applying the policy to today's `links/`
  shows the holes: jigsaw, Schrödinger, and XV are found-only; kropki and cage
  are broke-only. These are filled as authored, not by a blocking sweep.

- **A broke Schrödinger link is an open doubt, not a settled fact.** Schrödinger
  arrives by flag, so a broke link's infeasibility must ride on the givens the
  link carries. That such a link is constructible is likely but unproven —
  verify one builds before the policy demands it, else hand-author it.

## When to revisit

Revisit if a working-state break becomes expressible as a link — if SudokuMaker
grows a wire encoding for placements or candidate sets. The 4 cases moved to
`verdict_test.py` were moved *because* no link could carry them; that premise
failing is the signal to reconsider where they live.
