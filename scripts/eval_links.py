"""Human-eval tool over the link corpus (`just eval-links`), a sibling of the
`verify_links` solution-link oracle (spec #244/ADR-0007). Where `verify_links`
answers "does the emitter agree with the front door", this one lays the raw
material out for a person to check the verdict by eye.

It serves a small localhost page as a slideshow — one link at a time, the
puzzle and its solution side by side in iframes (a `broke` case has no solution,
so that pane says so). Approve or Flag records the verdict and advances to the
next slide; a note field feeds the flag. Approving records the stem in a
gitignored log (`.eval-approved.json`), so later runs show only the links not
yet approved (`--all` shows every one). The board is solved once per shown link,
so re-runs get cheaper as the log grows.

    uv run python scripts/eval_links.py        # then open the printed URL
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import threading
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

# The durable flag log: {stem, comment} notes a reviewer jotted while looking.
# Gitignored alongside the approval log; flags accumulate across runs (a flagged
# link returns next run, unlike an approved one).
FLAGGED_PATH = Path(__file__).parent / ".eval-flagged.json"

# Where flags land once a wayfinder map is made from them, stamped with the map's
# issue number so they aren't re-proposed. `/gridfind-flags-to-map` passes this to
# `archive_flags` after filing a map; gitignored alongside the flag log.
FLAGGED_ARCHIVE_PATH = Path(__file__).parent / ".eval-flagged-archive.json"


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


def load_flags(path: Path) -> list[dict[str, str]]:
    """The recorded `{stem, comment}` flags in order, or an empty list when the
    log doesn't exist yet."""
    if not path.exists():
        return []
    return json.loads(path.read_text())["flagged"]


def record_flag(path: Path, stem: str, comment: str) -> None:
    """Append a `{stem, comment}` flag, creating the log if absent. Flags
    accumulate — a second flag on a stem adds an entry, never replaces one."""
    flagged = load_flags(path)
    flagged.append({"stem": stem, "comment": comment})
    path.write_text(json.dumps({"flagged": flagged}, indent=2) + "\n")


def load_archive(path: Path) -> list[dict[str, str | int]]:
    """The archived flags in order — each an `{stem, comment, issue}` entry — or
    an empty list when the archive doesn't exist yet."""
    if not path.exists():
        return []
    return json.loads(path.read_text())["archived"]


def archive_flags(
    flagged_path: Path, archive_path: Path, stems: set[str], issue_number: int
) -> None:
    """Move every flag whose stem is in `stems` out of the flag store and into
    the archive, stamping each moved entry with `issue_number` (the
    `wayfinder:map` it fed). Flags whose stem is not in `stems` stay in the
    store; the archive accumulates across calls."""
    flags = load_flags(flagged_path)
    moved = [{**flag, "issue": issue_number} for flag in flags if flag["stem"] in stems]
    if not moved:
        return  # nothing covered — a true no-op, leaving both files untouched
    kept = [flag for flag in flags if flag["stem"] not in stems]
    archived = load_archive(archive_path)
    archived.extend(moved)
    archive_path.write_text(json.dumps({"archived": archived}, indent=2) + "\n")
    flagged_path.write_text(json.dumps({"flagged": kept}, indent=2) + "\n")


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
  body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 80rem; margin: 1.5rem auto;
         padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.2rem; }}
  .slide {{ display: none; }}
  .slide.active {{ display: block; }}
  .slide h2 {{ font-size: 1.05rem; margin: 0 0 .6rem; }}
  .verdict {{ font-size: .8rem; padding: .1rem .5rem; border-radius: 999px;
             color: #fff; margin-left: .4rem; }}
  .found {{ background: #2e7d32; }}
  .broke {{ background: #b71c1c; }}
  .panes {{ display: flex; gap: 1rem; }}
  .pane {{ flex: 1; min-width: 0; height: 78vh; border: 1px solid #ccc;
          border-radius: 6px; }}
  .pane.empty {{ display: flex; align-items: center; justify-content: center;
                color: #777; background: #fafafa; }}
  @media (max-width: 60rem) {{ .panes {{ flex-direction: column; }}
                              .pane {{ height: 60vh; }} }}
  button {{ margin-top: .8rem; margin-right: .5rem; padding: .35rem 1rem; border: 0;
           border-radius: 6px; background: #1565c0; color: #fff; cursor: pointer;
           font-size: .9rem; }}
  button.flag {{ background: #ef6c00; }}
  button:disabled {{ background: #999; cursor: default; }}
  textarea {{ display: block; width: 100%; margin-top: .6rem; min-height: 2.4rem;
             font: inherit; box-sizing: border-box; }}
</style></head>
<body>
<h1>gridfind link eval &mdash;
  <span id="pos">1</span> of <span id="total">{count}</span>
  <button onclick="finish()">Finish</button></h1>
{body}
<section id="done" hidden>
  <h2>All reviewed &mdash; nice work.</h2>
  <button onclick="finish()">Close</button>
</section>
<script>
const total = {count};
let current = 0;

function slide(i) {{ return document.querySelector('[data-slide="' + i + '"]'); }}

function mount(i) {{
  const s = slide(i);
  if (!s) return;
  s.querySelectorAll("iframe.pane").forEach(f => {{ f.src = f.dataset.src; }});
}}
function unmount(i) {{
  const s = slide(i);
  if (!s) return;
  s.querySelectorAll("iframe.pane").forEach(f => {{ f.removeAttribute("src"); }});
}}

function advance() {{
  const shown = slide(current);
  if (shown) shown.classList.remove("active");
  unmount(current);
  current++;
  if (current >= total) {{ document.getElementById("done").hidden = false; return; }}
  document.getElementById("pos").textContent = current + 1;
  slide(current).classList.add("active");
  mount(current);
}}

async function finish() {{
  await fetch("/finish", {{ method: "POST" }});
  document.body.innerHTML = "<h1>eval closed &mdash; you can close this tab</h1>";
}}
async function approve(btn, stem) {{
  btn.disabled = true;
  const r = await fetch("/approve", {{ method: "POST", body: stem }});
  if (r.ok) {{ advance(); }} else {{ btn.disabled = false; btn.textContent = "retry"; }}
}}
async function flag(btn, stem) {{
  const note = document.getElementById("note-" + stem);
  btn.disabled = true;
  const r = await fetch("/flag", {{
    method: "POST", body: JSON.stringify({{ stem: stem, comment: note.value }})
  }});
  if (r.ok) {{ advance(); }} else {{ btn.disabled = false; btn.textContent = "retry"; }}
}}

if (total === 0) {{
  document.getElementById("pos").textContent = "0";  // "0 of 0", not "1 of 0"
  document.getElementById("done").hidden = false;
}} else mount(0);
</script>
</body></html>
"""


def _pane(view: LinkView) -> str:
    """The right pane of a slide: the solution in an iframe for a `found` case,
    or a labelled empty pane when there is no solution to show."""
    if view.solution_link is None:
        return '<div class="pane empty">no solution — broke case</div>'
    answer = html.escape(view.solution_link, quote=True)
    return f'<iframe class="pane" data-src="{answer}"></iframe>'


def _slide(index: int, stem: str, view: LinkView) -> str:
    """One link as a slide: its stem and verdict, the puzzle and solution side
    by side as lazily-mounted iframes (the puzzle link rides in `data-src` so a
    hidden slide never boots the app), a note field, and Approve/Flag controls.
    Only the first slide (`index == 0`) is active; the rest wait their turn."""
    safe = html.escape(stem, quote=True)
    js_stem = html.escape(json.dumps(stem), quote=True)
    puzzle = html.escape(view.puzzle_link, quote=True)
    active = " active" if index == 0 else ""
    return (
        f'<section class="slide{active}" data-slide="{index}">'
        f'<h2>{safe}<span class="verdict {view.kind}">{view.kind}</span></h2>'
        f'<div class="panes">'
        f'<iframe class="pane" data-src="{puzzle}"></iframe>'
        f"{_pane(view)}"
        f"</div>"
        f'<textarea id="note-{safe}" placeholder="note about this link"></textarea>'
        f'<button onclick="approve(this, {js_stem})">Approve</button>'
        f'<button class="flag" onclick="flag(this, {js_stem})">Flag</button>'
        f"</section>"
    )


def render_page(cards: Sequence[tuple[str, LinkView]]) -> str:
    """The full eval page: one slide per (stem, view), shown one at a time.
    Acting on a slide advances to the next; when none are left, the end-state
    takes over. An empty corpus renders straight to that end-state."""
    body = "\n".join(_slide(i, stem, view) for i, (stem, view) in enumerate(cards))
    return _PAGE.format(count=len(cards), body=body)


class _ApprovalHandler(BaseHTTPRequestHandler):
    """Serves the approval page and records approvals and flags — thin wiring
    over `render_page`, `record_approval`, and `record_flag`; class attributes
    carry the run's state. `GET /` returns the page; `POST /approve` with a
    stem body records it; `POST /flag` with a `{stem, comment}` body appends a
    flag; `POST /finish` ends the run. Approve and flag reject a stem that names
    no real link; `/flag` also rejects an empty comment."""

    page: str = ""
    known: frozenset[str] = frozenset()
    approvals: Path = APPROVED_PATH
    flags: Path = FLAGGED_PATH

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.page.encode())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        if self.path == "/approve":
            self._approve(body.strip())
        elif self.path == "/flag":
            self._flag(body)
        elif self.path == "/finish":
            self._finish()
        else:
            self._reject()

    def _approve(self, stem: str) -> None:
        if stem not in self.known:
            self._reject()
            return
        record_approval(self.approvals, stem)
        self._ok()

    def _flag(self, body: str) -> None:
        payload = json.loads(body)
        stem = payload["stem"]
        comment = payload["comment"].strip()
        if stem not in self.known or not comment:
            self._reject()
            return
        record_flag(self.flags, stem, comment)
        self._ok()

    def _finish(self) -> None:
        # Answer first, then stop the server from a side thread — shutdown()
        # deadlocks if called on the serve_forever thread that runs this handler.
        self._ok()
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _ok(self) -> None:
        self.send_response(200)
        self.end_headers()

    def _reject(self) -> None:
        self.send_response(400)
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
    _ApprovalHandler.flags = FLAGGED_PATH

    url = f"http://127.0.0.1:{args.port}/"
    server = HTTPServer(("127.0.0.1", args.port), _ApprovalHandler)
    print(f"eval page: {url}  ({len(cards)} to check) — Finish button or Ctrl+C")
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
