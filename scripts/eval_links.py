"""Human-eval view over the link corpus (`just eval-links`), a sibling of the
`verify_links` solution-link oracle (spec #244/ADR-0007). Where `verify_links`
answers "does the emitter agree with the front door", this one lays the raw
material out for a person to check the verdict by eye: over every case file
under `links/`, print the puzzle link (open it to see the clues), and for a
`found` case the rendered witness grid plus the filled-in solution link (open
it to see the answer in the app). A `broke` case prints the verdict and the
puzzle link — there is no witness to show.

    uv run python scripts/eval_links.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from verify_links import LINKS_DIR, decode_flags, emit_solution_link

from gridfind.sudokumaker import decode_link
from gridfind.verdict import verdict


class LinkView(NamedTuple):
    """One case file's argv reduced to what a person needs to verify the
    verdict by eye. `witness_grid` and `solution_link` are set only for a
    `found` case; a `broke`/`unknown` case carries the puzzle link alone."""

    kind: str
    puzzle_link: str
    witness_grid: str | None
    solution_link: str | None


def eval_link(argv: Sequence[str]) -> LinkView:
    """One case file's argv (flags then the link) reduced to a `LinkView`. A
    `found` case renders its witness grid and re-emits that same witness as a
    solution link (via `emit_solution_link`, the one source of the fill+encode
    step); anything else carries the puzzle link alone."""
    flags = decode_flags(argv)
    link = argv[-1]
    puzzle, state = decode_link(
        link,
        schrodinger=flags.schrodinger,
        reading=flags.reading,
        doubler=flags.doubler,
    )
    result = verdict(puzzle, state)
    if result.kind != "found" or result.witness is None:
        return LinkView(result.kind, link, witness_grid=None, solution_link=None)
    return LinkView(
        result.kind,
        link,
        witness_grid=result.witness.render(),
        solution_link=emit_solution_link(link, result.witness, puzzle.board.size),
    )


def _format(name: str, view: LinkView) -> str:
    lines = [
        "=" * 70,
        f"{name}  →  {view.kind}",
        f"  puzzle:   {view.puzzle_link}",
    ]
    if view.witness_grid is not None:
        lines.append("  witness:")
        lines += [f"    {row}" for row in view.witness_grid.splitlines()]
    if view.solution_link is not None:
        lines.append(f"  solution: {view.solution_link}")
    return "\n".join(lines)


def main() -> int:
    for path in sorted(LINKS_DIR.rglob("*.txt")):
        argv = path.read_text().split()
        print(_format(path.stem, eval_link(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
