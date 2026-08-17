"""The document boundary: lz-string decompress a SudokuMaker `?puzzle=` link
to its JSON document (`link_to_document`) and compress one back
(`document_to_link`), the size/domain fields every decode reads off that document
(`board_size`, `digit_domain`, `schrodinger_domain`), the one-pass
type bucketing (`bucket_constraints_by_type`) `decode_link` runs once per
link, and the shared enabled-block walk (`enabled_blocks`) every per-type
decoder in the package indexes into that bucket through.
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Iterator
from typing import Any, cast

from lzstring import LZString

# The default board a link describes when it states no `size`/`width`:
# SudokuMaker omits those headers only on the classic 9x9 (§4b, ADR-0011).
_CLASSIC_SIZE = 9


def link_to_document(link: str) -> dict[str, object]:
    """A SudokuMaker `?puzzle=` link (or a bare payload) decompressed to its
    full `formatVersion 1.5.0` document — `formatVersion` plus its `puzzle`
    block. The exact reverse of `document_to_link`, and `decode_link`'s own
    first step: strip the `?puzzle=` prefix, unquote, lz-string-decompress,
    parse the JSON. `decode_link` keeps only the `puzzle` block; a re-encoder
    needs the whole document to preserve every field the app renders."""
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    document: Any = json.loads(raw)
    return document


def document_to_link(document: dict[str, object]) -> str:
    """A decoded SudokuMaker document (the full `json.loads(raw)` object
    `decode_link` reads — `formatVersion` plus its `puzzle` block) mapped back
    to an openable `sudokumaker.app` URL. The exact reverse of `link_to_document`'s
    payload step: lz-string-compress the document's JSON to an
    encoded URI component, then prepend the `?puzzle=` prefix `decode_link`
    strips. `document` rides through untouched, so its `size`/`type`-bearing
    fields survive verbatim and the link opens as the same puzzle."""
    payload = LZString.compressToEncodedURIComponent(json.dumps(document))
    return f"https://sudokumaker.app/?puzzle={payload}"


def board_size(puzzle_data: dict[str, object]) -> int:
    """The board's size `N` read from the link, most specific first (§4b): a
    `width` (with `height`, else derived from the cell count), else a `size`,
    else the classic default `9` — SudokuMaker omits `size`/`width` only when
    the board is the default 9x9, so an absent header means 9, never an
    inference from the cell count (ADR-0011). The shape must be square
    (`rows == cols`) and its cell count must match (`rows * cols == len(cells)`);
    a non-square link, a size/count mismatch, or a sizeless non-81-cell link
    (a real 4x4/6x6 carries its `size`) is refused with its own reason."""
    cells = puzzle_data.get("cells")
    if not isinstance(cells, list):
        msg = "non-classic link: puzzle carries no cells array"
        raise ValueError(msg)
    count = len(cells)
    if "width" in puzzle_data:
        cols = as_int(puzzle_data["width"], "width")
        height = puzzle_data.get("height")
        rows = as_int(height, "height") if height is not None else count // (cols or 1)
    elif "size" in puzzle_data:
        rows = cols = as_int(puzzle_data["size"], "size")
    else:
        rows = cols = _CLASSIC_SIZE
    if rows != cols:
        msg = f"non-square link: {rows}x{cols} is not a square grid"
        raise ValueError(msg)
    if rows * cols != count:
        msg = f"non-classic link: {count} cells do not match size {rows}"
        raise ValueError(msg)
    return rows


def as_int(value: object, field: str) -> int:
    """A link header field that must be an integer, or a `ValueError` naming it
    (a `bool` is not an `int` here — a `True` width is a malformed link)."""
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"non-classic link: {field} must be an int, got {value!r}"
        raise ValueError(msg)
    return value


def digit_domain(puzzle_data: dict[str, object], size: int) -> range:
    """The board's digit domain (§4b): `minDigit`..`maxDigit` when the link
    carries them, else the implicit `1..N`. `maxDigit` defaults to a full
    `N`-wide span from `minDigit`, and the span is validated against N
    (`maxDigit - minDigit + 1 == N`) — a domain that doesn't fit the board is
    refused. A classic link omits both, so this is `1..9`, unchanged."""
    min_digit = as_int(puzzle_data.get("minDigit", 1), "minDigit")
    max_digit = as_int(puzzle_data.get("maxDigit", min_digit + size - 1), "maxDigit")
    if max_digit - min_digit + 1 != size:
        msg = f"non-classic link: domain {min_digit}..{max_digit} is not {size} digits"
        raise ValueError(msg)
    return range(min_digit, max_digit + 1)


def schrodinger_domain(puzzle_data: dict[str, object], size: int) -> range:
    """The board's digit domain under the classic Schrödinger reading:
    `minDigit` through `minDigit + N`, an `N + 1`-wide span carrying the
    `k = 1` extra digit the classic Schrödinger rule derives, not reads. When
    the link declares no `minDigit`, the extra digit defaults to `0` prepended
    below the base `1…N`, giving the classic `0…N` (ADR-0014); an explicit
    `minDigit` is honored as-is."""
    min_digit = as_int(puzzle_data.get("minDigit", 0), "minDigit")
    return range(min_digit, min_digit + size + 1)


# `puzzle_data["constraints"]` bucketed by wire `type`, in wire order —
# `bucket_constraints_by_type`'s return, and what `enabled_blocks` indexes
# into by type. `Any` in the element type keeps the decoded-JSON boundary,
# as elsewhere in this module.
ConstraintBuckets = dict[int, list[dict[str, Any]]]


def bucket_constraints_by_type(puzzle_data: dict[str, object]) -> ConstraintBuckets:
    """`puzzle_data["constraints"]` grouped by wire `type` in one pass —
    `decode_link` runs this once per link and threads the result to every
    per-type decoder, so each decoder selects its own type's blocks by one
    dict lookup. A non-list `constraints` buckets to nothing; a non-dict block,
    or one whose `type` is not an int — a `bool` is not one, matching `as_int`
    — is dropped (no per-type decoder can ever select it by wire `type`).
    Enabled/disabled filtering stays a per-read concern in `enabled_blocks` —
    a bucket carries a type's disabled blocks too, since
    `warn_on_dropped_constraints` needs to see them."""
    buckets: ConstraintBuckets = {}
    blocks = puzzle_data.get("constraints", [])
    if not isinstance(blocks, list):
        return buckets
    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            continue
        block = cast("dict[str, Any]", raw_block)
        kind = block.get("type")
        if isinstance(kind, int) and not isinstance(kind, bool):
            buckets.setdefault(kind, []).append(block)
    return buckets


def enabled_blocks(buckets: ConstraintBuckets, type_: int) -> Iterator[dict[str, Any]]:
    """Every enabled constraint block of one `type` from the pre-bucketed
    table (`bucket_constraints_by_type`), in wire order — the shared front
    the per-type decoders (XV, kropki, cage) and `_regions_matrix` all iterate
    behind. Folds the one guard every decoder needs beyond the bucket lookup:
    a `disabled` block is skipped (the setter switched it off, so it is not
    part of the puzzle even for a type gridfind decodes)."""
    for block in buckets.get(type_, []):
        if block.get("disabled") is not True:
            yield block
