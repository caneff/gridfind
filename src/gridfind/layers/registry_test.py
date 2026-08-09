import gridfind.layers


def test_public_api_surface_is_exactly_the_committed_names() -> None:
    # A tripwire, not a behavior test: the only thing it enforces is that
    # changing this list is a public API change. Editing `__all__` must be a
    # deliberate act with this expectation updated alongside it.
    #
    # Issue #101 / #25 / #24: gridfind.layers is internal-only, so its committed
    # public surface is these names — the one door from constraints to a layer
    # stack (`build_stack`), `canonical_identity`, and `UnknownLayerError`.
    # Registries and layer classes are internal.
    assert gridfind.layers.__all__ == [
        "UnknownLayerError",
        "build_stack",
        "canonical_identity",
    ]
