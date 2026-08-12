"""Human-eval tool over the link corpus (`just eval-links`), a sibling of the
`verify_links` solution-link oracle (spec #244/ADR-0007). Where `verify_links`
answers "does the emitter agree with the front door", this one lays the raw
material out for a person to check the verdict by eye.

It serves a small localhost page: one card per link with the puzzle link (open
it to see the clues), the solution link (a `found` case's witness filled back
in — open it to see the answer), and an Approve button. Approving records the
stem in a gitignored log (`.eval-approved.json`), so later runs show only the
links not yet approved (`--all` shows every one). The board is solved once per
shown link, so re-runs get cheaper as the log grows.

    uv run python scripts/eval_links.py        # then open the printed URL
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import webbrowser
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import NamedTuple

from verify_links import LINKS_DIR, decode_flags, emit_solution_link

from gridfind.sudokumaker import decode_link
from gridfind.verdict import verdict

# The durable approval log: link stems a person has eyeballed and accepted.
# Gitignored — a personal verification record, not a repo fact.
APPROVED_PATH = Path(__file__).parent / ".eval-approved.json"


def load_approved(path: Path) -> set[str]:
    """The set of link stems recorded as approved, or an empty set when the
    log doesn't exist yet."""
    if not path.exists():
        return set()
    data = json.loads(path.read_text())
    return set(data["approved"])


def record_approval(path: Path, stem: str) -> None:
    """Add `stem` to the approval log, creating it if absent. Idempotent — an
    already-approved stem stays a single entry."""
    approved = load_approved(path)
    approved.add(stem)
    path.write_text(json.dumps({"approved": sorted(approved)}, indent=2) + "\n")


class LinkView(NamedTuple):
    """One case file's argv reduced to what a person needs to verify the
    verdict by eye. `witness_grid` and `solution_link` are set only for a
    `found` case; a `broke`/`unknown` case carries the puzzle link alone."""

    kind: str
    puzzle_link: str
    witness_grid: str | None
    solution_link: str | None


def pending_stems(
    stems: Sequence[str], approved: set[str], *, show_all: bool
) -> list[str]:
    """The link stems to render, in their given order: every stem when
    `show_all`, else only those not yet approved."""
    return [stem for stem in stems if show_all or stem not in approved]


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


_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>gridfind link eval</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 46rem; margin: 2rem auto;
         padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.3rem; }}
  .card {{ border: 1px solid #ccc; border-radius: 8px; padding: 1rem 1.2rem;
          margin: 1rem 0; }}
  .card h2 {{ font-size: 1.05rem; margin: 0 0 .6rem; }}
  .verdict {{ font-size: .8rem; padding: .1rem .5rem; border-radius: 999px;
             color: #fff; margin-left: .4rem; }}
  .found {{ background: #2e7d32; }}
  .broke {{ background: #b71c1c; }}
  a {{ display: inline-block; margin-right: 1rem; }}
  button {{ margin-top: .8rem; padding: .35rem 1rem; border: 0; border-radius: 6px;
           background: #1565c0; color: #fff; cursor: pointer; font-size: .9rem; }}
  button:disabled {{ background: #999; cursor: default; }}
</style></head>
<body>
<h1>gridfind link eval &mdash; <span id="count">{count}</span> to check</h1>
{body}
<script>
async function approve(btn, stem) {{
  btn.disabled = true;
  const r = await fetch("/approve", {{ method: "POST", body: stem }});
  if (r.ok) {{
    document.getElementById("card-" + stem).remove();
    document.getElementById("count").textContent =
      document.querySelectorAll(".card").length;
  }} else {{ btn.disabled = false; btn.textContent = "retry"; }}
}}
</script>
</body></html>
"""


def _card(stem: str, view: LinkView) -> str:
    """One link's card: its stem and verdict, the puzzle link, the solution
    link (found cases only), and an Approve button carrying the stem."""
    puzzle = html.escape(view.puzzle_link, quote=True)
    links = [f'<a href="{puzzle}" target="_blank" rel="noopener">Puzzle</a>']
    if view.solution_link is not None:
        answer = html.escape(view.solution_link, quote=True)
        links.append(f'<a href="{answer}" target="_blank" rel="noopener">Solution</a>')
    safe = html.escape(stem, quote=True)
    return (
        f'<article class="card" id="card-{safe}">'
        f'<h2>{safe}<span class="verdict {view.kind}">{view.kind}</span></h2>'
        f"{''.join(links)}<br>"
        f'<button onclick="approve(this, {json.dumps(stem)})">Approve</button>'
        f"</article>"
    )


def render_page(cards: Sequence[tuple[str, LinkView]]) -> str:
    """The full approval page: one card per (stem, view), or a done message
    when nothing is pending."""
    body = "\n".join(_card(stem, view) for stem, view in cards)
    return _PAGE.format(count=len(cards), body=body or "<p>Nothing to check.</p>")


class _ApprovalHandler(BaseHTTPRequestHandler):
    """Serves the approval page and records approvals — thin wiring over
    `render_page` and `record_approval`; class attributes carry the run's
    state. `GET /` returns the page; `POST /approve` with a stem body records
    it, rejecting any stem that names no real link."""

    page: str = ""
    known: frozenset[str] = frozenset()
    approvals: Path = APPROVED_PATH

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.page.encode())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        stem = self.rfile.read(length).decode().strip()
        if self.path != "/approve" or stem not in self.known:
            self.send_response(400)
            self.end_headers()
            return
        record_approval(self.approvals, stem)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Silence the default per-request stderr logging.
        pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_links",
        description="Serve a browser page to eyeball each link's witness and "
        "approve it; approvals persist so later runs show only what's left.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="show every link, including already-approved ones (default: "
        "only non-approved)",
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="localhost port (default: 8765)"
    )
    args = parser.parse_args(argv)

    approved = load_approved(APPROVED_PATH)
    by_stem = {path.stem: path for path in sorted(LINKS_DIR.rglob("*.txt"))}
    shown = pending_stems(list(by_stem), approved, show_all=args.all)
    cards = [(stem, eval_link(by_stem[stem].read_text().split())) for stem in shown]

    _ApprovalHandler.page = render_page(cards)
    _ApprovalHandler.known = frozenset(by_stem)
    _ApprovalHandler.approvals = APPROVED_PATH

    url = f"http://127.0.0.1:{args.port}/"
    server = HTTPServer(("127.0.0.1", args.port), _ApprovalHandler)
    print(f"eval page: {url}  ({len(cards)} to check) — Ctrl+C to stop")
    # headless / WSL can't open a browser — the printed URL is the fallback.
    with contextlib.suppress(webbrowser.Error):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
