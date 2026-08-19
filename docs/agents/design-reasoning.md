# Design reasoning

How to argue a design call in gridfind.

- **Argue design calls on merits, never on "no puzzle uses it."** The supported puzzle/link set is small and grows on demand, so "no existing puzzle needs X" is circular — unsupported ≠ unneeded. Justify a scope, deferral, or modeling call by model coherence, code cost, or domain semantics instead. Dropping this crutch has flipped calls: forbidding a doubled S-cell costs an extra constraint; allowing it costs nothing, since `d0` is well-defined for both.
