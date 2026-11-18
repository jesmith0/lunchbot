from pathlib import Path

import pytest

from config import DEFAULT_DATA_DIR, Config, ConfigError


def test_defaults_without_env():
    config = Config.from_env({})
    assert config.data_dir == DEFAULT_DATA_DIR
    assert config.webhook_url is None
    assert config.room_webhooks == {}


def test_reads_env():
    config = Config.from_env(
        {
            "LUNCHBOT_DATA_DIR": "/srv/lunchbot",
            "LUNCHBOT_WEBHOOK_URL": "https://example.test/default",
            "LUNCHBOT_ROOM_WEBHOOKS": '{"Rogue One": "https://example.test/ro"}',
        }
    )
    assert config.data_dir == Path("/srv/lunchbot")
    assert config.webhook_for("Rogue One") == "https://example.test/ro"
    assert config.webhook_for("anything else") == "https://example.test/default"


def test_empty_values_fall_back_to_defaults():
    config = Config.from_env(
        {"LUNCHBOT_DATA_DIR": "", "LUNCHBOT_WEBHOOK_URL": "", "LUNCHBOT_ROOM_WEBHOOKS": ""}
    )
    assert config == Config.from_env({})


def test_missing_webhook_raises():
    with pytest.raises(ConfigError, match="LUNCHBOT_WEBHOOK_URL"):
        Config().webhook_for("Rogue One")


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", '{"room": 5}'])
def test_invalid_room_webhooks_rejected(raw):
    with pytest.raises(ConfigError, match="LUNCHBOT_ROOM_WEBHOOKS"):
        Config.from_env({"LUNCHBOT_ROOM_WEBHOOKS": raw})


def test_error_message_does_not_leak_urls():
    # Webhook URLs contain auth tokens; errors must not echo configured values.
    config = Config(room_webhooks={"a": "https://example.test/secret-token"})
    with pytest.raises(ConfigError) as exc:
        config.webhook_for("b")
    assert "secret-token" not in str(exc.value)
