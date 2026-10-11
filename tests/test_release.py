"""Releases: a signed `v*` tag builds the distributions and the image and creates the Release."""

import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from release_version import main, release_version

ROOT = Path(__file__).parent.parent
PINNED = re.compile(r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+(\.\d+)*")

type Config = dict[str, Any]


def workflow() -> Config:
    """Return `.github/workflows/release.yml`."""
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    return cast("Config", yaml.safe_load(text))


def steps(job: str) -> list[Config]:
    """Return a job's steps."""
    return cast("list[Config]", workflow()["jobs"][job]["steps"])


def step(job: str, text: str) -> Config:
    """Return the job's step whose `uses` or `run` contains ``text``."""
    return next(item for item in steps(job) if text in item.get("uses", item.get("run", "")))


def projects(root: Path, core: str, plugins: str) -> Path:
    """Write the two `pyproject.toml` files with the given versions."""
    (root / "packages" / "xincord-plugins").mkdir(parents=True)
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{core}"\n', encoding="utf-8")
    (root / "packages" / "xincord-plugins" / "pyproject.toml").write_text(
        f'[project]\nversion = "{plugins}"\n', encoding="utf-8"
    )
    return root


def test_matching_versions(tmp_path: Path) -> None:
    """Requirement: Signed release tags."""
    root = projects(tmp_path, "1.2.3", "1.2.3")

    assert release_version(root) == "1.2.3"
    assert release_version(root, "v1.2.3") == "1.2.3"


def test_mismatched_versions(tmp_path: Path) -> None:
    """Requirement: Signed release tags."""
    differing = projects(tmp_path / "differing", "1.2.3", "1.2.4")
    same = projects(tmp_path / "same", "1.2.3", "1.2.3")

    with pytest.raises(ValueError, match=r"1\.2\.3, 1\.2\.4"):
        release_version(differing)
    with pytest.raises(ValueError, match=r"v1\.2\.4 .*1\.2\.3"):
        release_version(same, "v1.2.4")


def test_script_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    """Requirement: Signed release tags."""
    assert main([]) == 0
    version = capsys.readouterr().out.strip()
    assert main([f"v{version}"]) == 0
    assert main(["v0.0.0-not-this"]) == 1
    assert "error:" in capsys.readouterr().err


def test_trigger_and_signature() -> None:
    """Requirement: Signed release tags."""
    raw = cast("dict[object, Any]", workflow())
    triggers = cast("Config", raw.get("on", raw.get(True)))  # YAML 1.1 reads `on` as true
    names = [item.get("name", item.get("uses", item.get("run"))) for item in steps("release")]
    check = step("release", "git verify-tag")

    assert triggers["push"] == {"tags": ["v*"]}
    assert "workflow_dispatch" in triggers
    assert check["if"] == "github.ref_type == 'tag'"
    assert ".gpg" in check["run"]
    assert names.index(check["name"]) < names.index(step("release", "uv build")["name"])
    assert "release_version.py" in step("release", "release_version.py")["run"]


def test_image() -> None:
    """Requirement: Release artifacts."""
    image = step("release", "docker/build-push-action")["with"]

    assert image["platforms"] == "linux/amd64,linux/arm64"
    assert image["push"] == "${{ github.ref_type == 'tag' }}"
    assert image["tags"].splitlines() == [
        "ghcr.io/${{ github.repository_owner }}/xincord:${{ steps.version.outputs.version }}",
        "ghcr.io/${{ github.repository_owner }}/xincord:latest",
    ]
    assert "org.opencontainers.image.source=" in image["labels"]
    assert "uv build --all-packages" in step("release", "uv build")["run"]


def test_github_release() -> None:
    """Requirement: Release artifacts."""
    notes = step("release", "git log")
    release = step("release", "gh release create")

    assert release["if"] == "github.ref_type == 'tag'"
    assert "--verify-tag" in release["run"]
    assert "dist/*" in release["run"]
    assert "--notes-file" in release["run"]
    assert "--prerelease" in release["run"]
    assert notes["if"] == "github.ref_type == 'tag'"


def test_dry_runs_push_nothing() -> None:
    """Requirement: Dry runs."""
    guarded = [
        step("release", "docker/login-action"),
        step("release", "gh release create"),
        step("release", "git verify-tag"),
    ]

    assert all(item["if"] == "github.ref_type == 'tag'" for item in guarded)
    assert all(
        "github.ref_type == 'tag'" in workflow()["jobs"][job]["if"]
        for job in ("pypi", "pypi-plugins")
    )


def test_pypi_waits_for_one_point_oh() -> None:
    """Requirement: PyPI from 1.0.0."""
    job = workflow()["jobs"]["pypi"]
    commands = " ".join(item.get("run", "") for item in job["steps"])

    assert "!startsWith(github.ref_name, 'v0.')" in job["if"]
    assert job["environment"] == "pypi"
    assert job["permissions"] == {"contents": "read", "id-token": "write"}
    assert "gh release download" in commands
    assert "uv publish --trusted-publishing always" in commands


def test_pypi_job_per_package() -> None:
    """Requirement: PyPI from 1.0.0."""
    jobs = workflow()["jobs"]
    core, plugins = jobs["pypi"], jobs["pypi-plugins"]

    def download(job: Config) -> str:
        return next(item["run"] for item in job["steps"] if "gh release" in item.get("run", ""))

    assert (core["environment"], plugins["environment"]) == ("pypi", "pypi-plugins")
    assert plugins["needs"] == "pypi"
    assert plugins["if"] == core["if"]
    assert plugins["permissions"] == core["permissions"]
    assert "--pattern 'xincord-*'" in download(core)
    assert "--pattern 'xincord_plugins-*'" in download(plugins)
    assert "uv publish --trusted-publishing always" in plugins["steps"][-1]["run"]


def test_actions_and_permissions() -> None:
    """Requirement: PyPI from 1.0.0."""
    config = workflow()
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses: (\S+(?: # \S+)?)", text)
    writers = {
        name: job["permissions"]
        for name, job in cast("dict[str, Config]", config["jobs"]).items()
        if "write" in cast("dict[str, str]", job.get("permissions", {})).values()
    }

    assert uses
    assert all(PINNED.fullmatch(item) for item in uses), uses
    assert config["permissions"] == {"contents": "read"}
    assert writers["release"] == {"contents": "write", "packages": "write"}
    assert set(writers) == {"release", "pypi", "pypi-plugins"}
