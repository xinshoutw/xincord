"""The container image and the compose service."""

from pathlib import Path

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
