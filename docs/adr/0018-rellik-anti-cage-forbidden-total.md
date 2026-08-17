# ADR-0018: the Rellik/Anti cage bans a forbidden total; its value carries the total

- **Status:** Accepted
- **Date:** 2026-08-17
- **Decides:** how a SudokuMaker link declares an anti-cage (Rellik) — the name
  that selects it, the channel that carries its forbidden total, and what the
  rule forbids
  (spec [#427](https://github.com/caneff/gridfind/issues/427), a second
  cage-selector kind on the named-marker-cage pattern of
  [ADR-0012](0012-named-marker-cages-retire-the-color-channel.md)).

## Context

A **rellik** (anti-) cage is the reference solver's Rellik rule: no non-empty
group of the cage's cells may sum to a chosen forbidden total. It is the mirror
of a killer cage, which requires its cells to sum *to* a target.

Two questions had to be answered to support it, and ADR-0012 already answered
the shape of both for the killer and modifier cages: a named `type 2001`
cosmetic cage selects a rule by its top-level `name`, and a cage's numeric
`value` carries whatever total that rule needs. A killer cage (`Sum`/`Killer`)
reads `value` as its target sum (ADR-0008); a modifier cage reads its `k` from
the name instead (ADR-0016). The rellik cage needs a name of its own and a
forbidden total — the same two channels, nothing new.

The rule itself is a subset-sum ban over an unknown number of groups, which
raises a model-size question a killer cage never has: a cage of `n` cells has
`2^n - 1` non-empty subsets, and stating `sum(group) != target` for every one
of them grows fast.

## Decision

**A `Rellik`/`Anti`-named `type 2001` cosmetic cage graduates to `cage` +
`rellik-cage`, its numeric `value` read as the forbidden total.** This reuses
the ADR-0012 named-marker-cage pattern for a second cage-selector kind
(`"rellik"`, beside `"killer"`), so there is no new wire-type.

1. **Name selects the rule.** `Rellik` and `Anti` join the recognized
   cage-selector names, case-insensitive and trimmed, through the same
   `naming` registry every marker cage uses. An unrecognized cage name still
   follows the uniform loud warn-drop (ADR-0012) — never a silent skip.

2. **`value` carries the forbidden total.** The decoder reads the cage's
   numeric `value` with the same string-to-int parse a killer sum uses, but
   feeds it to `rellik-cage` as the total to *ban* rather than to `group-sum`
   as the total to *require*. A blank, non-numeric, or zero `value` drops only
   the second constraint: the no-repeats `cage` still stands alone, exactly as
   a sumless killer cage does.

3. **`cage` owns distinctness, `rellik-cage` owns the ban.** Graduation emits a
   `cage` (`distinct-over: "digit"`) alongside `rellik-cage` over the same
   cells, the same two-constraint split killer uses (`cage` + `group-sum`,
   ADR-0009). The `rellik-cage` layer states no distinctness rule; it emits one
   `sum(group) != target` per surviving group and reads each cell through
   `value_expr`, so a doubler or S-cell inside the cage counts by its worth
   (ADR-0009).

4. **A sound size-band prune bounds the group count.** Enumerating all
   `2^n - 1` subsets is wasted model size once a cage grows. A group of size
   `k` can reach the target only if the target falls within the sum of the `k`
   smallest and `k` largest per-cell value bounds across the cage's cells, so a
   whole size class is dropped at once when the target is out of its reach. The
   band is a **sound over-approximation**: it reads only per-cell bounds and
   never assumes the composed `cage`'s distinctness, so it never drops a group
   that could reach the target even where a setter left the no-repeats half
   off. A tighter, distinct-digit-aware band is deferred until a real puzzle's
   group count bites.

## Consequences

- A setter draws a cosmetic cage on SudokuMaker, names it `Rellik`/`Anti`, and
  types the forbidden total into its value — no out-of-band flag, no new
  wire-type.
- The forbidden total lives on the cage `value` channel, its one home. The
  killer sum, the rellik total, and a modifier's `k` are read from exactly one
  place each, so a reader knows where any cage's number comes from.
- The prune trades minimum model size for a correctness floor that holds even
  on a malformed link that carries the ban without the no-repeats half.
