"""Move a SudokuMaker link between its link form and an editable JSON file.

A dev tool, and the editing half of the pair `inspect_link.py` opens: that one
reads a link and reports, this one lets you change it. Decode to JSON, edit the
document in your editor, encode it back.

    uv run python scripts/link_file.py decode '<link>' board.json
    uv run python scripts/link_file.py encode board.json link.txt

Either path may be `-` for stdin / stdout. `decode` also accepts a file holding
a link instead of the link itself, since that is how the links in
sudokumaker-custom-constraints are stored.

The round trip preserves the *document*, not the link text. A link written by
the app and a link written here can compress to different payloads and still
open the same puzzle — across gridfind's corpus, 114 of 125 links re-encode
byte-identical and the other 11 differ only in the compressed bytes. So compare
documents, never link strings, when checking that an edit changed only what you
meant to change.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from gridfind.sudokumaker import document_to_link, link_to_document


def read_link(source: str) -> str:
    """The link named by `source` — the link itself, or a file holding one.

    A link is one long token with no whitespace, so a `source` that names an
    existing file is read; anything else is already the link. The file's last
    whitespace-separated token wins, which tolerates a trailing newline and a
    file that comments above the link.
    """
    path = Path(source)
    if path.is_file():
        return path.read_text().split()[-1]
    return source.strip()


def decode(source: str, destination: str, stdout: TextIO) -> None:
    """Write the document behind `source`'s link to `destination` as indented
    JSON — the whole document, so `encode` can put back every field the app
    renders."""
    text = json.dumps(link_to_document(read_link(source)), indent=2) + "\n"
    _write(destination, text, stdout)


def encode(source: str, destination: str, stdout: TextIO) -> None:
    """Write the link for the JSON document at `source` to `destination`.

    Refuses to write a link that does not decode back to the document it came
    from: a link that has quietly lost a field opens as a different puzzle, and
    finding that out from a solver is far too late. The check guards the
    compression boundary, so it holds whatever `document` contains.
    """
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    document: Any = json.loads(
        sys.stdin.read() if source == "-" else Path(source).read_text()
    )
    link = document_to_link(document)
    if link_to_document(link) != document:
        raise ValueError("link does not round-trip; refusing to write it")
    _write(destination, link + "\n", stdout)


def _write(destination: str, text: str, stdout: TextIO) -> None:
    """`text` to `destination`, or to `stdout` when it is `-`."""
    if destination == "-":
        stdout.write(text)
    else:
        Path(destination).write_text(text)


COMMANDS = {"decode": decode, "encode": encode}


def main(argv: Sequence[str], stdout: TextIO, stderr: TextIO = sys.stderr) -> int:
    if len(argv) != 3 or argv[0] not in COMMANDS:
        print(
            f"usage: link_file.py {'|'.join(COMMANDS)} <source> <destination>",
            file=stderr,
        )
        return 2
    command, source, destination = argv
    try:
        COMMANDS[command](source, destination, stdout)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], sys.stdout))
