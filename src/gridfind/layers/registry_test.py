import ast
import pathlib

import gridfind.layers


def test_init_module_defines_no_def_or_class() -> None:
    # CODING_STANDARDS: __init__.py is wiring only — imports and __all__, no
    # behavior. A def/class landing here would silently regress that rule.
    source = pathlib.Path(gridfind.layers.__file__).read_text()
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        for node in ast.walk(tree)
    )


def test_public_api_surface_is_exactly_the_committed_names() -> None:
    # A tripwire, not a behavior test: the only thing it enforces is that
    # changing this list is a public API change. Editing `__all__` must be a
    # deliberate act with this expectation updated alongside it.
    #
    # gridfind.layers is internal-only, so its committed
    # public surface is these names — the one door from constraints to a layer
    # stack (`build_stack`), and the two errors it
    # raises (`UnknownLayerError`, `SBlindLayerError`).
    # Registries and layer classes are internal.
    assert set(gridfind.layers.__all__) == {
        "SBlindLayerError",
        "UnknownLayerError",
        "build_stack",
    }
    # Every advertised name must actually resolve — a dangling `__all__` entry
    # breaks `from gridfind.layers import X` for py.typed consumers.
    for name in gridfind.layers.__all__:
        assert hasattr(gridfind.layers, name)
