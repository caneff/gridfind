"""The witness-search strategy seam (spec #4, decisions 30, 33).

The core ships exactly one strategy — pure-satisfaction: no objective, no
near-miss. A downstream variant may contribute an alternate strategy (e.g.
objective-guided) without a core rewrite.
"""

from __future__ import annotations

from typing import Protocol

from ortools.sat.python import cp_model


class Strategy(Protocol):
    """Configures the model for the witness-find half of the verdict race."""

    def configure(self, model: cp_model.CpModel) -> None: ...


class PureSatisfaction:
    """The sole shipped strategy: find any witness, no objective to guide it."""

    def configure(self, model: cp_model.CpModel) -> None:
        pass


PURE_SATISFACTION = PureSatisfaction()
