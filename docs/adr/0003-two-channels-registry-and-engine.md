# ADR-0003: two channels — the registry carries derived facts, the engine carries setter input

- **Status:** Superseded by [ADR-0004](0004-binding-not-provenance.md) — the
  revisit condition below fired (issue #109), and the fix replaced this ADR's
  provenance test with a binding test rather than adding a read handle.
- **Date:** 2026-08-08
- **Decides:** whether every fact a layer reads must arrive through the structure
  registry (raised while speccing #78, which puts the setter's `board` on the
  `Engine`).

## Context

Decision 9 says the structure registry is *the only* channel through which
layers talk. That was true when every shared fact was something one layer
derived and another consumed — a cell's content, a window's concatenation.

It stopped being the whole truth when `Puzzle` arrived. The engine already
carries `constraints`: the setter's typed statements, handed to the engine by
`build_engine` and read by the layer that handles each type. #78 adds `board`
the same way, so `layers/board.py` can size the grid from the setter's `size`
instead of a hard-coded 9.

Publishing setter input as structures was the alternative, and it fails on its
own terms. `verdict` and `_base.emit_distinct_count` need the digit domain, and
neither is a layer — neither holds a registry handle. A fact every consumer
needs, layer or not, does not belong in a channel only layers can read.

The two channels are not a leak; they are a real distinction the vocabulary
had not yet named. **Who produced the fact** is the line:

- Setter input flowing *in* — `constraints`, and `board` after #78 — rides the
  engine as a carried field. It exists before any layer runs.
- Facts one layer *derives* for another to consume — `grid`, cell content —
  ride the structure registry. They exist only once a layer has built them.

## Decision

1. **Two channels, split by provenance.** The structure registry carries
   layer-derived facts. The engine's carried fields carry setter input. Neither
   channel absorbs the other.

2. **Decision 9 is rescoped, not reversed.** The registry remains the only
   channel through which layers talk *to each other*. It was never the channel
   through which setter input reaches them.

3. **A new carried field must earn it.** Add one only for a fact that (a) comes
   from the setter rather than from a layer, and (b) has at least one consumer
   that is not a layer. Anything a layer derives goes in the registry.

## When to revisit

Revisit if a non-layer consumer of a *derived* fact appears — that would mean
the registry's read side, not its write side, is the thing that is too narrow,
and the fix would be a registry read handle rather than a third channel.
