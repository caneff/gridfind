"""Grid-puzzle constraint solving and validation: `verdict(puzzle, working_state)`
decides found / broke / unknown and, on found, hands back a completed
`Witness`. `Puzzle` and `WorkingState` are the structured input;
`enumerate_witnesses` collects up to N distinct completions instead of one."""

from gridfind.puzzle import Puzzle, WorkingState
from gridfind.verdict import Enumeration, Result, enumerate_witnesses, verdict

__all__ = [
    "Enumeration",
    "Puzzle",
    "Result",
    "WorkingState",
    "enumerate_witnesses",
    "verdict",
]
