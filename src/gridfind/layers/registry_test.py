import gridfind.layers


def test_public_api_surface_is_exactly_the_committed_names() -> None:
    # A tripwire, not a behavior test: the only thing it enforces is that
    # changing this list is a public API change. Editing `__all__` must be a
    # deliberate act with this expectation updated alongside it.
    #
    # gridfind.layers is internal-only, so its committed
    # public surface is these names — the one door from constraints to a layer
    # stack (`build_stack`), `canonical_identity`, and `UnknownLayerError`.
    # Registries and layer classes are internal.
    assert set(gridfind.layers.__all__) == {
        "UnknownLayerError",
        "build_stack",
        "canonical_identity",
    }
    # Every advertised name must actually resolve — a dangling `__all__` entry
    # breaks `from gridfind.layers import X` for py.typed consumers.
    for name in gridfind.layers.__all__:
        assert hasattr(gridfind.layers, name)
