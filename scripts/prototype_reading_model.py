"""PROTOTYPE — throwaway. Answers #593: the S-cell / modifier reading model.

Not production. Run: uv run python <this file>. It prints the model and
asserts the worked examples, so a broken corner fails loudly.

It makes four things concrete to react to:
  1. The combine word rides the cosmetic-cage NAME (SM is a blind text
     transport; gridfind decodes). Fixed menu, setter-chosen per puzzle.
  2. The two reading knobs -> four corners -> the seam methods that exist.
     The fourth corner is refused.
  3. A constraint's reading is intrinsic by type; the cage alone carries a
     declared `distinct-over: digit|value` param.
  4. The Q5 names, in use.
"""

from __future__ import annotations

# --- 1. Combine mode: a word on the cosmetic-cage name -----------------------
# SM stores an opaque name string. gridfind's convention: the name marks the
# S-cell layer, and an optional combine word appends (like "Constant 3").
# Fixed menu, setter picks per puzzle. Absent word -> the puzzle's default.

COMBINE_MENU = ("sum", "concat")  # the fixed set; concat still unbuilt (#535)
DEFAULT_COMBINE = "sum"


def parse_scell_cage_name(name: str) -> tuple[str, str] | None:
    """A cosmetic-cage name -> (layer, combine_mode), or None if not ours.

    "S-cell"        -> ("s-cell", "sum")     # default word omitted
    "S-cell concat" -> ("s-cell", "concat")
    "Doubler"       -> None                  # a different layer, no combine
    """
    head, _, tail = name.partition(" ")
    if head != "S-cell":
        return None
    if tail == "":
        return ("s-cell", DEFAULT_COMBINE)
    if tail in COMBINE_MENU:
        return ("s-cell", tail)
    raise ValueError(f"unknown combine word {tail!r}; menu is {COMBINE_MENU}")


# --- 2. The two knobs, four corners, seam methods ----------------------------
# Knob A "modifier reading": underlying | mapped
# Knob B "S-cell reading":   per-digit  | combined
# Corner -> the engine seam method a reader calls (all but one already exist).

SEAM = {
    ("underlying", "combined"): "base_value",   # s_value, or the digit
    ("mapped", "combined"): "value_expr",       # base_value + modifier map
    ("underlying", "per-digit"): "contents",    # raw slots (d0 for width-1)
    ("mapped", "per-digit"): "REFUSE",          # the undefined corner
}


def seam_method(modifier_reading: str, scell_reading: str) -> str:
    method = SEAM[(modifier_reading, scell_reading)]
    if method == "REFUSE":
        raise ValueError(
            "undefined corner: no per-digit modifier map exists "
            "(a doubled S-cell is 2*combined, not per-digit)"
        )
    return method


# --- 3. A constraint's reading: intrinsic by type, cage alone declares -------
# Every constraint reads `value` (value mode) unless its meaning fixes digit.
# The cage is the one two-valued case: `distinct-over: digit|value`.

INTRINSIC_READING = {
    "thermo": "value",       # always mapped value
    "group-sum": "value",    # folds modifier + combined
    "no-repeats-digit": "digit",  # the classic killer exception
}


def cage_reading(distinct_over: str) -> str:
    """The cage's declared param picks a coherent corner, not two knobs."""
    return {"digit": "per-digit slots", "value": "combined mapped value"}[distinct_over]


# --- worked examples (the runnable check) ------------------------------------
def demo() -> None:
    # 1. combine word decodes off the name; SM never sees S-cell-ness
    assert parse_scell_cage_name("S-cell") == ("s-cell", "sum")
    assert parse_scell_cage_name("S-cell concat") == ("s-cell", "concat")
    assert parse_scell_cage_name("Doubler") is None

    # an S-cell holding {2,3}: value depends on the setter's combine word
    def combined(digits: tuple[int, ...], mode: str) -> int:
        if mode == "sum":
            return sum(digits)
        return int("".join(str(d) for d in digits))  # concat

    assert combined((2, 3), "sum") == 5
    assert combined((2, 3), "concat") == 23

    # 2. three corners resolve to a real seam method; the fourth refuses
    assert seam_method("underlying", "combined") == "base_value"
    assert seam_method("mapped", "combined") == "value_expr"
    assert seam_method("underlying", "per-digit") == "contents"
    try:
        seam_method("mapped", "per-digit")
        raise AssertionError("fourth corner should refuse")
    except ValueError as e:
        assert "undefined corner" in str(e)

    # a per-digit read is combine-mode-independent (Q2 point in favor)
    #   digit-mode cage over {2,3} sees slots 2 and 3 whatever the combine word

    # 3. intrinsic vs declared reading
    assert INTRINSIC_READING["thermo"] == "value"
    assert INTRINSIC_READING["no-repeats-digit"] == "digit"
    assert cage_reading("digit") == "per-digit slots"
    assert cage_reading("value") == "combined mapped value"

    print("MODEL (react to this):\n")
    print("combine menu (fixed, setter picks per puzzle):", COMBINE_MENU)
    print("  carried as a word on the cosmetic-cage name; gridfind decodes, SM blind\n")
    print("four corners  (modifier reading x S-cell reading -> seam method):")
    for (mod, sc), m in SEAM.items():
        print(f"  {mod:<10} + {sc:<9} -> {m}")
    print("\nconstraint reading:")
    print("  intrinsic by type:", INTRINSIC_READING)
    print("  cage declares:     distinct-over: digit|value ->",
          "{digit: per-digit slots, value: combined mapped value}")
    print("\nnames in use: digit/value mode, modifier reading, S-cell reading,",
          "combine mode, undefined corner")
    print("\nall worked examples pass.")


if __name__ == "__main__":
    demo()
