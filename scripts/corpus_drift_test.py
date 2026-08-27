"""The one drift guard for every synthesized corpus link: each committed
`links/<name>.txt` must be byte-identical to a fresh call of its
synthesizer's `CORPUS[name]`. Auto-discovers every `synthesize_*_links.py`
module in this directory, so a new synthesizer inherits the guard for free —
nothing to add per script.

A stem in `HUMAN_AUTHORED` is captured by hand on SudokuMaker.com rather
than built by a synthesizer: it carries no `CORPUS` entry to diff against,
by design, not by omission. Naming it here — instead of
leaving it to pass by silently matching nothing in `_discover_cases` — means
a future synthesizer claiming the same stem collides with a recorded
decision rather than an invisible gap.
"""

from __future__ import annotations

import importlib

import pytest
from _corpus import LINKS_DIR, discover_modules, synthesizer_by_stem

# By-stem record of every corpus link captured by hand rather than
# synthesized, each with the issue that captured it.
# `test_human_authored_stem_carries_no_synthesizer` fails loud if a later
# synthesizer claims one of these names — the exemption from the drift check
# would then be silently wrong instead of an intentional record.
HUMAN_AUTHORED: dict[str, str] = {
    "found-quadruple-4x4-human": (
        "issue #730: real SudokuMaker quadruple (303) link that grounded "
        "corner_to_quad's lattice (issue #731)"
    ),
}


def _discover_cases() -> list[tuple[str, str]]:
    """Every `(module_stem, corpus_name)` pair across every
    `synthesize_*_links.py` module `discover_modules` finds."""
    return [
        (module.__name__, name)
        for module in discover_modules()
        for name in sorted(module.CORPUS)
    ]


_CASES = _discover_cases()


@pytest.mark.parametrize(
    ("module_stem", "name"),
    _CASES,
    ids=[f"{module_stem}:{name}" for module_stem, name in _CASES],
)
def test_committed_corpus_file_matches_its_synthesizer(
    module_stem: str, name: str
) -> None:
    """The committed corpus is built in code, never hand-authored: each file
    is exactly its synthesizer's output. A hand-edit (or a stale regenerate)
    turns this red."""
    module = importlib.import_module(module_stem)
    path = LINKS_DIR / f"{name}.txt"
    assert path.read_text() == module.CORPUS[name]() + "\n"


@pytest.mark.parametrize("stem", sorted(HUMAN_AUTHORED), ids=sorted(HUMAN_AUTHORED))
def test_human_authored_stem_carries_no_synthesizer(stem: str) -> None:
    """A named human-authored stem is excluded from the byte-drift check
    above on purpose: it must exist under `links/` and must not collide with
    a `CORPUS` entry any synthesizer claims — the moment one does, the
    exclusion is stale and this stem belongs in `_discover_cases` instead."""
    assert (LINKS_DIR / f"{stem}.txt").exists()
    assert stem not in synthesizer_by_stem()
