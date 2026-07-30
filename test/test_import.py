def test_import():
    import radiosoma  # noqa: F401
    from radiosoma import SomaFmStation  # noqa: F401


def test_version():
    from radiosoma.version import __version__
    assert __version__
