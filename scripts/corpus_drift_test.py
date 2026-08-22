"""The one drift guard for every synthesized corpus link: each committed
`links/<name>.txt` must be byte-identical to a fresh call of its
synthesizer's `CORPUS[name]`. Auto-discovers every `synthesize_*_links.py`
module in this directory, so a new synthesizer inherits the guard for free —
nothing to add per script.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from _corpus import LINKS_DIR

_SCRIPTS_DIR = Path(__file__).resolve().parent


def _discover_cases() -> list[tuple[str, str]]:
    """Every `(module_stem, corpus_name)` pair across every
    `synthesize_*_links.py` module beside this file."""
    cases: list[tuple[str, str]] = []
    for path in sorted(_SCRIPTS_DIR.glob("synthesize_*_links.py")):
        module = importlib.import_module(path.stem)
        cases.extend((path.stem, name) for name in sorted(module.CORPUS))
    return cases


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
