"""Regenerate `docs/accepted-link-setter-guide.html` from
`gridfind.setter_guide.render()` (ADR-0013). Wired to `just setter-guide`;
`setter_guide_test.py`'s freshness test is what `just check` relies on to
catch a page that drifted from this script's last run.

    uv run python scripts/generate_setter_guide.py
"""

from __future__ import annotations

import pathlib

from gridfind import setter_guide

_COMMITTED_PAGE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "docs"
    / "accepted-link-setter-guide.html"
)


def main() -> None:
    _COMMITTED_PAGE.write_text(setter_guide.render())


if __name__ == "__main__":
    main()
