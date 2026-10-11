"""Requirement: Command line options.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/Arguments.kt:11-60
"""

import logging
from importlib.metadata import entry_points

import discord
import pytest

from xincord.core import cli
from xincord.core.cli import Options, main, parse_args


def test_defaults() -> None:
    assert parse_args([]) == Options(token=None, level="INFO", no_online=False, force_lang=False)


@pytest.mark.parametrize(
    "argv",
    [
        ["-t", "abc", "-l", "debug", "-N", "-Flang"],
        ["--token", "abc", "--level", "DEBUG", "--no-online", "--force-renew-lang-resources"],
    ],
)
def test_every_option(argv: list[str]) -> None:
    assert parse_args(argv) == Options(token="abc", level="DEBUG", no_online=True, force_lang=True)


@pytest.mark.parametrize(
    "argv", [["--ignore-update"], ["--auto-defer-interactions"], ["--level", "loud"]]
)
def test_rejected_options(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        parse_args(argv)

    assert stopped.value.code == 2
    assert "usage: xincord" in capsys.readouterr().err


@pytest.mark.xfail(strict=True, reason="Command line options")
@pytest.mark.parametrize("argv", [["--token", "abc"], ["-t", "abc"]])
def test_token_option_is_gone(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    """Requirement: Command line options, scenario Rejected options.

    A token on the command line shows in the host's process lists: XINCORD_TOKEN replaces it.
    """
    with pytest.raises(SystemExit) as stopped:
        parse_args(argv)

    assert stopped.value.code == 2
    assert "usage: xincord" in capsys.readouterr().err


def test_the_xincord_command(monkeypatch: pytest.MonkeyPatch) -> None:
    levels: list[int] = []
    runs: list[Options] = []

    def setup_logging(*, level: int, **_: object) -> None:
        levels.append(level)

    async def run(options: Options, *, console: bool = False) -> int:
        assert not console  # pytest's stdin is not a terminal
        runs.append(options)
        return 3

    monkeypatch.setattr(discord.utils, "setup_logging", setup_logging)
    monkeypatch.setattr(cli, "run", run)

    assert main(["-l", "warn", "-N"]) == 3
    assert levels == [logging.WARNING]
    assert runs == [Options(level="WARN", no_online=True)]
    (script,) = entry_points(group="console_scripts", name="xincord")
    assert script.value == "xincord.core.cli:main"
