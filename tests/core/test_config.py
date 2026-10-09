"""Config loading: validation, defaults and unknown keys."""

import logging
from typing import TYPE_CHECKING

import pytest

from xincord.core.config import ConfigError, Model, load_config

if TYPE_CHECKING:
    from pathlib import Path


def xfail(requirement: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=requirement)


VALIDATED = xfail("Config files are validated against a typed schema")
DEFAULTED = xfail("Missing config files are created from the default")
UNKNOWN = xfail("Unknown keys warn instead of failing")


class Inner(Model):
    name: str
    count: int = 0


class Sample(Model):
    inner: Inner = Inner(name="default")
    items: tuple[Inner, ...] = ()
    flag: bool = False


DEFAULT = "flag: true\n"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@VALIDATED
def test_valid_file_loads(tmp_path: Path) -> None:
    path = write(tmp_path, "inner: {name: a, count: 2}\nitems: [{name: b}]\n")

    loaded = load_config(path, Sample, DEFAULT)

    assert loaded == Sample(inner=Inner(name="a", count=2), items=(Inner(name="b"),))


@VALIDATED
def test_invalid_value_is_reported_with_its_location(tmp_path: Path) -> None:
    path = write(tmp_path, "items:\n  - name: b\n    count: many\n")

    with pytest.raises(ConfigError) as error:
        load_config(path, Sample, DEFAULT)

    assert str(path) in str(error.value)
    assert "items.0.count" in str(error.value)


@VALIDATED
@pytest.mark.parametrize("text", ["flag: [unclosed\n", "- a\n- list\n", "just text\n"])
def test_broken_yaml_is_reported(tmp_path: Path, text: str) -> None:
    path = write(tmp_path, text)

    with pytest.raises(ConfigError, match=str(path)):
        load_config(path, Sample, DEFAULT)


@VALIDATED
def test_empty_file_uses_the_defaults(tmp_path: Path) -> None:
    path = write(tmp_path, "")

    assert load_config(path, Sample, DEFAULT) == Sample()


@DEFAULTED
def test_default_is_written_for_a_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "plugins" / "Example" / "config.yaml"

    loaded = load_config(path, Sample, DEFAULT)

    assert path.read_text(encoding="utf-8") == DEFAULT
    assert loaded == Sample(flag=True)


@DEFAULTED
def test_existing_file_is_kept(tmp_path: Path) -> None:
    path = write(tmp_path, "flag: false\n")

    loaded = load_config(path, Sample, DEFAULT)

    assert loaded.flag is False
    assert path.read_text(encoding="utf-8") == "flag: false\n"


@UNKNOWN
def test_unknown_nested_key_is_reported(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = write(tmp_path, "inner: {name: a, colour: red}\nitems: [{name: b, size: 3}]\nextra: 1\n")

    with caplog.at_level(logging.WARNING, logger="xincord.core.config"):
        loaded = load_config(path, Sample, DEFAULT)

    assert loaded.inner.name == "a"
    warnings = [record.getMessage() for record in caplog.records]
    for key in ("inner.colour", "items.0.size", "extra"):
        assert any(key in message and str(path) in message for message in warnings), key
