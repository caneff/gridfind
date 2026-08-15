import gridfind.layers


def test_every_advertised_name_resolves() -> None:
    # A dangling `__all__` entry breaks `from gridfind.layers import X` for
    # py.typed consumers.
    for name in gridfind.layers.__all__:
        assert hasattr(gridfind.layers, name)
