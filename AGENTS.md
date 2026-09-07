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

Moved here from the second-brain vault memory (second-brain-v2 #140) so it loads only in SudokuMaker sessions.

- When generating a SudokuMaker puzzle link or board, a cell holds a value only when it is a given, and most outside-clue ring cells stay blank. Never store the solution or a hidden clue as a non-given value (it ships as an entered digit), and never fill the whole ring ("the same dumbass thing as always"). Chris has had to say both repeatedly; verify with a decode that non-given cells are `{}` and the ring is sparse before reporting a link share-ready. Two exceptions: pencilmarks he asks for by name ("add the pencilmarks too") are candidates, not values, and are wanted; and a ring carved to CP-SAT minimality is "mostly blank" by definition (owner ruling, sudokumaker #286) — do not re-derive or thin it.
- SudokuMaker lives at sudokumaker.app — sudokumaker.com is a parked domain. For wire-format questions, read the app's main-*.js bundle (live fetch or the HAR under examples/_shared), and check gridfind's docs/research/ for the recorded method before re-deriving it.
