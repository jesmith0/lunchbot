import random

import pytest

from lunchbot.core import Bot
from lunchbot.storage import Store


class FixedRandom(random.Random):
    """random() always returns `value`; weighted choices still work."""

    def __init__(self, value: float = 0.99) -> None:
        super().__init__(0)
        self.value = value

    def random(self) -> float:
        return self.value


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "restaurants.txt").write_text("CHIPOTLE, 5\nEVOS, 1\n")
    (tmp_path / "drivers.txt").write_text("JEREMY, 1\n")
    (tmp_path / "vetos.txt").write_text("")
    return tmp_path


@pytest.fixture
def store(data_dir):
    return Store(data_dir)


@pytest.fixture
def bot(store):
    # 0.99 never triggers the Friday tech talk (see TECH_TALK_CHANCE)
    return Bot(store, rng=FixedRandom(0.99))
