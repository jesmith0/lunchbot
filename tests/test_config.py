from pathlib import Path

import pytest

from lunchbot.config import DEFAULT_DATA_DIR, Config, ConfigError, SlackConfig


def test_defaults_without_env():
    assert Config.from_env({}) == Config(data_dir=DEFAULT_DATA_DIR)
    assert DEFAULT_DATA_DIR.name == "data"
    assert (DEFAULT_DATA_DIR / "restaurants.txt").exists()


def test_reads_env():
    assert Config.from_env({"LUNCHBOT_DATA_DIR": "/srv/lunchbot"}).data_dir == Path("/srv/lunchbot")


def test_empty_value_falls_back_to_default():
    assert Config.from_env({"LUNCHBOT_DATA_DIR": ""}) == Config.from_env({})


def test_slack_settings():
    config = Config.from_env(
        {
            "LUNCHBOT_PLATFORM": "slack",
            "SLACK_BOT_TOKEN": "xoxb-1",
            "SLACK_SIGNING_SECRET": "s",
            "SLACK_APP_TOKEN": "",
            "LUNCHBOT_SLACK_CHANNEL": "C1",
        }
    )
    assert config.platform == "slack"
    assert config.slack == SlackConfig(bot_token="xoxb-1", signing_secret="s", channel="C1")


def test_unknown_platform_rejected():
    with pytest.raises(ConfigError, match="LUNCHBOT_PLATFORM"):
        Config.from_env({"LUNCHBOT_PLATFORM": "hipchat"})
