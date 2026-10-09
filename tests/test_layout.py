"""Requirement: Two distributions share the xincord namespace."""

import importlib
from importlib import metadata
from pathlib import Path


def test_both_import_packages_load() -> None:
    core = importlib.import_module("xincord.core")
    plugins = importlib.import_module("xincord.plugins")

    assert core.__name__ == "xincord.core"
    assert plugins.__name__ == "xincord.plugins"
    core_version = metadata.distribution("xincord").version
    assert metadata.distribution("xincord-plugins").version == core_version


def test_xincord_is_a_namespace_package() -> None:
    namespace = importlib.import_module("xincord")
    core = importlib.import_module("xincord.core")
    plugins = importlib.import_module("xincord.plugins")
    assert core.__file__ is not None
    assert plugins.__file__ is not None

    assert getattr(namespace, "__file__", None) is None
    search_path = {Path(entry) for entry in namespace.__path__}
    assert Path(core.__file__).parent.parent in search_path
    assert Path(plugins.__file__).parent.parent in search_path
