# gridfind — agent guide

Grid-puzzle constraint solving and validation: decide found / broke / unknown. CP-SAT engine (OR-Tools), Python only.

> Keep this file and `CODING_STANDARDS.md` thin — progressive disclosure:
> pointers here, detail in `docs/agents/*.md`. New guidance = a new doc + a
> pointer, never inline prose.

- Commands → `docs/agents/commands.md`
- Where things are → `docs/agents/where-things-are.md`
- Coding + testing standards → `CODING_STANDARDS.md`
- Domain / context → `CONTEXT.md`, `docs/agents/domain.md`
- Issue tracker → `docs/agents/issue-tracker.md`
- Triage labels → `docs/agents/triage-labels.md`
- Design reasoning → `docs/agents/design-reasoning.md`

## SudokuMaker links (always on)

Load the global `sm-link` skill before generating, editing, or sharing a SudokuMaker link. It holds the givens/ring/pencilmark rules, the pre-share decode check, and the sudokumaker.app wire-format pointers (single home, moved from vault memory in second-brain-v2 #140).
