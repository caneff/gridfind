# ADR-0006: Schrödinger working-state directives are hard-coded, not layer-registered

- **Status:** Accepted
- **Date:** 2026-08-09
- **Amended:** 2026-08-15 — a sixth directive, `SCellMarkRestriction`, joined
  the original five, and the six dataclasses moved into `s_directives.py`
  beside the codec that already lived there, closing the two-file split this
  ADR originally left open ([#463](https://github.com/caneff/gridfind/issues/463),
  spec [#462](https://github.com/caneff/gridfind/issues/462)). See "One home:
  dataclasses, union, and codec together" below.
- **Decides:** how [#142](https://github.com/caneff/gridfind/issues/142) carries
  the Schrödinger working-state directives on `WorkingState`.

## Context

`CONTEXT.md` describes the working-state grammar as extensible: "Each active
layer registers its own directives on top." Issue #142, which adds the
Schrödinger directives (singleton pin, S-cell pin, bare singleton, bare S-cell,
half S-cell), inherits that language and reads, on its face, as a mandate to
build a registration seam — a mechanism by which a layer publishes directive
types and `WorkingState`'s JSON dispatches to them.

No such seam exists. `WorkingState` is a closed frozen dataclass with two
fields, `places` and `candidates`, and hand-written `to_json` / `from_json`
that name those keys directly. The generic engine↔layer authoring contract —
the surface a directive-registration mechanism would belong to — is already
owned by a separate effort, issue #26. And only one layer, `schrodinger`, has
directives at all.

## Decision

The Schrödinger directives are **hard-coded on `WorkingState`, no registration
seam**. They land as one new field, `s_directives`, holding a tuple of small
frozen dataclasses that share a `kind` tag. `to_json` writes a single list of
`{kind, address, …}` objects; `from_json` dispatches on a local `kind → class`
dict and defaults the field to empty when the key is absent, so existing JSON
still parses. The core `places` / `candidates` fields are untouched.

"Layer-registered" is read as describing #26's eventual seam, not a thing #142
must stand up. Building a registration mechanism for a single layer's directives
is a plugin system with one plugin — surface with nothing behind it.

## Considered Options

- **A registration seam now** — a layer publishes its directive types, and
  `WorkingState` serialization dispatches through a registry. Rejected: it is
  #26's scope, and it pays the full cost of an extension point to host exactly
  one occupant.
- **Five parallel flat fields** (`singleton_pins`, `s_cell_pins`, …), each a
  tuple, each with its own JSON key and `from_json` branch — mirroring
  `places` / `candidates` literally. Rejected: it smears one layer's grammar
  across five fields and five wire keys; a single tagged list holds it in one
  place without reintroducing dispatch-by-layer.

## When to revisit

When a **second** directive-bearing layer arrives and needs its own working-state
grammar. That is the trigger for #26 to build the real registration seam, and
`s_directives` becomes its first migration — a concrete second occupant, not a
speculative one, is what justifies the extension point.

## One home: dataclasses, union, and codec together (2026-08-15 amendment)

The original decision landed the six dataclasses (a sixth, `SCellMarkRestriction`,
followed later — ADR-0014) in `puzzle.py` as "bare schema," while the `kind`-tag
codec (`s_directive_to_dict`/`s_directive_from_dict`) and the pair guard
(`validate_s_cell_pair`) lived in `s_directives.py`. The two modules imported
each other's *module* (never top-level names) to break the resulting cycle —
`puzzle.SDirective` referenced from `s_directives.py`, `s_directives.validate_s_cell_pair`
called from `puzzle.py`'s `SCellPin.__post_init__`. That split, plus the
Schrödinger-specific isinstance ladder `applier.py`'s model-application needs
and the digit-count dispatch `sudokumaker/cells.py`'s decode needs, meant a
directive-shaped fix could touch four files.

The dataclasses, the closed `SDirective` union, and the codec now all live in
`s_directives.py` — one module owns the six directives' full schema and wire
format. `puzzle.py`'s `WorkingState` imports `SDirective` and the two codec
functions from there for its own `to_json`/`from_json`; nothing in
`s_directives.py` imports `puzzle`, so the cycle this ADR's original text
described is gone, not merely worked around. `applier.py` (model application)
and `sudokumaker/cells.py` (SudokuMaker-wire construction) now import the six
dataclasses from `s_directives.py` instead of `puzzle.py`; those two remain
separate homes by necessity — one turns a directive into a CP-SAT constraint
(needs `Engine`/`ortools`, which `puzzle.py`'s schema-only contract forbids),
the other turns a marker cage's raw `value` into a directive (a SudokuMaker
decode concern, not a persistence-format concern) — but both now read the
one schema `s_directives.py` defines rather than each carrying its own copy.

This does not revisit the no-registration-seam decision above: the six
directives are still hard-coded, not registered, and the closed-set/no-seventh
reasoning is unchanged. It only collapses the artificial two-file split within
that hard-coded design.
