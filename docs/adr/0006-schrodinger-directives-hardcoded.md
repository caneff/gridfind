# ADR-0006: Schrödinger working-state directives are hard-coded, not layer-registered

- **Status:** Accepted
- **Date:** 2026-08-09
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
