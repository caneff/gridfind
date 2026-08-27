"""Report every synthesized found/broke link where a setter's given sits on
a cell the link's own constraint exists to test.

Rule (spec #723): no given may occupy a cell referenced by any constraint a
synthesized found/broke link exists to test — a line's path, a cage's cells
(and its equality-/rellik-cage and group-sum siblings, the same cells under a
second constraint type), a quad's four cells, a clone group, a pair's two
cells (`pair-difference`/`pair-ratio`, including their kropki-dot decodes),
an indexer cell. Row/column/box uniqueness and the region map are not the
constraint under test, so a given anywhere relative to those is never a hit —
nor is a kropki/XV negative-space pair (`params["negate"]`), the implicit
default rule over every *other* adjacent pair rather than a drawn clue.

    uv run python scripts/audit_givens_on_clue.py

Report mode only (spec #723 dec 3): not wired into `just check` yet — a
future ticket adds that once every real hit below is triaged. `EXEMPTIONS` is
the by-stem record of that triage, one line each; the human decides every
entry from this report, never the agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from _corpus import LINKS_DIR as _LINKS_DIR
from _corpus import iter_side_links

from gridfind.puzzle import Constraint, Puzzle
from gridfind.sudokumaker import link_to_puzzle

# The one params key each clue-carrying constraint type names its cells
# under. Every other type (rows-distinct, cols-distinct, regions-distinct,
# the diagonals, line-count-distinct, doubler/constant, schrodinger,
# offset-adjacency, outside-cells, …) carries no clue cells of its own and is
# never "the constraint under test" (spec #723).
_TESTED_TYPES: dict[str, str] = {
    "line": "path",
    "cage": "cells",
    "equality-cage": "cells",
    "rellik-cage": "cells",
    "group-sum": "cells",
    "quadruple": "cells",
    "clone": "cells",
    "pair-difference": "cells",
    "pair-ratio": "cells",
    "indexing": "cells",
}

# By-stem exemptions, each carrying the human's one-line reason (spec #723
# dec 3). The cosmetic-cage pair (synthesize_scell_links.py): their full grid
# of givens, including the two cells the dropped cage would have named, is
# the point — proving an unnamed/unrecognized-named cosmetic cage contributes
# no rule at all (ADR-0012), not a given happening to dodge one. The
# kropki-negative six: each fixture's verdict turns on an unmarked negative
# pair, not the marked dot the audit flags — the marked dot's givens pin only
# the positive clue. The unmarked pair sits at R3C3/R3C4 on the 4x4 boards and
# at R4C4/R4C5 on the 6x6 doubler board, so the reason names the right pair
# for each grid size.
_KROPKI_NEGATIVE_REASON_4X4 = (
    "verdict rests on the negative rule over the unmarked R3C3/R3C4 pair; "
    "the marked dot's givens pin the positive clue only"
)
_KROPKI_NEGATIVE_REASON_6X6 = (
    "verdict rests on the negative rule over the unmarked R4C4/R4C5 pair; "
    "the marked dot's givens pin the positive clue only"
)
EXEMPTIONS: dict[str, str] = {
    "found-cosmetic-cage-unnamed-4x4": (
        "full-grid-of-givens proves an unnamed cosmetic cage drops (ADR-0012)"
    ),
    "found-cosmetic-cage-unrecognized-4x4": (
        "full-grid-of-givens proves an unrecognized-named cosmetic cage "
        "drops (ADR-0012)"
    ),
    "found-kropki-negative-4x4": _KROPKI_NEGATIVE_REASON_4X4,
    "broke-kropki-negative-4x4": _KROPKI_NEGATIVE_REASON_4X4,
    "found-kropki-negative-doubler-6x6": _KROPKI_NEGATIVE_REASON_6X6,
    "broke-kropki-negative-doubler-6x6": _KROPKI_NEGATIVE_REASON_6X6,
    "found-black-kropki-negative-4x4": _KROPKI_NEGATIVE_REASON_4X4,
    "broke-black-kropki-negative-4x4": _KROPKI_NEGATIVE_REASON_4X4,
}


def constraint_cells(constraint: Constraint) -> list[str] | None:
    """The cells `constraint` names as its own clue, or `None` when its type
    carries no clue cells (outside `_TESTED_TYPES`) or its cells come from a
    negative-space default rather than a drawn clue (`params["negate"]`)."""
    if constraint.params.get("negate"):
        return None
    key = _TESTED_TYPES.get(constraint.type)
    if key is None:
        return None
    return cast("list[str]", constraint.params[key])


def puzzle_hits(puzzle: Puzzle) -> list[str]:
    """Every `type@address` hit in `puzzle`, sorted: a given whose address
    also names a cell in some constraint's own tested-cell list."""
    given_addresses = {given.address for given in puzzle.givens}
    hits = {
        f"{constraint.type}@{address}"
        for constraint in puzzle.constraints
        for address in constraint_cells(constraint) or ()
        if address in given_addresses
    }
    return sorted(hits)


def link_hits(link: str) -> list[str]:
    """`puzzle_hits` over a raw SudokuMaker link, decoded through the one
    `link_to_puzzle` seam every verdict runs through."""
    puzzle, _state = link_to_puzzle(link)
    return puzzle_hits(puzzle)


def build_report(links_dir: Path) -> dict[str, list[str]]:
    """Every found/broke corpus link's hits, stem -> sorted hit list; a stem
    with no hits is omitted. `iter_side_links` (`_corpus.py`) owns the corpus
    walk itself."""
    report: dict[str, list[str]] = {}
    for stem, _side, link in iter_side_links(links_dir):
        hits = link_hits(link)
        if hits:
            report[stem] = hits
    return report


def format_report(report: dict[str, list[str]]) -> str:
    """The flagged list (unexempted hits), then the exempted list with each
    reason, or a clean-bill line when nothing is flagged."""
    flagged = {stem: hits for stem, hits in report.items() if stem not in EXEMPTIONS}
    exempted = {stem: hits for stem, hits in report.items() if stem in EXEMPTIONS}
    body = ["Givens-on-the-clue audit:"]
    if flagged:
        body.append(f"{len(flagged)} flagged link(s):")
        body += [
            f"  - {stem}: {', '.join(hits)}" for stem, hits in sorted(flagged.items())
        ]
    else:
        body.append("No unexempted hits.")
    if exempted:
        body.append("")
        body.append(f"{len(exempted)} exempted link(s):")
        body += [
            f"  - {stem}: {', '.join(hits)}  ({EXEMPTIONS[stem]})"
            for stem, hits in sorted(exempted.items())
        ]
    return "\n".join(body)


def main(links_dir: Path = _LINKS_DIR) -> int:
    report = build_report(links_dir)
    print(format_report(report))
    flagged = [stem for stem in report if stem not in EXEMPTIONS]
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
