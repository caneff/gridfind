"""Human-eval tool over the link corpus (`just eval-links`), a sibling of the
`verify_links` solution-link oracle (ADR-0007). Where `verify_links`
answers "does the emitter agree with the front door", this one lays the raw
material out for a person to check the verdict by eye.

It serves a small localhost page as a slideshow — one link at a time, the
puzzle and its solution side by side in iframes (a `broke` case has no solution,
so that pane says so). Approve or Flag records the verdict and advances to the
next slide; Back steps to the previous one (its verdict stays logged); a note
field feeds the flag. Approving records the stem in a
gitignored log (`.eval-approved.json`), so later runs show only the links not
yet approved (`--all` shows every one). The board is solved once per shown link,
so re-runs get cheaper as the log grows.

    uv run python scripts/eval_links.py             # every non-approved link
    uv run python scripts/eval_links.py --changed   # only this branch's edits
    uv run python scripts/eval_links.py --all       # every link, approved too

`--changed` is the one to reach for in a worktree: the approval log is
gitignored, so a fresh worktree inherits no approvals and the default run would
re-show the whole corpus. `--changed` instead lists only the fixtures this
branch edited (versus `--base`, default `main`) — committed, staged, unstaged,
or untracked — so you eval exactly what you touched.

Launching this from an automated or background agent session: the server's
process tree lives under that session, so it can be reaped when the launching
task is torn down — the page then stops responding mid-review. Treat that as
expected: relaunch when the page goes dead, or run the server from a shell that
outlives the agent (your own terminal) when you need it to stay up. Either way,
open the printed URL yourself (`wslview <url>` under WSL); the in-process
`webbrowser` auto-open is unreliable.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import inspect
import json
import subprocess
import threading
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import NamedTuple

from _corpus import synthesizer_by_stem
from verify_links import LINKS_DIR, emit_solution_link, oracle_witness

# Shown for a stem no `CORPUS` map claims — a human-authored link predating
# the synthesized corpus, which carries no synthesizer docstring to draw on.
FALLBACK_PROOF = "Legacy hand-authored link — no synthesizer to say what it proves."

# The durable approval log: link stems a person has eyeballed and accepted.
# Gitignored — a personal verification record, not a repo fact.
APPROVED_PATH = Path(__file__).parent / ".eval-approved.json"

# The durable flag log: {stem, comment} notes a reviewer jotted while looking.
# Gitignored alongside the approval log; flags accumulate across runs (a flagged
# link returns next run, unlike an approved one).
FLAGGED_PATH = Path(__file__).parent / ".eval-flagged.json"

# Where flags land once an issue is made from them — a map, a spec, or a
# ticket — stamped with that issue's number so they aren't re-proposed.
# `/gridfind-flags-to-tickets` passes this to `archive_flags` after filing;
# gitignored alongside the flag log.
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


# Called by the `gridfind-flags-to-tickets` skill via `python -c`, not from any
# Python import — static analysis (and a grep for callers) will not find that
# call site. Do not delete this as dead code.
def archive_flags(
    flagged_path: Path, archive_path: Path, stems: set[str], issue_number: int
) -> None:
    """Move every flag whose stem is in `stems` out of the flag store and into
    the archive, stamping each moved entry with `issue_number` (the issue it
    fed). Flags whose stem is not in `stems` stay in the store; the archive
    accumulates across calls."""
    flags = load_flags(flagged_path)
    moved = [{**flag, "issue": issue_number} for flag in flags if flag["stem"] in stems]
    if not moved:
        return
    kept = [flag for flag in flags if flag["stem"] not in stems]
    archived = load_archive(archive_path)
    archived.extend(moved)
    archive_path.write_text(json.dumps({"archived": archived}, indent=2) + "\n")
    flagged_path.write_text(json.dumps({"flagged": kept}, indent=2) + "\n")


class LinkView(NamedTuple):
    """One case file's argv reduced to what a person needs to verify the
    verdict by eye. `witness_grid` and `solution_link` are set only for a
    `found` case; a `broke`/`unknown` case carries the puzzle link alone.
    `proof` is the "what this proves" line — its synthesizer's docstring, or
    `FALLBACK_PROOF` for a legacy stem."""

    kind: str
    puzzle_link: str
    witness_grid: str | None
    solution_link: str | None
    proof: str
    # `kind` is the verdict word (`found`/`broke`/`unknown`), or `malformed` for
    # a malformed link the front door refuses — carrying the puzzle link alone.


def feature_then_kind(stem: str) -> tuple[str, str]:
    """Sort key pairing a feature's cards: `broke-thermo-4x4` and
    `found-thermo-4x4` sort adjacent, broke first."""
    kind, _, feature = stem.partition("-")
    return feature, kind


def pending_stems(
    stems: Sequence[str], approved: set[str], *, show_all: bool
) -> list[str]:
    """The link stems to render, in their given order: every stem when
    `show_all`, else only those not yet approved."""
    return [stem for stem in stems if show_all or stem not in approved]


def _stems_from_git_paths(*outputs: str) -> set[str]:
    """Every `*.txt` link stem named across `git diff`/`git status --porcelain`
    output. Both a bare diff path and a porcelain `XY <path>` (or rename
    `XY <old> -> <new>`) line are scanned by whitespace token, so status
    columns and the rename arrow fall away on their own; a rename's stale old
    stem rides along harmlessly, dropped when the caller intersects the corpus."""
    return {
        Path(token).stem
        for output in outputs
        for line in output.splitlines()
        for token in line.split()
        if token.endswith(".txt")
    }


def changed_link_stems(base: str) -> set[str]:
    """The corpus stems edited versus `base` — the committed diff plus any
    staged, unstaged, or untracked change under `links/`. The `--changed`
    filter reads this so a worktree evals only its own edited examples, without
    depending on the gitignored approval log (which a fresh worktree never
    inherits)."""

    def git(*args: str) -> str:
        done = subprocess.run(  # noqa: S603 — fixed argv, no shell, trusted input
            ["git", "-C", str(LINKS_DIR), *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout

    committed = git("diff", "--name-only", f"{base}...HEAD", "--", str(LINKS_DIR))
    working = git("status", "--porcelain", "--", str(LINKS_DIR))
    return _stems_from_git_paths(committed, working)


def proof_for(stem: str, synthesizers: Mapping[str, Callable[[], str]]) -> str:
    """The "what this proves" line for `stem`: its synthesizer's docstring,
    reached by looking `stem` up in the `stem -> synthesizer` map
    `_corpus.synthesizer_by_stem` builds from every module's `CORPUS`, or
    `FALLBACK_PROOF` when no synthesizer built this stem (a legacy,
    human-authored link) or its function carries no docstring."""
    fn = synthesizers.get(stem)
    if fn is None or fn.__doc__ is None:
        return FALLBACK_PROOF
    return inspect.cleandoc(fn.__doc__)


def view_for(stem: str, argv: Sequence[str], proof: str) -> LinkView:
    """The view for one case file, keyed off its expected-outcome prefix. A
    `malformed-*` fixture is a malformed link the front door refuses (exit 2),
    so it carries no verdict to eyeball and is presented without decoding;
    everything else routes through `eval_link`."""
    if stem.partition("-")[0] == "malformed":
        return LinkView(
            "malformed", argv[-1], witness_grid=None, solution_link=None, proof=proof
        )
    return eval_link(argv, proof)


def eval_link(argv: Sequence[str], proof: str) -> LinkView:
    """One case file's argv (flags then the link) reduced to a `LinkView`. A
    `found` case renders its witness grid and re-emits that same witness as a
    solution link (via `emit_solution_link`, the one source of the fill+encode
    step); anything else carries the puzzle link alone. The puzzle pane shows
    the setter's link verbatim — its marker cages already carry the authentic
    black cosmetic style, so they read as ordinary named cages, never colored,
    because a setter does not color their cages. The review highlight is the
    witness's job: the solution link colors discovered markers red
    (`colorize_marker_cages`, inside `emit_solution_link`), so red flags what
    gridfind found, not what the setter drew."""
    link = argv[-1]
    kind, witness, size = oracle_witness(link)
    if witness is None:
        return LinkView(kind, link, witness_grid=None, solution_link=None, proof=proof)
    return LinkView(
        kind,
        link,
        witness_grid=witness.render(),
        solution_link=emit_solution_link(link, witness, size),
        proof=proof,
    )


# pragma: no mutate start — render+server (presentation): HTML/CSS/JS template,
# the slide/page renderers, and the HTTP handler + main() that serves them. The
# data layer above this marker (approval/flag logs, stem selection, decode/verdict
# wiring) stays in mutation scope.
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
  .proof {{ color: #555; font-size: .9rem; margin: -.3rem 0 .8rem; }}
  .verdict {{ font-size: .8rem; padding: .1rem .5rem; border-radius: 999px;
             color: #fff; margin-left: .4rem; }}
  .found {{ background: #2e7d32; }}
  .broke {{ background: #b71c1c; }}
  .malformed {{ background: #b26a00; }}
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
  <button onclick="back()">Back</button>
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

function go(i) {{
  const shown = slide(current);
  if (shown) shown.classList.remove("active");
  unmount(current);
  current = i;
  document.getElementById("done").hidden = current < total;
  if (current >= total) return;
  document.getElementById("pos").textContent = current + 1;
  const next = slide(current);
  next.classList.add("active");
  // Revisited via Back: its verdict is already logged, let it be re-recorded.
  next.querySelectorAll("button").forEach(b => {{ b.disabled = false; }});
  mount(current);
}}
function advance() {{ go(current + 1); }}
function back() {{ if (current > 0) go(current - 1); }}

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
        reason = "malformed link" if view.kind == "malformed" else f"{view.kind} case"
        return f'<div class="pane empty">no solution — {reason}</div>'
    answer = html.escape(view.solution_link, quote=True)
    return f'<iframe class="pane" allow="clipboard-write" data-src="{answer}"></iframe>'


def _slide(index: int, stem: str, view: LinkView) -> str:
    """One link as a slide: its stem and verdict, the puzzle and solution side
    by side as lazily-mounted iframes (the puzzle link rides in `data-src` so a
    hidden slide never boots the app), a note field, and Approve/Flag controls.
    Only the first slide (`index == 0`) is active; the rest wait their turn."""
    safe = html.escape(stem, quote=True)
    js_stem = html.escape(json.dumps(stem), quote=True)
    puzzle = html.escape(view.puzzle_link, quote=True)
    proof = html.escape(view.proof, quote=True)
    active = " active" if index == 0 else ""
    return (
        f'<section class="slide{active}" data-slide="{index}">'
        f'<h2>{safe}<span class="verdict {view.kind}">{view.kind}</span></h2>'
        f'<p class="proof">{proof}</p>'
        f'<div class="panes">'
        f'<iframe class="pane" allow="clipboard-write" data-src="{puzzle}"></iframe>'
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
        "--changed",
        action="store_true",
        help="show only the links edited versus --base (committed, staged, "
        "unstaged, or untracked) — the way to eval just this branch's fixtures "
        "in a worktree, where the approval log starts empty",
    )
    parser.add_argument(
        "--base",
        default="main",
        help="the ref --changed diffs against (default: main)",
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="localhost port (default: 8765)"
    )
    args = parser.parse_args(argv)

    approved = load_approved(APPROVED_PATH)
    # Feature first, verdict second: each feature's broke/found pair sits
    # together instead of every broke card before every found card.
    paths = sorted(LINKS_DIR.rglob("*.txt"), key=lambda p: feature_then_kind(p.stem))
    by_stem = {path.stem: path for path in paths}
    if args.changed:
        # An explicit edit set overrides the approval log: you asked for your
        # own changes, so show them whether or not they were approved before.
        edited = changed_link_stems(args.base)
        shown = [stem for stem in by_stem if stem in edited]
    else:
        shown = pending_stems(list(by_stem), approved, show_all=args.all)
    synthesizers = synthesizer_by_stem()
    cards = [
        (
            stem,
            view_for(
                stem,
                by_stem[stem].read_text().split(),
                proof_for(stem, synthesizers),
            ),
        )
        for stem in shown
    ]

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
# pragma: no mutate end
