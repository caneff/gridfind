"""`naming`: the normalized-name -> shape registry both name-bearing carriers
(a `type 2001` cosmetic cage's top-level `name`, a `type 1000` custom
constraint's `definition.name`) route through. Whole-decode coverage of the
carriers themselves lives beside their own modules — `markers_test.py`
(`cosmetic_cage_kind` on `type 2001`), `registry_test.py` (the `type 1000`
carrier-fitness warn-drop) — this file pins the registry and its
normalization directly.
"""

from __future__ import annotations

from hypothesis import given as hyp_given
from hypothesis import strategies as st

from gridfind.sudokumaker.naming import (
    _NAME_REGISTRY,
    _normalize_component_name,
    named_component,
    shape_needs_cells,
)


def test_normalize_component_name_trims_and_lowercases() -> None:
    assert _normalize_component_name("  Sum  ") == "sum"


def test_normalize_component_name_rejects_blank_and_non_string() -> None:
    assert _normalize_component_name(None) is None
    assert _normalize_component_name("") is None
    assert _normalize_component_name("   ") is None
    assert _normalize_component_name(5) is None


def test_named_component_is_none_for_an_unrecognized_name() -> None:
    assert named_component("Whimsy") is None


def test_sum_and_killer_share_the_killer_role_and_cage_selector_shape() -> None:
    assert named_component("Sum") == named_component("Killer")
    component = named_component("Sum")
    assert component is not None
    assert component.role == "killer"
    assert component.shape == "cage-selector"


def test_doubler_is_a_cell_marker() -> None:
    component = named_component("Doubler")
    assert component is not None
    assert component.role == "doubler"
    assert component.shape == "cell-marker"


def test_schrodinger_aliases_share_the_s_cell_role() -> None:
    umlaut = named_component("Schrödinger")
    ascii_fold = named_component("Schrodinger")
    s_cell = named_component("S-cell")
    assert umlaut == ascii_fold == s_cell
    assert s_cell is not None
    assert s_cell.role == "s-cell"
    assert s_cell.shape == "cell-marker"


def test_every_registered_shape_currently_needs_cells() -> None:
    # Both shapes built so far (cage-selector, cell-marker) need a cage's
    # cells — the property carrier-fitness checks a name-bearing carrier
    # against (ADR-0012, #434).
    shapes = {component.shape for component in _NAME_REGISTRY.values()}
    assert shapes == {"cage-selector", "cell-marker"}
    assert all(shape_needs_cells(shape) for shape in shapes)


@hyp_given(
    padding=st.text(alphabet=" \t", max_size=3),
    upper=st.booleans(),
)
def test_a_registered_name_survives_case_and_whitespace_variation(
    padding: str, upper: bool
) -> None:
    # Every registered name recognizes case-insensitively and trimmed,
    # whatever the specific padding or casing a link happens to carry.
    name = "doubler".upper() if upper else "doubler"
    varied = f"{padding}{name}{padding}"

    component = named_component(varied)

    assert component is not None
    assert component.role == "doubler"
