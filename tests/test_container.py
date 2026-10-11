"""The container image and the compose service."""

import re
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).parent.parent
# Exact versions of the pinned series, so that Renovate's patch updates pass.
PYTHON_IMAGE = re.compile(r"python:3\.14\.\d+-slim-trixie\b")
UV_IMAGE = re.compile(r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+\s")
PINNED = re.compile(r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+(\.\d+)*")  # an action at a commit


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


def node_config() -> dict[str, Any]:
    """Return the Lavalink node's config, inline in `compose.yaml`, as compose leaves it."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    return cast("dict[str, Any]", yaml.safe_load(compose["configs"]["lavalink"]["content"]))


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

    assert {".git", ".venv", "**/__pycache__", ".pytest_cache", ".ruff_cache"} <= ignored
    assert {"config.yaml", "plugins", "data"} <= ignored  # the bot's files in a clone


def test_service_definition() -> None:
    """Requirement: Compose service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    bot = compose["services"]["bot"]

    assert bot["volumes"] == [".:/bot", "data:/bot/data"]
    assert bot["init"] is True
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

    assert ".env" in ignored


def test_lavalink_service() -> None:
    """Requirement: Lavalink service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    lavalink = compose["services"]["lavalink"]

    assert LAVALINK_IMAGE.fullmatch(lavalink["image"])  # Ubuntu (glibc for DAVE), arm64 too
    assert lavalink["configs"] == [
        {"source": "lavalink", "target": "/opt/Lavalink/application.yml"}
    ]
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
    config = node_config()

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
    assert config["plugins"]["lavasrc"]["sources"]["spotify"] == "${SPOTIFY_ENABLED:-false}"
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
    config = node_config()

    # Lavalink 4.2.2's load handler names each identifier at INFO (checked with the image).
    assert config["logging"]["level"]["lavalink.server.player.AudioLoaderRestHandler"] == "WARN"


def test_youtube_oauth() -> None:
    """Requirement: YouTube OAuth for the node."""
    youtube = node_config()["plugins"]["youtube"]
    example = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    assert youtube["clients"] == ["MUSIC", "ANDROID_VR", "WEB", "WEBEMBEDDED", "TV"]
    assert youtube["oauth"] == {  # compose fills them in from .env
        "enabled": "${YOUTUBE_OAUTH_ENABLED:-false}",
        "refreshToken": "${YOUTUBE_OAUTH_REFRESH_TOKEN:-}",
    }
    assert "# YOUTUBE_OAUTH_ENABLED=true" in example
    assert "# YOUTUBE_OAUTH_REFRESH_TOKEN=" in example


def test_remote_cipher() -> None:
    """Requirement: Remote cipher for the node."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    assert node_config()["plugins"]["youtube"]["remoteCipher"] == {  # compose fills them in
        "url": "${YOUTUBE_CIPHER_URL:-https://cipher.kikkia.dev/}",
        "password": "${YOUTUBE_CIPHER_PASSWORD:-}",
    }
    assert any(line.startswith("# YOUTUBE_CIPHER_URL=") for line in example)
    assert "# YOUTUBE_CIPHER_PASSWORD=" in example


def test_published_image_in_its_own_directory() -> None:
    """Requirement: Compose service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    bot = compose["services"]["bot"]

    assert bot["image"] == "ghcr.io/xinshoutw/xincord:${XINCORD_VERSION:-latest}"
    assert "build" not in bot  # compose would build instead of pulling
    assert bot["volumes"] == [".:/bot", "data:/bot/data"]


def test_building_from_a_clone() -> None:
    """Requirement: Compose service."""
    override = yaml.safe_load((ROOT / "compose.build.yaml").read_text(encoding="utf-8"))

    assert override["services"]["bot"] == {"build": ".", "image": "xincord:local"}


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


def test_bot_runs_without_a_terminal() -> None:
    """Requirement: Compose service.

    Without a TTY the console stays off, so the container's log holds no prompt.
    """
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    bot = compose["services"]["bot"]

    assert "tty" not in bot
    assert "stdin_open" not in bot


def test_bot_starts_after_the_node_when_it_runs() -> None:
    """Requirement: Compose service."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))

    # Started, not healthy, and only when the music profile runs it.
    assert compose["services"]["bot"]["depends_on"] == {
        "lavalink": {"condition": "service_started", "required": False}
    }


def test_node_only_with_the_music_profile() -> None:
    """Requirement: Lavalink service, scenario Only with the music profile."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert compose["services"]["lavalink"]["profiles"] == ["music"]
    assert re.search(r"^# COMPOSE_PROFILES=music$", example, re.MULTILINE)


def test_image_checked_in_ci() -> None:
    """Requirement: Image checked in CI."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    steps = cast("list[dict[str, Any]]", yaml.safe_load(text)["jobs"]["image"]["steps"])
    (build,) = [step for step in steps if step.get("uses", "").startswith("docker/build-push-")]
    runs = [cast("str", step["run"]) for step in steps if "run" in step]

    assert build["with"]["platforms"] == "linux/amd64"
    assert (build["with"]["push"], build["with"]["load"]) == (False, True)
    assert any("entry_points" in run and "xincord.plugins" in run for run in runs)
    assert any(run.rstrip().endswith("--no-online") for run in runs)
    uses = re.findall(r"uses: (\S+(?: # \S+)?)", text)
    assert all(PINNED.fullmatch(item) for item in uses), uses


def test_token_from_env() -> None:
    """Requirement: Token from .env."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert compose["services"]["bot"]["environment"]["XINCORD_TOKEN"] == "${XINCORD_TOKEN:-}"
    assert re.search(r"^# XINCORD_TOKEN=$", example, re.MULTILINE)


def test_build_context_leaves_out_the_backups() -> None:
    """Requirement: Container image, scenario Build context."""
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ignored = {line.strip() for line in lines if line.strip() and not line.startswith("#")}

    assert "backups" in ignored
