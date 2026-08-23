"""The `line` layer: the shared spine every SudokuMaker line relation
(renban, whisper, palindrome, between, region-sum, sequence, grouped-line,
lockout, double-arrow) rides — one layer kind, shaped like `Thermo`, plus a
per-alias relation table.

`LINE_RELATIONS` is the one growth point: each row is `(reading_mode,
predicate)`, keyed by the clue's own `params["relation"]` alias. `emit` owns
the three family-wide decisions once — the path read, the reading-mode seam
selection, and the Schrödinger digit-mode rule — so a new relation costs one
table row and one predicate, never a new layer or decode path. A
`"value"`-mode relation reads each path cell through `engine.value_expr`
(ADR-0009, precedence `modifier_value -> s_value -> digit`), so a doubler or
a Schrödinger cell on the line counts as its folded value, the same seam
`thermo` and the pair-relation family already read. A `"digit"`-mode relation
reads each path cell through `engine.real_digit_slots` (ADR-0019 dec 6)
instead — a list of `(digit, guard)` pairs per cell, `d0`'s guard always
`None`, `d1`'s the cell's `is_s` — the same gated seam `clone` reads a
digit-set clue through, so a Schrödinger cell on a set-structured digit
relation (renban) contributes both its digits, never folded to one `s_value`.

Whisper is the value-mode row: for each adjacent path pair, `|value_expr(i) -
value_expr(i+1)| >= params["minDifference"]` — German (5) and Dutch (4) are
this same relation at a different threshold. `minDifference` is read with a
bare subscript, so a clue missing it raises `KeyError` rather than falling
back to an invented default.

Renban is the first digit-mode row, and states nothing beyond the path: every
real digit slot distinct, and the run's spread (`max - min`) one less than
however many real slots the path actually carries — a Schrödinger cell's
extra, gated slot included, so a 2-cell path holding an S-cell can seat a
3-digit run.

Palindrome is the second digit-mode row, and the first **position-structured**
one: every mirror pair `(i, n-1-i)` of the path holds the same real digit, its
odd-length middle cell (read by no pair) left free. Position structure means
each cell must fold to one real digit before the mirror pairing runs, so
unlike renban's set-structured pooling a Schrödinger-widened cell has no
defined fold — `_single_real_digits` raises through `sole` (`engine.py`)
rather than guess one. This is the shared position-structured Schrödinger
raise grouped-line (#682) reuses.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, sole
from gridfind.layers._base import abs_diff_var, emit_over_pairs
from gridfind.puzzle import JsonValue

ReadingMode = str  # "value" or "digit"
ValueSequence = list[cp_model.IntVar]
DigitSlot = tuple[cp_model.IntVar, cp_model.IntVar | None]
DigitSequence = list[list[DigitSlot]]
ValuePredicate = Callable[[Engine, ValueSequence, Mapping[str, JsonValue]], None]
DigitPredicate = Callable[[Engine, DigitSequence, Mapping[str, JsonValue]], None]
LinePredicate = ValuePredicate | DigitPredicate


def _whisper(
    engine: Engine,
    sequence: ValueSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Every adjacent path pair's values differ by at least `minDifference`.
    Mints one fresh aux var `d == |a - b|` per pair via `abs_diff_var`
    (`differs_by`'s shared mint), then pins it to `d >= minimum`."""
    minimum = cast("int", params["minDifference"])

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        d = abs_diff_var(engine, a, b, suffix="gap")
        engine.model.add(d >= minimum)

    emit_over_pairs(engine, list(pairwise(sequence)), rel)


def _renban(
    engine: Engine,
    sequence: DigitSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Every real digit slot on the path distinct, and `max - min` one less
    than the count of real slots — a run of that many consecutive,
    non-repeating digits, owning its own distinctness (no cage/region
    needed).

    Distinctness rides the same sentinel trick `cage`'s `distinct-over:
    "digit"` mode uses (`layers/cage.py`): a non-S-cell's second slot sits on
    its own per-cell sentinel, always above every real digit, so a plain
    `add_all_different` over every raw slot — gated or not — already forbids
    a real repeat, no `only_enforce_if` needed. `min` needs no gating either,
    for the same reason: a sentinel can never be the smallest value present.

    `max` cannot take the same shortcut: a sentinel left in would inflate it.
    Each gated slot instead contributes a fresh var pinned to its own digit
    under its guard, the board's own floor otherwise — a value no real digit
    on the path can fall beneath, so it never wins a max it does not belong
    in. `slot_count` — one per path cell, plus one more per realized
    Schrödinger cell — is the same guard sum, read as a plain linear
    expression rather than reified.
    """
    board = engine.board
    low, high = board.values[0], board.values[-1]
    slots = [slot for cell in sequence for slot in cell]
    digits = [digit for digit, _ in slots]
    engine.model.add_all_different(digits)

    max_terms: list[cp_model.IntVar] = []
    for digit, guard in slots:
        if guard is None:
            max_terms.append(digit)
            continue
        term = engine.model.new_int_var(low, high, f"{digit.name}.renban_span")
        engine.model.add(term == digit).only_enforce_if(guard)
        engine.model.add(term == low).only_enforce_if(guard.negated())
        max_terms.append(term)

    slot_count = len(sequence) + sum(guard for _, guard in slots if guard is not None)
    minimum = engine.model.new_int_var(low, high, f"{digits[0].name}.renban_min")
    maximum = engine.model.new_int_var(low, high, f"{digits[0].name}.renban_max")
    engine.model.add_min_equality(minimum, digits)
    engine.model.add_max_equality(maximum, max_terms)
    engine.model.add(maximum - minimum == slot_count - 1)


def _single_real_digits(sequence: DigitSequence) -> list[cp_model.IntVar]:
    """The position-structured Schrödinger raise: fold each path cell's real
    digit slots to its one real digit via `sole` (`engine.py`) before a
    position- or window-structured relation pairs or windows them. Renban's
    set-structured pooling quantifies over every real slot instead and never
    calls this. A cell Schrödinger-widened to two real slots has no defined
    fold — which slot the relation's rule would mean is not stated anywhere
    — so `sole` raises `GridfindError` loud rather than guess one. Palindrome
    is the first caller; grouped-line (#682) reuses this same fold."""
    return [sole(cell)[0] for cell in sequence]


def _palindrome(
    engine: Engine,
    sequence: DigitSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Every mirror pair `(i, n-1-i)` holds the same real digit; an
    odd-length path's middle cell is read by neither pair and so stays free."""
    digits = _single_real_digits(sequence)
    for i in range(len(digits) // 2):
        engine.model.add(digits[i] == digits[-1 - i])


LINE_RELATIONS: dict[str, tuple[ReadingMode, LinePredicate]] = {
    "whisper": ("value", _whisper),
    "renban": ("digit", _renban),
    "palindrome": ("digit", _palindrome),
}


@dataclass
class Line:
    """One line kind for every relation `LINE_RELATIONS` names, dispatched by
    each clue's own `params["relation"]` — an unrecognized alias raises
    `KeyError` (`build_stack` accepts any `line` constraint; the relation
    table is where an unmodeled alias fails loud)."""

    name: str = "line"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            relation = cast("str", clue.params["relation"])
            reading_mode, predicate = LINE_RELATIONS[relation]
            path = cast("list[str]", clue.params["path"])
            if reading_mode == "value":
                value_sequence = [
                    cast("cp_model.IntVar", engine.value_expr(address))
                    for address in path
                ]
                cast("ValuePredicate", predicate)(engine, value_sequence, clue.params)
            elif reading_mode == "digit":
                digit_sequence = [engine.real_digit_slots(address) for address in path]
                cast("DigitPredicate", predicate)(engine, digit_sequence, clue.params)
            else:
                msg = (
                    f"{relation!r} line relation reads {reading_mode!r} mode, "
                    "not yet built"
                )
                raise NotImplementedError(msg)
