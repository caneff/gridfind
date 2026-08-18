"""PROTOTYPE — throwaway. Answers #596: the engine read-seam a layer calls
to honor its declared mode. Shape-only: CP vars/guards are faked with plain
Python so the API and the gating are concrete and assertable without OR-Tools.
Run: uv run python <this file>.

The question: one unified read(mode), or explicit digit/value calls?
This stub argues EXPLICIT, and shows the one new piece the seam needs:
a gated real-digit read for digit mode (raw `contents` leaks the sentinel).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# --- fakes standing in for the CP model ------------------------------------
# A "slot" is a real digit int. is_s is a bool per cell. A singleton's second
# slot holds a SENTINEL (schrodinger's d1 > high) that a predicate must never see.
SENTINEL = 999


@dataclass
class Cell:
    d0: int
    d1: int  # SENTINEL when not widened
    is_s: bool


class Engine:
    """The seam. Value side already exists; the digit side gains ONE method."""

    def __init__(self, cells: dict[str, Cell]) -> None:
        self.cells = cells

    # value mode (exists today) --------------------------------------------
    def value_expr(self, addr: str) -> int:
        c = self.cells[addr]
        combined = c.d0 * 10 + c.d1 if c.is_s else c.d0  # concat, illustrative
        return combined  # a modifier layer would map this; base_value skips the map

    # digit mode (THE new seam) --------------------------------------------
    def real_digit_slots(self, addr: str) -> list[tuple[int, bool | None]]:
        """The is_s-gated real digits (#594): d0 always real (guard None),
        d1 real only when is_s (guard = is_s). The clue applies its own
        predicate/quantifier over these; the sentinel is never handed out
        as a live term. Gating lives HERE, in one home, not in each clue."""
        c = self.cells[addr]
        return [(c.d0, None), (c.d1, c.is_s)]

    # the raw primitive the gated read is built from (kept, sentinel-exposing)
    def contents(self, addr: str) -> list[int]:
        c = self.cells[addr]
        return [c.d0, c.d1]


# --- how a clue APPLIES a predicate over the gated slots -------------------
# A guard of None means "always holds"; a bool guard means "holds only if True".
# This is the .only_enforce_if(is_s) shape, faked.
def holds_for_all(slots: list[tuple[int, bool | None]], pred: Callable[[int], bool]) -> bool:
    return all(pred(v) for v, g in slots if g is None or g)  # sentinel (g False) skipped


def holds_for_any(slots: list[tuple[int, bool | None]], pred: Callable[[int], bool]) -> bool:
    return any(pred(v) for v, g in slots if g is None or g)


def real_set(slots: list[tuple[int, bool | None]]) -> frozenset[int]:
    return frozenset(v for v, g in slots if g is None or g)


# --- the four clue shapes from #594, each declaring its own quantifier -----
def even_odd_all_even(engine: Engine, addr: str) -> bool:  # even/odd -> forall
    return holds_for_all(engine.real_digit_slots(addr), lambda d: d % 2 == 0)


def presence_has(engine: Engine, addr: str, wanted: int) -> bool:  # quad -> exists
    return holds_for_any(engine.real_digit_slots(addr), lambda d: d == wanted)


def clone_match(engine: Engine, a: str, b: str) -> bool:  # clone -> set-equality
    return real_set(engine.real_digit_slots(a)) == real_set(engine.real_digit_slots(b))


def adjacent_share_a_digit(engine: Engine, a: str, b: str) -> bool:  # offset-adj
    return bool(real_set(engine.real_digit_slots(a)) & real_set(engine.real_digit_slots(b)))


# --- worked check ----------------------------------------------------------
def demo() -> None:
    eng = Engine({
        "S": Cell(d0=2, d1=4, is_s=True),    # S-cell {2,4}
        "One": Cell(d0=3, d1=SENTINEL, is_s=False),  # singleton 3
        "SixEight": Cell(d0=6, d1=8, is_s=True),     # S-cell {6,8}
    })

    # 1. THE bug the gated read prevents: a forall predicate must never see
    #    the sentinel. Singleton 3 read all-even -> False (3 odd), NOT crash
    #    or a sentinel test.
    assert even_odd_all_even(eng, "One") is False
    assert even_odd_all_even(eng, "S") is True      # {2,4} both even
    assert even_odd_all_even(eng, "SixEight") is True
    # raw contents WOULD leak the sentinel — proof the gated read matters:
    assert 999 in eng.contents("One")               # sentinel present in raw
    assert 999 not in real_set(eng.real_digit_slots("One"))  # gated hides it

    # 2. exists / presence
    assert presence_has(eng, "S", 4) is True
    assert presence_has(eng, "One", 4) is False

    # 3. set-shaped: clone, adjacency
    assert clone_match(eng, "S", "S") is True
    assert clone_match(eng, "S", "SixEight") is False
    assert adjacent_share_a_digit(eng, "S", "SixEight") is False  # {2,4} vs {6,8}
    assert adjacent_share_a_digit(eng, "S", "One") is False

    # 4. value mode is a different SHAPE — one number, not a slot set. This is
    #    why a unified read(mode) returning a union is awkward; explicit wins.
    assert eng.value_expr("S") == 24
    assert eng.value_expr("One") == 3

    print("SEAM SHAPE (react to this):\n")
    print("value mode:  value_expr(addr) -> one expression        (exists)")
    print("             base_value(addr) -> underlying, no modifier (exists)")
    print("digit mode:  real_digit_slots(addr) -> [(d0, None), (d1, is_s)]  (NEW)")
    print("             -> the is_s-gated real digits; sentinel never a live term")
    print("             -> contents(addr) stays as the raw primitive it's built on\n")
    print("the clue owns the quantifier over the gated slots (per #594):")
    print("  even/odd  -> forall   presence -> exists")
    print("  clone     -> set ==   adjacency -> set & (share)")
    print("  cage-digit-distinct -> add_all_different (sentinel-tolerant, may keep raw contents)\n")
    print("NOT a unified read(mode): value=one expr, digit=gated slot list —")
    print("different shapes, so explicit typed calls beat a union return.\n")
    print("all worked examples pass.")


if __name__ == "__main__":
    demo()
