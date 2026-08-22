# One obvious entrypoint for the gate — agents and CI run `just check`.

# Full gate (what CI runs). Run before calling any task done.
check: lint typecheck test content-width-check link-coverage-check

lint:
    uv run ruff check .
    uv run ruff format --check .

# `Engine.contents`/`Engine.domain` are the one home for reading a cell's
# content width (issue #104, pluralized #140) — a ruff rule can't express
# "this attribute, outside this file", so this is a grep. `*_test.py` is
# exempt: those are whitebox tests of the engine's own `Cell` shape.
content-width-check:
    #!/usr/bin/env bash
    set -euo pipefail
    hits=$(grep -rn '\.content\[' src/gridfind --include='*.py' \
        | grep -v '/engine\.py:' \
        | grep -v '_test\.py:' \
        || true)
    if [ -n "$hits" ]; then
        echo "$hits"
        echo 'content[ read outside engine.py — route through Engine.contents()/domain() (issue #104)' >&2
        exit 1
    fi

# Corpus-coverage drift guard (issue #633): a wire-type/cage-kind combination
# with no `found-` or no `broke-` link under src/gridfind/links/ is a
# coverage hole. Exits non-zero on any hole, gating the same way
# content-width-check does.
link-coverage-check:
    uv run python scripts/audit_link_coverage.py

# Auto-fix + format in place.
fmt:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run ty check

test:
    uv run pytest

# On-demand real-link E2E suite (spec #185, issue #186): drives real
# SudokuMaker links through the CLI front door. CP-SAT-slow, not flaky —
# skipped by `just check` / `uv run pytest` via the `not e2e` deselection.
e2e:
    uv run pytest -m e2e

# On-demand slow library tests: exhaustive enumerations and other CP-SAT-heavy
# checks too slow for `just check`, skipped there via the `not slow` deselection.
slow:
    uv run pytest -m slow

# On-demand solution-link oracle (spec #244, issue #249): for every link
# under src/gridfind/links/, prints a found link's witness filled back in as
# an openable sudokumaker.app solution-link, or `broke` for a broke link.
# CP-SAT-slow, kept out of `just check` and `just e2e`.
verify-links:
    uv run python scripts/verify_links.py

# On-demand human-eval tool (spec #244): serves a localhost page with, per
# link, the puzzle link, an openable solution-link (found), and an Approve
# button. Approvals persist in a gitignored log so re-runs show only what's
# left; `--all` shows every link. CP-SAT-slow, kept out of `just check`.
eval-links *ARGS:
    uv run python scripts/eval_links.py {{ARGS}}

# Regenerate docs/accepted-link-setter-guide.html from code (ADR-0013). Run
# this after touching DECODER_REGISTRY, a cage-name frozenset, BOX_SHAPE, or
# the template — `just check`'s test suite fails on any resulting drift.
setter-guide:
    uv run python scripts/generate_setter_guide.py
