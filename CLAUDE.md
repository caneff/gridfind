@AGENTS.md

## Coding invariants (always on)

- **One home per behavior — no parallel implementations.** When two call sites
  need the same decode, walk, lookup, or assembly, route both through one shared
  seam; do not hand-roll a second copy that reads the same data a different way.
  A parallel implementation drifts silently: a fix or new constraint lands in
  one copy, the other keeps the old behavior, and the two verdicts disagree on
  the same puzzle with nothing red to show it. This is the repo's dominant
  refactor — killer cages, the edge-clue decoders, `decode_cell`/`write_cell`,
  the decoder registry, the region-map resolver, the active/inert predicate, and
  witness assembly were each collapsed to a single home after a second copy
  appeared.
- **Unknown or unmodeled input fails loud — warn to stderr or raise, never
  drop silently.** An unrecognized flag, layer name, or constraint payload means
  the code's model of the link is incomplete, and a silent skip turns that into
  a wrong verdict the caller cannot see. Reject a genuinely unknown name
  (`UnknownLayerError`); for a constraint the engine cannot yet model but the
  link legitimately carries, drop it with a stderr warning
  (`_warn_on_dropped_constraints`, `_warn_dropped_negative`) so the run
  continues but the gap is visible. Silence is the one forbidden response.

Touching code? Read `CODING_STANDARDS.md` for the full standards.
