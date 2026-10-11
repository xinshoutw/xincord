"""The container image and the compose service."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent


def instructions() -> list[tuple[str, str]]:
    """Return the Dockerfile's instructions as (keyword, arguments), continuations joined."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8").replace("\\\n", " ")
    steps: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        keyword, _, arguments = line.strip().partition(" ")
        steps.append((keyword.upper(), " ".join(arguments.split())))
    return steps


def test_image_definition() -> None:
    """Requirement: Container image."""
    steps = instructions()
    stages = [index for index, (keyword, _) in enumerate(steps) if keyword == "FROM"]
    runtime = steps[stages[-1] :]

    assert all(steps[index][1].startswith("python:3.14.8-slim-trixie") for index in stages)
    assert any(
        keyword == "COPY" and "ghcr.io/astral-sh/uv:0.12.24" in arguments
        for keyword, arguments in steps
    )
    assert any(
        keyword == "RUN" and "uv sync --locked --no-dev --all-packages --no-editable" in arguments
        for keyword, arguments in steps
    )
    users = [arguments for keyword, arguments in runtime if keyword == "USER"]
    assert users
    assert users[-1] not in {"root", "0"}
    assert ("WORKDIR", "/bot") in runtime
    assert ("ENTRYPOINT", '["xincord"]') in runtime


def test_build_context() -> None:
    """Requirement: Container image."""
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ignored = {line.strip() for line in lines if line.strip() and not line.startswith("#")}

    assert {".git", ".venv", "**/__pycache__", ".pytest_cache", ".ruff_cache", "bot"} <= ignored


def test_service_definition() -> None:
    """Requirement: Compose service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    bot = compose["services"]["bot"]

    assert bot["build"] == "."
    assert bot["volumes"] == ["./bot:/bot", "data:/bot/data"]
    assert (bot["stdin_open"], bot["tty"], bot["init"]) == (True, True, True)
    assert bot["restart"] == "unless-stopped"
    assert bot["stop_grace_period"] == "30s"
    assert bot["logging"] == {
        "driver": "json-file",
        "options": {"max-size": "10m", "max-file": "3"},
    }
    assert "data" in compose["volumes"]


LAVALINK_IMAGE = "ghcr.io/lavalink-devs/lavalink:4.2.2"
EXACT = re.compile(r":\d+\.\d+\.\d+$")  # a Maven version that never moves


@pytest.mark.xfail(strict=True, reason="Container image")
def test_build_context_leaves_out_the_secrets() -> None:
    """Requirement: Container image."""
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ignored = {line.strip() for line in lines if line.strip() and not line.startswith("#")}

    assert {".env", "lavalink"} <= ignored


@pytest.mark.xfail(strict=True, reason="Compose service")
def test_bot_starts_after_the_node() -> None:
    """Requirement: Compose service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))

    # Started, not healthy: the other plugins run while the node starts or fails.
    assert compose["services"]["bot"]["depends_on"] == {
        "lavalink": {"condition": "service_started"}
    }


@pytest.mark.xfail(strict=True, reason="Lavalink service")
def test_lavalink_service() -> None:
    """Requirement: Lavalink service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    lavalink = compose["services"]["lavalink"]

    assert lavalink["image"] == LAVALINK_IMAGE  # Ubuntu (glibc for DAVE), arm64 too
    assert lavalink["volumes"] == ["./lavalink/application.yml:/opt/Lavalink/application.yml:ro"]
    password = lavalink["environment"]["LAVALINK_SERVER_PASSWORD"]
    assert password.startswith("${LAVALINK_PASSWORD:?")  # from .env, required
    health = " ".join(lavalink["healthcheck"]["test"])
    assert "curl" in health
    assert "Authorization: $${LAVALINK_SERVER_PASSWORD}" in health  # /version needs it
    assert "/version" in health
    assert lavalink["restart"] == "unless-stopped"
    assert lavalink["logging"] == {
        "driver": "json-file",
        "options": {"max-size": "10m", "max-file": "3"},
    }
    assert "ports" not in lavalink  # only the bot reaches it, over compose's network


@pytest.mark.xfail(strict=True, reason="Lavalink service")
def test_node_config() -> None:
    """Requirement: Lavalink service."""
    config = yaml.safe_load((ROOT / "lavalink" / "application.yml").read_text(encoding="utf-8"))

    dependencies = [plugin["dependency"] for plugin in config["lavalink"]["plugins"]]
    assert [dependency.rsplit(":", 1)[0] for dependency in dependencies] == [
        "dev.lavalink.youtube:youtube-plugin",
        "com.github.topi314.lavasrc:lavasrc-plugin",
    ]
    assert all(EXACT.search(dependency) for dependency in dependencies)
    sources = config["lavalink"]["server"]["sources"]
    assert (sources["youtube"], sources["http"], sources["local"]) == (False, False, False)
    assert config["logging"]["request"]["enabled"] is False  # it would log every search
    assert config["plugins"]["lavasrc"]["sources"]["spotify"] == "${SPOTIFY_ENABLED:false}"
    assert config["plugins"]["youtube"]["enabled"] is True


@pytest.mark.xfail(strict=True, reason="Lavalink service")
def test_secrets_stay_untracked() -> None:
    """Requirement: Lavalink service."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    values = dict(
        line.split("=", 1)
        for line in example.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

    assert "/.env" in gitignore
    assert values == {"LAVALINK_PASSWORD": "change-me"}  # an example, never a real password
