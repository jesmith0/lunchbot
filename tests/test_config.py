from pathlib import Path

from lunchbot.config import DEFAULT_DATA_DIR, Config


def test_defaults_without_env():
    assert Config.from_env({}) == Config(data_dir=DEFAULT_DATA_DIR)
    assert DEFAULT_DATA_DIR.name == "data"
    assert (DEFAULT_DATA_DIR / "restaurants.txt").exists()


def test_reads_env():
    assert Config.from_env({"LUNCHBOT_DATA_DIR": "/srv/lunchbot"}).data_dir == Path("/srv/lunchbot")


def test_empty_value_falls_back_to_default():
    assert Config.from_env({"LUNCHBOT_DATA_DIR": ""}) == Config.from_env({})
