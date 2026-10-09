"""Requirement: Core config schema."""

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from xincord.core.config import CoreConfig, default_core_config, load_config

if TYPE_CHECKING:
    from pathlib import Path


def activity(**fields: object) -> dict[str, object]:
    return {"status": {"activities": [{"type": "playing", "text": "a game", **fields}]}}


def target(**fields: object) -> dict[str, object]:
    base = {"guild_id": 1, "channel_id": 2, "types": ["command"], "format": "%user_name%"}
    return {"interaction_log": [base | fields]}


def location(error: pytest.ExceptionInfo[ValidationError]) -> tuple[int | str, ...]:
    return error.value.errors()[0]["loc"]


def test_default_core_config_validates(tmp_path: Path) -> None:
    config = load_config(tmp_path / "config.yaml", CoreConfig, default_core_config())

    assert config.token == ""
    assert config.interaction_log == ()
    assert config.status.activities


def test_full_config_loads() -> None:
    config = CoreConfig.model_validate(
        {
            "token": "secret",
            "status": {
                "activities": [
                    {"type": "streaming", "text": "Live", "url": "https://example.com/live"},
                    {"type": "custom", "text": "Hello", "seconds": 2.5},
                ],
            },
            "interaction_log": [
                {"guild_id": 1, "channel_id": 2, "types": ["command", "modal"], "format": "x"},
            ],
        },
    )

    first, second = config.status.activities
    assert (first.type, first.url, first.seconds) == ("streaming", "https://example.com/live", 5)
    assert (second.type, second.seconds) == ("custom", 2.5)
    assert config.interaction_log[0].types == ("command", "modal")


def test_streaming_activity_needs_a_url() -> None:
    with pytest.raises(ValidationError) as error:
        CoreConfig.model_validate(activity(type="streaming"))

    assert location(error)[:3] == ("status", "activities", 0)


@pytest.mark.parametrize("seconds", [0, -1])
def test_activity_duration_must_be_positive(seconds: float) -> None:
    with pytest.raises(ValidationError) as error:
        CoreConfig.model_validate(activity(seconds=seconds))

    assert location(error)[:3] == ("status", "activities", 0)


def test_interaction_log_types_are_limited() -> None:
    with pytest.raises(ValidationError) as error:
        CoreConfig.model_validate(target(types=["command", "select"]))

    assert location(error)[:2] == ("interaction_log", 0)
