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


def test_every_advertised_name_resolves() -> None:
    # A dangling `__all__` entry breaks `from gridfind.layers import X` for
    # py.typed consumers.
    for name in gridfind.layers.__all__:
        assert hasattr(gridfind.layers, name)
