"""Dependency updates: Dependabot opens security updates, Renovate opens version updates."""

import json
import re
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).parent.parent
OPENSPEC_PIN = re.compile(r"@fission-ai/openspec@\d")
SKIPPED = ("openspec/changes/archive/", "docs/porting/analysis/research/")
LAVALINK_MAVEN = "https://maven.lavalink.dev/releases"

type Config = dict[str, Any]


def dependabot() -> Config:
    """Return `.github/dependabot.yml`."""
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    return cast("Config", yaml.safe_load(text))


def renovate() -> Config:
    """Return `.github/renovate.json`."""
    text = (ROOT / ".github" / "renovate.json").read_text(encoding="utf-8")
    return cast("Config", json.loads(text))


def rules(config: Config) -> list[Config]:
    """Return Renovate's package rules."""
    return cast("list[Config]", config.get("packageRules", []))


def pattern(text: str) -> re.Pattern[str]:
    """Compile a Renovate regex (`/.../` or a bare match string) with Python's named groups."""
    body = text[1:-1] if len(text) > 1 and text.startswith("/") and text.endswith("/") else text
    return re.compile(re.sub(r"\(\?<(?=[A-Za-z])", "(?P<", body))


def custom(config: Config, datasource: str) -> Config:
    """Return the regex manager that looks versions up in `datasource`."""
    managers = cast("list[Config]", config["customManagers"])
    return next(manager for manager in managers if manager["datasourceTemplate"] == datasource)


def test_dependabot_version_updates_are_off() -> None:
    """Requirement: Dependabot opens security updates only."""
    updates = cast("list[Config]", dependabot()["updates"])

    assert dependabot()["version"] == 2
    assert {update["package-ecosystem"] for update in updates} == {"uv", "github-actions"}
    assert len(updates) == 2
    for update in updates:
        assert update["directory"] == "/"
        assert update["schedule"]["interval"]
        assert update["open-pull-requests-limit"] == 0


def test_dependabot_commit_messages() -> None:
    """Requirement: Dependabot opens security updates only."""
    updates = cast("list[Config]", dependabot()["updates"])
    messages = {update["package-ecosystem"]: update["commit-message"] for update in updates}

    assert messages == {"uv": {"prefix": "build"}, "github-actions": {"prefix": "ci"}}


def test_renovate_waits_seven_days_every_monday() -> None:
    """Requirement: Renovate opens version updates."""
    config = renovate()

    assert "config:recommended" in config["extends"]
    assert config["timezone"] == "Asia/Taipei"
    assert config["schedule"] == ["* * * * 1"]
    assert config["minimumReleaseAge"] == "7 days"
    assert config["internalChecksFilter"] == "strict"
    assert config["vulnerabilityAlerts"] == {"enabled": False}


def test_renovate_commit_messages() -> None:
    """Requirement: Renovate opens version updates."""
    config = renovate()
    actions = [rule for rule in rules(config) if rule.get("matchManagers") == ["github-actions"]]

    assert config["semanticCommits"] == "enabled"
    assert config["semanticCommitType"] == "build"
    assert "semanticCommitScope" in config
    assert config["semanticCommitScope"] is None
    assert [rule.get("semanticCommitType") for rule in actions] == ["ci"]


def test_renovate_managers() -> None:
    """Requirement: Renovate opens version updates."""
    config = renovate()
    pep621 = [
        rule
        for rule in rules(config)
        if rule.get("matchManagers") == ["pep621"] and "rangeStrategy" in rule
    ]
    groups = [rule for rule in rules(config) if rule.get("groupName") == "uv"]

    assert set(config["enabledManagers"]) == {
        "pep621",
        "github-actions",
        "dockerfile",
        "docker-compose",
        "pyenv",
        "custom.regex",
    }
    assert [rule.get("rangeStrategy") for rule in pep621] == ["update-lockfile"]
    assert len(groups) == 1
    assert {"ghcr.io/astral-sh/uv", "uv_build"} <= set(groups[0]["matchPackageNames"])


def test_renovate_ignores_python_ranges_and_the_workspace() -> None:
    """Requirement: Renovate opens version updates."""
    disabled = [rule for rule in rules(renovate()) if rule.get("enabled") is False]

    assert {"matchManagers": ["pep621"], "matchDepTypes": ["requires-python"]}.items() <= next(
        rule for rule in disabled if "matchDepTypes" in rule
    ).items()
    names = next(rule for rule in disabled if "matchPackageNames" in rule)["matchPackageNames"]
    assert {"xincord", "xincord-plugins"} <= set(names)


def test_every_openspec_pin_is_managed() -> None:
    """Requirement: Renovate updates the versions that no manager reads."""
    manager = custom(renovate(), "npm")
    files = [pattern(item) for item in manager["managerFilePatterns"]]
    (match,) = (pattern(item) for item in manager["matchStrings"])
    tracked = [
        *ROOT.glob("*.md"),
        *(ROOT / "scripts").glob("*"),
        *(ROOT / ".github").rglob("*.y*ml"),
        *(ROOT / "docs").rglob("*.md"),
        *(ROOT / "openspec").rglob("*.md"),
    ]
    versions: set[str] = set()
    for path in tracked:
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if relative.startswith(SKIPPED) or not OPENSPEC_PIN.search(text):
            continue
        assert any(file.search(relative) for file in files), relative
        found = [found["currentValue"] for found in match.finditer(text)]
        assert len(found) == len(OPENSPEC_PIN.findall(text)), relative
        versions.update(found)

    assert manager["depNameTemplate"] == "@fission-ai/openspec"
    assert len(versions) == 1


def test_lavalink_plugins_are_managed() -> None:
    """Requirement: Renovate updates the versions that no manager reads."""
    manager = custom(renovate(), "maven")
    (match,) = (pattern(item) for item in manager["matchStrings"])
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    found = {item["depName"]: item["currentValue"] for item in match.finditer(text)}

    files = cast("list[str]", manager["managerFilePatterns"])
    assert any(pattern(item).search("compose.yaml") for item in files)
    assert set(found) == {
        "dev.lavalink.youtube:youtube-plugin",
        "com.github.topi314.lavasrc:lavasrc-plugin",
    }
    assert all(re.fullmatch(r"\d+\.\d+\.\d+|[0-9a-f]{40}", version) for version in found.values())
    assert manager["registryUrlTemplate"] == LAVALINK_MAVEN


def test_snapshot_pins_stay() -> None:
    """Requirement: Renovate updates the versions that no manager reads."""
    snapshot = [
        rule for rule in rules(renovate()) if rule.get("matchCurrentValue") == "/^[0-9a-f]{40}$/"
    ]

    assert len(snapshot) == 1
    assert snapshot[0]["matchPackageNames"] == ["dev.lavalink.youtube:youtube-plugin"]
    assert snapshot[0]["enabled"] is False


def test_node_plugins_in_compose() -> None:
    """Requirement: Renovate updates the versions that no manager reads."""
    manager = custom(renovate(), "maven")
    files = cast("list[str]", manager["managerFilePatterns"])
    ignored = next(
        rule
        for rule in rules(renovate())
        if rule.get("enabled") is False and "xincord" in rule.get("matchPackageNames", [])
    )

    assert any(pattern(item).search("compose.yaml") for item in files)
    assert "ghcr.io/xinshoutw/xincord" in ignored["matchPackageNames"]


def test_patch_updates_automerge() -> None:
    """Requirement: Renovate automerges patch updates and lock-file maintenance only."""
    config = renovate()
    automerged = [rule for rule in rules(config) if rule.get("automerge") is True]

    assert config["separateMinorPatch"] is True
    assert [rule.get("matchUpdateTypes") for rule in automerged] == [["patch"]]
    assert config.get("automerge", False) is False


def test_minor_and_major_updates_wait() -> None:
    """Requirement: Renovate automerges patch updates and lock-file maintenance only."""
    every = rules(renovate())
    last_automerge = max(index for index, rule in enumerate(every) if rule.get("automerge"))
    python = [
        index
        for index, rule in enumerate(every)
        if "python" in rule.get("matchPackageNames", [])
        and set(rule.get("matchUpdateTypes", [])) == {"minor", "major"}
        and rule.get("automerge") is False
    ]

    assert len(python) == 1
    assert python[0] > last_automerge


def test_lock_file_maintenance_is_monthly() -> None:
    """Requirement: Renovate automerges patch updates and lock-file maintenance only."""
    maintenance = cast("Config", renovate()["lockFileMaintenance"])

    assert maintenance == {"enabled": True, "schedule": ["* 0-3 1 * *"], "automerge": True}


def test_renovate_waits_for_ci() -> None:
    """Requirement: Renovate automerges patch updates and lock-file maintenance only."""
    config = renovate()
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    triggers = workflow.get("on", workflow.get(True))  # YAML 1.1 reads a bare `on` as true

    assert config["platformAutomerge"] is False
    assert config["automergeType"] == "pr"
    assert config["automergeStrategy"] == "squash"
    assert config.get("ignoreTests", False) is False
    assert "pull_request" in triggers


def test_updates_without_release_dates_wait_for_the_owner() -> None:
    """Requirement: Renovate automerges patch updates and lock-file maintenance only."""
    every = rules(renovate())
    ghcr = [rule for rule in every if rule.get("matchPackageNames") == ["ghcr.io/**"]]
    runners = [rule for rule in every if rule.get("matchDepTypes") == ["github-runner"]]

    for rule in (*ghcr, *runners):
        assert rule["minimumReleaseAge"] is None
        assert rule["automerge"] is False
    assert len(ghcr) == len(runners) == 1
    last_automerge = max(index for index, rule in enumerate(every) if rule.get("automerge"))
    assert min(every.index(ghcr[0]), every.index(runners[0])) > last_automerge
