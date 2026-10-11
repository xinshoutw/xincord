"""The container image and the compose service."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
# Exact versions of the pinned series, so that Renovate's patch updates pass.
PYTHON_IMAGE = re.compile(r"python:3\.14\.\d+-slim-trixie\b")
UV_IMAGE = re.compile(r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+\s")


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

    assert all(PYTHON_IMAGE.match(steps[index][1]) for index in stages)
    assert any(keyword == "COPY" and UV_IMAGE.search(arguments) for keyword, arguments in steps)
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


def test_time_zone_from_env() -> None:
    """Requirement: Time zone from .env."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert compose["services"]["bot"]["environment"]["TZ"] == "${TZ:-UTC}"
    assert re.search(r"^# TZ=\S+$", example, re.MULTILINE)


# Lavalink 4.2.0 or a later 4.x, exact: DAVE arrived in 4.2.0.
LAVALINK_IMAGE = re.compile(r"ghcr\.io/lavalink-devs/lavalink:4\.(?:[2-9]|[1-9]\d+)\.\d+")
EXACT = re.compile(r":\d+\.\d+\.\d+$")  # a Maven version that never moves
SNAPSHOT = re.compile(r":[0-9a-f]{40}$")  # a snapshot's commit, which never moves either


def test_build_context_leaves_out_the_secrets() -> None:
    """Requirement: Container image."""
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ignored = {line.strip() for line in lines if line.strip() and not line.startswith("#")}

    assert {".env", "lavalink"} <= ignored


def test_bot_starts_after_the_node() -> None:
    """Requirement: Compose service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))

    # Started, not healthy: the other plugins run while the node starts or fails.
    assert compose["services"]["bot"]["depends_on"] == {
        "lavalink": {"condition": "service_started"}
    }


def test_lavalink_service() -> None:
    """Requirement: Lavalink service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    lavalink = compose["services"]["lavalink"]

    assert LAVALINK_IMAGE.fullmatch(lavalink["image"])  # Ubuntu (glibc for DAVE), arm64 too
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


def test_node_config() -> None:
    """Requirement: Lavalink service."""
    config = yaml.safe_load((ROOT / "lavalink" / "application.yml").read_text(encoding="utf-8"))

    dependencies = [plugin["dependency"] for plugin in config["lavalink"]["plugins"]]
    assert [dependency.rsplit(":", 1)[0] for dependency in dependencies] == [
        "dev.lavalink.youtube:youtube-plugin",
        "com.github.topi314.lavasrc:lavasrc-plugin",
    ]
    snapshots = [plugin["snapshot"] for plugin in config["lavalink"]["plugins"]]
    # A release, or a snapshot pinned by its commit (youtube-source until a release has its fixes).
    assert all(
        (SNAPSHOT if snapshot else EXACT).search(dependency)
        for dependency, snapshot in zip(dependencies, snapshots, strict=True)
    )
    sources = config["lavalink"]["server"]["sources"]
    assert (sources["youtube"], sources["http"], sources["local"]) == (False, False, False)
    assert config["logging"]["request"]["enabled"] is False  # it would log every search
    assert config["plugins"]["lavasrc"]["sources"]["spotify"] == "${SPOTIFY_ENABLED:false}"
    assert config["plugins"]["youtube"]["enabled"] is True


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


def test_node_logs_no_queries() -> None:
    """Requirement: Lavalink service."""
    config = yaml.safe_load((ROOT / "lavalink" / "application.yml").read_text(encoding="utf-8"))

    # Lavalink 4.2.2's load handler names each identifier at INFO (checked with the image).
    assert config["logging"]["level"]["lavalink.server.player.AudioLoaderRestHandler"] == "WARN"


def test_youtube_oauth() -> None:
    """Requirement: YouTube OAuth for the node."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    environment = compose["services"]["lavalink"]["environment"]
    config = yaml.safe_load((ROOT / "lavalink" / "application.yml").read_text(encoding="utf-8"))
    youtube = config["plugins"]["youtube"]
    example = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    assert environment["YOUTUBE_OAUTH_ENABLED"] == "${YOUTUBE_OAUTH_ENABLED:-false}"
    assert environment["YOUTUBE_OAUTH_REFRESH_TOKEN"] == "${YOUTUBE_OAUTH_REFRESH_TOKEN:-}"
    assert youtube["clients"] == ["MUSIC", "ANDROID_VR", "WEB", "WEBEMBEDDED", "TV"]
    assert youtube["oauth"] == {
        "enabled": "${YOUTUBE_OAUTH_ENABLED:false}",
        "refreshToken": "${YOUTUBE_OAUTH_REFRESH_TOKEN:}",
    }
    assert "# YOUTUBE_OAUTH_ENABLED=true" in example
    assert "# YOUTUBE_OAUTH_REFRESH_TOKEN=" in example


def test_remote_cipher() -> None:
    """Requirement: Remote cipher for the node."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    environment = compose["services"]["lavalink"]["environment"]
    config = yaml.safe_load((ROOT / "lavalink" / "application.yml").read_text(encoding="utf-8"))
    example = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    assert config["plugins"]["youtube"]["remoteCipher"] == {
        "url": "${YOUTUBE_CIPHER_URL:https://cipher.kikkia.dev/}",
        "password": "${YOUTUBE_CIPHER_PASSWORD:}",
    }
    assert environment["YOUTUBE_CIPHER_URL"] == "${YOUTUBE_CIPHER_URL:-https://cipher.kikkia.dev/}"
    assert environment["YOUTUBE_CIPHER_PASSWORD"] == "${YOUTUBE_CIPHER_PASSWORD:-}"
    assert any(line.startswith("# YOUTUBE_CIPHER_URL=") for line in example)
    assert "# YOUTUBE_CIPHER_PASSWORD=" in example


@pytest.mark.xfail(strict=True, reason="Compose service")
def test_published_image_in_its_own_directory() -> None:
    """Requirement: Compose service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    bot = compose["services"]["bot"]

    assert bot["image"] == "ghcr.io/xinshoutw/xincord:${XINCORD_VERSION:-latest}"
    assert "build" not in bot  # compose would build instead of pulling
    assert bot["volumes"] == [".:/bot", "data:/bot/data"]


@pytest.mark.xfail(strict=True, reason="Compose service")
def test_building_from_a_clone() -> None:
    """Requirement: Compose service."""
    override = yaml.safe_load((ROOT / "compose.build.yaml").read_text(encoding="utf-8"))

    assert override["services"]["bot"] == {"build": ".", "image": "xincord:local"}


@pytest.mark.xfail(strict=True, reason="Lavalink service")
def test_node_config_inline() -> None:
    """Requirement: Lavalink service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    config = yaml.safe_load(compose["configs"]["lavalink"]["content"])

    assert compose["services"]["lavalink"]["configs"] == [
        {"source": "lavalink", "target": "/opt/Lavalink/application.yml"}
    ]
    assert "volumes" not in compose["services"]["lavalink"]
    assert config["server"]["port"] == 2333
    assert not (ROOT / "lavalink").exists()


def test_image_turns_off_cpr() -> None:
    """Requirement: No cursor position requests."""
    steps = instructions()
    stages = [index for index, (keyword, _) in enumerate(steps) if keyword == "FROM"]
    runtime = steps[stages[-1] :]

    assert any(
        keyword == "ENV" and "PROMPT_TOOLKIT_NO_CPR=1" in arguments.split()
        for keyword, arguments in runtime
    )
