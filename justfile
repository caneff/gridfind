# One obvious entrypoint for the gate — agents and CI run `just check`.

# Full gate (what CI runs). Run before calling any task done.
check: lint typecheck test content-width-check

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

# Auto-fix + format in place.
fmt:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run ty check

test:
    uv run pytest

# Focused selection over the puzzle corpus, by canonical-stack id or by layer
# name (e.g. `just puzzles rows-distinct`, `just puzzles board+cols-distinct+regions-distinct+rows-distinct`).
puzzles PATTERN:
    uv run pytest src/gridfind/population_test.py -k "{{PATTERN}}"
